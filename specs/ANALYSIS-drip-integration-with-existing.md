---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-27"
status: reviewed
source_skill: sf-docs
scope: feature
owner: Diane
confidence: medium
risk_level: medium
security_impact: unknown
docs_impact: yes
user_story: "Cartographier l'integration du module Drip avec les composants existants de ContentFlow Lab"
linked_systems: []
depends_on: []
supersedes: []
evidence: []
next_step: "/sf-docs audit specs/DRIP_IMPLEMENTATION.md"
---
# Analyse d'integration : Content Drip × Existant ContentFlow Lab

Date: 2026-04-06
Companion de: `SPEC-progressive-content-release.md`

---

## Objectif

Cartographier ce qui existe deja dans le Lab, ce qu'on peut reutiliser directement,
ce qu'on doit adapter, et ce qu'on doit creer from scratch pour le Content Drip.

Ce document est fige comme reference d'analyse historique pour expliquer les choix
de conception qui ont precede l'implementation.

## Questions ouvertes (non bloquantes)

- Valider la source de verite finale entre cette analyse et `specs/DRIP_IMPLEMENTATION.md` pour eviter une double maintenance.
- Confirmer si les endpoints "analyze/approve/start/status" de la spec initiale doivent etre conserves en alias ou consideres obsoletes face aux endpoints implementes.
- Decider si ce document doit rester un artefact d'analyse historique ou etre converti en ADR (decision record) succinct.

---

## 1. Cartographie de l'existant pertinent

### 1.1 StatusService (`status/service.py`) — REUTILISABLE A 80%

C'est le coeur du systeme. Singleton SQLite avec WAL mode.

**Ce qui existe et qu'on reutilise tel quel :**

| Methode | Usage pour le Drip |
|---------|--------------------|
| `create_content()` | Creer un ContentRecord par article importe dans le drip |
| `transition()` | Passer un article de SCHEDULED → PUBLISHING → PUBLISHED |
| `get_history()` | Audit trail des publications drip |
| `get_stats()` | Dashboard de progression (N published, N scheduled, etc.) |
| `list_content()` | Filtrer par status/project pour trouver les articles du drip |
| `update_content()` | Mettre a jour `scheduled_for`, `published_at`, `metadata` |
| `get_due_jobs()` | **Deja le cron tick** — trouve les jobs ou `next_run_at <= now` |
| `create_schedule_job()` | Creer le job de drip recurrent |
| `find_similar_content()` | Detection de doublons a l'import |

**Ce qu'il faut adapter :**

- `list_content()` a besoin d'un filtre `scheduled_for BETWEEN ? AND ?` pour le calendrier drip
- Un nouveau `source_robot` a ajouter : `"drip"` dans l'enum `SourceRobot`
- Un nouveau `content_type` possible : `"drip-batch"` ou reutiliser `"article"`

### 1.2 ContentRecord (`status/schemas.py`) — REUTILISABLE DIRECTEMENT

Le schema ContentRecord a **deja tout** ce dont DripItem a besoin :

```
ContentRecord                    DripItem (spec)
═══════════════                  ═══════════════
id                          →    id
title                       →    title
content_path                →    content_ref
status (lifecycle enum)     →    status (pending/scheduled/published)
scheduled_for               →    scheduled_date
published_at                →    published_at
tags                        →    cluster info (via tags ou metadata)
metadata                    →    cluster_id, cluster_name, is_pillar, position
project_id                  →    drip_plan_id (via project_id ou metadata)
priority                    →    position (ordre dans la sequence)
content_hash                →    pour detecter les modifications pendant le drip
```

**Decision cle :** On n'a PAS besoin d'un nouveau modele DripItem.
On utilise ContentRecord avec :
- `source_robot = "drip"`
- `metadata.drip_plan_id` = lien vers le plan
- `metadata.cluster_id`, `metadata.cluster_name`, `metadata.is_pillar`
- `metadata.position` = ordre dans la sequence
- `scheduled_for` = date de publication programmee
- Le lifecycle existant (TODO → SCHEDULED → PUBLISHING → PUBLISHED) couvre parfaitement le flux

**Avantage :** Le calendrier, les stats, l'historique, les filtres — tout marche deja.

### 1.3 ContentLifecycleStatus (`status/schemas.py`) — REUTILISABLE TEL QUEL

```python
TODO → IN_PROGRESS → GENERATED → PENDING_REVIEW → APPROVED → SCHEDULED → PUBLISHING → PUBLISHED
```

Pour le drip, le flux est plus court :
```
APPROVED → SCHEDULED → PUBLISHING → PUBLISHED
```

Les articles importes dans le drip sont deja du contenu existant (pas genere par l'IA).
On les cree directement en `APPROVED` et on les passe en `SCHEDULED` quand le plan est active.

La matrice de transitions existante autorise deja : `APPROVED → SCHEDULED → PUBLISHING → PUBLISHED`. Zero modification.

### 1.4 Schedule Jobs (`status/db.py` table `schedule_jobs`) — REUTILISABLE

La table existe :
```sql
schedule_jobs (
    id, user_id, project_id, job_type, generator_id, configuration,
    schedule, cron_expression, schedule_day, schedule_time, timezone,
    enabled, last_run_at, last_run_status, next_run_at, created_at, updated_at
)
```

Pour le drip, on cree un ScheduleJob avec :
- `job_type = "drip"`
- `configuration = { plan config JSON (cadence, cluster_strategy, ssg_config, gsc_config) }`
- `schedule = "hourly"` ou cron expression custom
- `next_run_at` = prochain tick

`get_due_jobs()` le trouvera automatiquement quand c'est l'heure.

### 1.5 Topical Mesh Architect — REUTILISABLE POUR LE CLUSTERING AUTO

`agents/seo/topical_mesh_architect.py` + `agents/seo/tools/mesh_analyzer.py`

**Ce qui existe :**

| Methode | Ce qu'elle fait | Usage Drip |
|---------|----------------|------------|
| `ExistingMeshAnalyzer.analyze_existing_website()` | Clone/lit un repo, extrait la structure, identifie clusters | **Clustering AUTO** |
| `_build_mesh_from_content()` | Construit le graphe de liens internes | Identifier piliers et spokes |
| `_find_mesh_issues()` | Trouve orphelins, clusters faibles | Prioriser l'ordre de publication |
| `GitHubRepoAnalyzer.find_all_content_files()` | Scanne les fichiers .md/.mdx | Import initial des articles |
| `GitHubRepoAnalyzer.analyze_site_structure()` | Arborescence des fichiers | Clustering par DIRECTORY |

**Adaptations necessaires :**
- `ExistingMeshAnalyzer` travaille par repo URL + git clone. Pour un usage local (GoCharbon sur le meme serveur), il faut supporter `local_repo_path` directement → **deja supporte** via le parametre `local_repo_path` de `analyze_existing_website()`.
- Le resultat du mesh doit etre converti en `{ cluster_id, cluster_name, is_pillar }` pour chaque fichier → **nouveau code**, mais c'est un simple mapping.

### 1.6 Deployment Router (`/api/deployment`) — MODELE A SUIVRE

Pas directement reutilisable (genere du contenu SEO, ne publie pas de l'existant), mais le pattern est le bon :

- `BatchRunRequest` / `BatchProgress` → meme logique pour le drip batch
- `PIPELINE_STEPS` pour le tracking de progression → adapter pour le drip
- In-memory state avec `_current_job` → a remplacer par du SQLite pour la persistance

### 1.7 Calendar Endpoint (`/api/scheduler/calendar`) — A ENRICHIR

Le calendrier agrege deja `ContentRecords` + `ScheduleJobs` pour une plage de dates.
Les articles drip apparaitront automatiquement dans le calendrier car ce sont des ContentRecords avec `scheduled_for`.

**Zero modification** — ca marche out of the box si on utilise ContentRecord.

### 1.8 Publish Router (`/api/publish`) — COMPLEMENTAIRE, PAS IMPACTE

Le publish existant est pour les plateformes sociales (Zernio). Le drip publie vers un SSG.
Deux flux separes, pas de conflit.

### 1.9 SQLite DB (`status/db.py`) — AJOUT D'UNE TABLE

On a besoin d'une seule nouvelle table : `drip_plans`. Les items sont des ContentRecords.

```sql
CREATE TABLE IF NOT EXISTS drip_plans (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',    -- draft|active|paused|completed|cancelled

    -- Configuration (JSON blobs)
    cadence_config TEXT NOT NULL DEFAULT '{}',
    cluster_strategy TEXT NOT NULL DEFAULT '{}',
    ssg_config TEXT NOT NULL DEFAULT '{}',
    gsc_config TEXT,

    -- Stats
    total_items INTEGER NOT NULL DEFAULT 0,

    -- Execution
    started_at TEXT,
    completed_at TEXT,
    last_drip_at TEXT,
    next_drip_at TEXT,

    -- Schedule Job link
    schedule_job_id TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drip_plans_status ON drip_plans(status);
CREATE INDEX IF NOT EXISTS idx_drip_plans_user ON drip_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_drip_plans_project ON drip_plans(project_id);
```

---

## 2. Ce qu'on cree from scratch

### 2.1 Drip Service (`api/services/drip_service.py`)

Logique metier du drip. S'appuie entierement sur StatusService.

```python
class DripService:
    """Orchestrate progressive content publication."""

    def __init__(self, status_svc: StatusService):
        self.svc = status_svc

    # ── Plan CRUD ──
    def create_plan(self, ...) -> dict
    def get_plan(self, plan_id) -> dict
    def list_plans(self, user_id, project_id) -> list
    def update_plan(self, plan_id, ...) -> dict
    def delete_plan(self, plan_id) -> None

    # ── Import & Clustering ──
    def import_content_from_directory(self, plan_id, directory, ...) -> int
        """Scanne les fichiers MD, cree un ContentRecord par article."""
    def cluster_by_directory(self, plan_id) -> dict
        """Groupe les items par arborescence de dossiers."""
    def cluster_by_tags(self, plan_id) -> dict
        """Groupe les items par tags frontmatter."""
    def cluster_auto(self, plan_id, repo_url) -> dict
        """Appelle ExistingMeshAnalyzer pour detecter les cocons."""

    # ── Scheduling ──
    def generate_schedule(self, plan_id) -> list[dict]
        """Assigne les scheduled_for selon cadence + ordre des clusters."""
    def preview_schedule(self, plan_id) -> list[dict]
        """Dry-run : retourne le calendrier sans ecrire."""

    # ── Execution ──
    def activate_plan(self, plan_id) -> dict
        """Cree le ScheduleJob, passe les items en SCHEDULED."""
    def execute_drip_tick(self, plan_id) -> dict
        """Publie les items dus aujourd'hui (appele par le cron)."""
    def pause_plan(self, plan_id) -> dict
    def resume_plan(self, plan_id) -> dict
    def cancel_plan(self, plan_id) -> dict

    # ── SSG Integration ──
    def update_frontmatter(self, file_path, updates) -> None
        """Modifie le frontmatter YAML d'un fichier Markdown."""
    def trigger_rebuild(self, ssg_config) -> dict
        """Envoie le webhook ou trigger GitHub Actions."""

    # ── GSC (Phase 4) ──
    def submit_urls_to_gsc(self, gsc_config, urls) -> dict
    def check_indexation(self, gsc_config, urls) -> dict
```

### 2.2 Drip Router (`api/routers/drip.py`)

Nouveau router FastAPI. Suit exactement le pattern des routers existants.

### 2.3 Frontmatter Parser/Writer

Utilitaire pour lire et modifier le YAML frontmatter des fichiers .md.
N'existe nulle part dans le Lab actuellement.

```python
# api/services/frontmatter.py

def read_frontmatter(file_path: str) -> dict
    """Parse le frontmatter YAML d'un fichier Markdown."""

def update_frontmatter(file_path: str, updates: dict) -> None
    """Met a jour des champs du frontmatter sans toucher au body."""
```

### 2.4 Rebuild Trigger

Utilitaire pour declencher un rebuild SSG.

```python
# api/services/rebuild_trigger.py

async def trigger_webhook(url: str) -> dict
async def trigger_github_actions(repo: str, workflow: str, branch: str, token: str) -> dict
```

---

## 3. Schema d'integration global

```
EXISTANT (reutilise)                    NOUVEAU (a creer)
════════════════════                    ═════════════════

┌──────────────────┐                   ┌──────────────────┐
│  StatusService   │◄──────────────────│  DripService     │
│  (service.py)    │  utilise          │  (drip_service)  │
│                  │                   │                  │
│  • ContentRecord │  ← les items     │  • create_plan   │
│  • transition()  │    du drip sont   │  • import_content│
│  • schedule_jobs │    des CR         │  • cluster_*     │
│  • get_due_jobs  │                   │  • schedule      │
│  • get_stats     │                   │  • execute_tick  │
└────────┬─────────┘                   └────────┬─────────┘
         │                                      │
         │  SQLite                               │ appelle
         ▼                                      ▼
┌──────────────────┐                   ┌──────────────────┐
│  DB Tables       │                   │  ExistingMesh    │
│                  │                   │  Analyzer        │
│  content_records │ ← items drip     │  (mesh_analyzer) │
│  status_changes  │ ← audit trail    │                  │
│  schedule_jobs   │ ← job drip       │  → clusters      │
│  drip_plans  NEW │ ← config plan    │  → piliers       │
└──────────────────┘                   │  → orphelins     │
                                       └──────────────────┘
         ┌──────────────────┐
         │  Calendar        │
         │  (/api/scheduler │
         │   /calendar)     │
         │                  │  ← les drip items apparaissent
         │  Agrege CR +     │     automatiquement car ce sont
         │  ScheduleJobs    │     des ContentRecords avec
         └──────────────────┘     scheduled_for

         ┌──────────────────┐          ┌──────────────────┐
         │  Drip Router     │ NEW      │  Frontmatter     │ NEW
         │  /api/drip/*     │          │  Parser/Writer   │
         │                  │          │                  │
         │  Plans CRUD      │          │  read_frontmatter│
         │  Import          │          │  update_fm       │
         │  Schedule        │          └──────────────────┘
         │  Execute         │
         │  Pause/Resume    │          ┌──────────────────┐
         └──────────────────┘          │  Rebuild Trigger │ NEW
                                       │                  │
                                       │  webhook         │
                                       │  github_actions  │
                                       └──────────────────┘
```

---

## 4. Ce qui n'a PAS besoin de changer

| Composant | Pourquoi il reste intact |
|-----------|------------------------|
| `Publish Router` | Publie vers social (Zernio). Flux separe du drip (SSG). |
| `Deployment Router` | Pipeline de generation SEO. Le drip ne genere pas de contenu. |
| `Internal Linking Agent` | Analyse de liens. Pas impacte par le scheduling. |
| `Newsletter Crew` | Pipeline newsletter independant. |
| `Idea Pool` | Alimentation d'idees. Le drip travaille sur du contenu existant, pas des idees. |
| `Content Templates` | Templates de generation. Le drip ne genere rien. |
| `Auth (Clerk)` | Le drip reutilise l'auth existante via `CurrentUser`. |

---

## 5. Modifications mineures a l'existant

### 5.1 Ajouter `"drip"` a SourceRobot

```python
# agents/scheduler/schemas/publishing_schemas.py
class SourceRobot(str, Enum):
    SEO = "seo"
    NEWSLETTER = "newsletter"
    ARTICLE = "article"
    MANUAL = "manual"
    IMAGES = "images"
    DRIP = "drip"          # ← ajouter
```

### 5.2 Ajouter la table `drip_plans` dans `init_db()`

Ajouter le CREATE TABLE dans `status/db.py` → `init_db()`.

### 5.3 Ajouter un filtre date-range a `list_content()`

```python
# status/service.py → list_content()
# Ajouter un parametre optionnel :
def list_content(self, ..., scheduled_between: Optional[tuple[str, str]] = None):
    if scheduled_between:
        query += " AND scheduled_for BETWEEN ? AND ?"
        params.extend(scheduled_between)
```

### 5.4 Enregistrer le router dans `api/main.py`

```python
from api.routers.drip import router as drip_router
app.include_router(drip_router)
```

---

## 6. Risques d'integration identifies

| Risque | Severite | Mitigation |
|--------|----------|------------|
| **ContentRecord surcharge** — utiliser CR pour les items drip ajoute potentiellement des milliers de records | Moyen | Filtrer par `source_robot = "drip"` dans les vues existantes. Le dashboard n'affiche deja que les records du project actif. |
| **SourceRobot enum** — ajouter une valeur casse les validations existantes si le code deserialise strictement | Faible | L'enum est dans un seul fichier. La migration est une ligne. |
| **Concurrence SQLite** — le cron tick ecrit pendant que l'UI lit | Faible | WAL mode deja active. SQLite gere bien les lectures concurrentes. |
| **Taille du schedule_jobs.configuration** — le JSON de config drip est plus gros que les configs existantes | Negligeable | SQLite TEXT n'a pas de limite pratique. |
| **Calendar flooding** — 290 events drip dans le calendrier | Moyen | Le calendrier filtre deja par plage de dates + project_id. Ajouter un filtre `source_robot` optionnel pour masquer/afficher les drip items. |

---

## 7. Implementation — Status

### Etape 1 — Fondations ✅
- [x] Ajouter `DRIP = "drip"` a `SourceRobot`
- [x] Ajouter `drip_plans` table dans `init_db()`
- [x] Creer `api/services/drip_service.py` avec plan CRUD (store SQLite)
- [x] Creer `api/routers/drip.py` avec plans CRUD endpoints
- [x] Creer `api/models/drip.py` — 13 enums + 8 modeles Pydantic

### Etape 2 — Import et clustering DIRECTORY ✅
- [x] `import_from_directory()` — scanner les .md, creer des ContentRecords
- [x] `api/services/frontmatter.py` — parser/writer YAML frontmatter
- [x] `cluster_by_directory()` — grouper les CR par arborescence, detecter piliers

### Etape 3 — Scheduling + Execution ✅
- [x] `generate_schedule()` — cadence fixe + ramp_up, skip weekends
- [x] `preview` endpoint — dry-run
- [x] `activate_plan()` — creer le ScheduleJob, passer les items en SCHEDULED
- [x] `execute_drip_tick()` — modifier les pubDate/draft dans les fichiers
- [x] `api/services/rebuild_trigger.py` — webhook + GitHub Actions
- [x] Plan lifecycle : pause / resume / cancel
- [x] Auto-completion quand tous les items sont publies

### Etape 4 — Clustering avance ✅
- [x] `cluster_by_tags()` — grouper par tag primaire, pilier = item avec le plus de tags
- [x] `cluster_auto()` — appeler `ExistingMeshAnalyzer`, fallback directory si crewai absent
- [x] Endpoint unifie `/cluster?mode=directory|tags|auto`

### Etape 5 — GSC ✅
- [x] `GSCClient` — Indexing API (submit URL_UPDATED) + URL Inspection API (check indexation)
- [x] Batch submit avec quota (200/jour)
- [x] Endpoints `/gsc/submit-urls` et `/gsc/indexation-status`
- [x] Auto-submit dans `execute-tick` quand GSC configure

---

## 8. Fichiers crees

```
api/
  models/
    drip.py                    # 13 enums + 8 modeles Pydantic
  routers/
    drip.py                    # 17 endpoints /api/drip/*
  services/
    drip_service.py            # 17 methodes (CRUD + import + 3 clustering + schedule + execute + lifecycle)
    frontmatter.py             # Parser/writer YAML frontmatter
    rebuild_trigger.py         # Webhook + GitHub Actions trigger
    gsc_client.py              # Google Search Console (Indexing + URL Inspection APIs)
```

## 9. Fichiers modifies

```
status/db.py                   # +30 lignes : CREATE TABLE drip_plans
agents/scheduler/schemas/publishing_schemas.py  # +1 ligne : DRIP = "drip"
api/main.py                    # +2 lignes : import + include drip_router
```

Total : **6 fichiers crees**, **3 fichiers modifies**.
Toutes les etapes backend sont terminees.

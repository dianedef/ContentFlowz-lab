---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "1.0.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-27"
status: ready
source_skill: sf-docs
scope: feature
owner: Diane
confidence: medium
risk_level: medium
security_impact: unknown
docs_impact: yes
user_story: "Planifier et executer une publication progressive de contenu SSG sans departs d'indexation prematuree"
linked_systems: []
depends_on: []
supersedes: []
evidence: []
next_step: "/sf-docs audit specs/SPEC-progressive-content-release.md"
---
# Spec: Progressive Content Release (Content Drip)

Date: 2026-04-06
Status: Ready
Author: Diane + Claude

---

## Titre

Orchestrer la publication progressive de contenu existant pour les sites SSG :
detection automatique des cocons semantiques, cadence configurable, rebuilds planifies, soumission GSC.

---

## Probleme

### Le cas GoCharbon (et tout site de contenu SSG)

Un site de contenu construit avec un SSG (Astro, Next, Hugo...) accumule du contenu en phase de preparation. Au moment du lancement :

- **~290 articles** sont prets a publier
- Les publier d'un coup envoie un signal negatif a Google ("content farm", "scraped content")
- Google favorise les sites qui publient regulierement et construisent leur autorite topique incrementalement
- L'indexation massive dilue le crawl budget sur des centaines de pages simultanement

### Pourquoi c'est un probleme generique

Tout utilisateur de ContentFlow qui :
1. Migre un blog existant vers un nouveau domaine
2. Lance un nouveau site avec du contenu pre-genere par l'IA
3. Fusionne plusieurs sites de contenu
4. Relance un site apres une longue pause

...a le meme besoin : **drip-publier** le contenu existant pour que les moteurs de recherche percoivent une activite editoriale naturelle.

### Ce qui existe deja dans ContentFlow

| Composant | Ce qu'il fait | Ce qui manque |
|-----------|--------------|---------------|
| **Scheduler** (`/api/scheduler`) | Jobs CRUD, calendar view, scheduling individuel | Pas d'orchestration batch, pas de strategie de cadence |
| **Publish** (`/api/publish`) | Publication vers plateformes sociales via Zernio | Pas de publication vers SSG, pas de rebuild trigger |
| **Deployment** (`/api/deployment`) | Pipeline SEO (research → content → deploy) | Cree du contenu, ne gere pas la liberation de contenu existant |
| **Topical Mesh** (`/api/mesh`) | Analyse cocons semantiques, autorite, clusters | Lecture seule — n'influence pas le calendrier de publication |
| **Internal Linking** (`/api/internal-linking`) | Analyse et insertion de liens internes | Pas de notion d'ordre de publication |
| **Calendar** (Flutter) | Vue calendrier des events content | Affiche, ne planifie pas de batch |

**Le trou :** aucun composant ne prend un batch de N articles et ne les repartit intelligemment dans le temps en respectant la structure thematique.

---

## Solution

Un nouveau module **Content Drip** qui orchestre la publication progressive.

### Flux principal

```
ENTREE                         TRAITEMENT                           SORTIE
═══════                        ══════════                           ══════

Batch de N articles    ──▶  1. Analyse des cocons semantiques  ──▶  Plan de publication
(fichiers MD, DB,           2. Ordonnancement intelligent           (dates assignees
 ou ContentRecords)         3. Cadence configurable                  par article)
                            4. Dry-run visualisable                      │
                                                                         ▼
                                                                  Execution
                                                                  ─────────
                                                                  5. Mise a jour pubDate
                                                                  6. Trigger rebuild SSG
                                                                  7. Soumission GSC
                                                                  8. Monitoring indexation
```

### Principes de design

1. **Generique** — fonctionne pour n'importe quel SSG (Astro, Next, Hugo, Jekyll, etc.)
2. **Declaratif** — l'utilisateur configure une strategie, le systeme l'execute
3. **Reversible** — on peut toujours modifier le plan avant ou pendant l'execution
4. **Observable** — dashboard temps reel de l'avancement (publie / indexe / en attente)
5. **Reentrant** — reprend proprement apres interruption (crash, pause manuelle)

---

## Architecture detaillee

### Modele de donnees

#### DripPlan

Le plan de publication. Un par batch.

```python
class DripPlan(BaseModel):
    id: str                          # UUID
    project_id: str                  # Projet ContentFlow
    user_id: str
    name: str                        # "GoCharbon Launch"
    status: DripPlanStatus           # draft | active | paused | completed | cancelled

    # Configuration
    cadence: CadenceConfig
    cluster_strategy: ClusterStrategy
    ssg_config: SSGConfig
    gsc_config: Optional[GSCConfig]

    # Contenu
    total_items: int
    items: list[DripItem]

    # Execution
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_drip_at: Optional[datetime]
    next_drip_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime


class DripPlanStatus(str, Enum):
    DRAFT = "draft"           # Plan cree, pas encore active
    ACTIVE = "active"         # En cours d'execution
    PAUSED = "paused"         # Mis en pause manuellement
    COMPLETED = "completed"   # Tous les items publies
    CANCELLED = "cancelled"   # Annule
```

#### CadenceConfig

Comment le contenu est distribue dans le temps.

```python
class CadenceConfig(BaseModel):
    mode: CadenceMode                # fixed | ramp_up | custom
    items_per_day: int = 3           # Pour mode fixed
    ramp_schedule: Optional[list[RampStep]]  # Pour mode ramp_up
    publish_days: list[int] = [0,1,2,3,4,5,6]  # 0=lundi, 6=dimanche
    publish_time: str = "06:00"      # Heure locale de publication
    timezone: str = "Europe/Paris"
    start_date: date                 # Premier jour de publication


class CadenceMode(str, Enum):
    FIXED = "fixed"          # N articles/jour, constant
    RAMP_UP = "ramp_up"      # Monte progressivement (1→3→5/jour)
    CUSTOM = "custom"        # Calendrier manuel par date


class RampStep(BaseModel):
    """Pour le mode ramp_up : monter progressivement la cadence."""
    from_day: int            # Jour relatif (0 = debut)
    items_per_day: int       # Cadence pour cette phase
    # Ex: [RampStep(0, 1), RampStep(7, 3), RampStep(21, 5)]
    # = 1/jour la 1ere semaine, 3/jour semaines 2-3, 5/jour ensuite
```

#### ClusterStrategy

Comment les articles sont groupes et ordonnes.

```python
class ClusterStrategy(BaseModel):
    mode: ClusterMode
    pillar_first: bool = True         # Publier le pilier avant les spokes
    cluster_gap_days: int = 0         # Jours d'attente entre deux clusters
    min_cluster_size: int = 3         # En dessous, regrouper les orphelins


class ClusterMode(str, Enum):
    AUTO = "auto"            # Detection automatique via Topical Mesh
    DIRECTORY = "directory"  # Utiliser l'arborescence de fichiers comme clusters
    TAGS = "tags"            # Utiliser les tags/categories du frontmatter
    MANUAL = "manual"        # L'utilisateur definit les groupes
    NONE = "none"            # Pas de clustering, ordre chronologique ou alphabetique
```

#### DripItem

Un article dans le plan.

```python
class DripItem(BaseModel):
    id: str                          # UUID
    drip_plan_id: str

    # Reference au contenu
    content_ref: str                 # Chemin fichier (SSG) ou content_record_id (DB)
    title: str

    # Clustering
    cluster_id: Optional[str]        # ID du cluster detecte
    cluster_name: Optional[str]      # "SEO Fondamentaux", "Copywriting", etc.
    is_pillar: bool = False          # Est-ce la page pilier du cluster ?

    # Scheduling
    scheduled_date: Optional[date]   # Date de publication assignee
    position: int                    # Ordre dans la sequence globale

    # Execution
    status: DripItemStatus           # pending | scheduled | published | indexed | error
    published_at: Optional[datetime]
    indexed_at: Optional[datetime]   # Date de confirmation d'indexation GSC
    error_message: Optional[str]


class DripItemStatus(str, Enum):
    PENDING = "pending"        # Pas encore programme
    SCHEDULED = "scheduled"    # Date assignee, en attente
    PUBLISHED = "published"    # pubDate mise a jour, rebuild declenche
    INDEXED = "indexed"        # Confirme indexe par Google
    SKIPPED = "skipped"        # Ignore (doublon, draft, etc.)
    ERROR = "error"            # Erreur lors de la publication
```

#### SSGConfig

Configuration specifique au generateur de site statique.

```python
class SSGConfig(BaseModel):
    framework: SSGFramework          # astro | next | hugo | jekyll | custom

    # Mecanisme de gating du contenu
    gating_method: GatingMethod

    # Rebuild
    rebuild_method: RebuildMethod
    rebuild_webhook_url: Optional[str]     # Pour Vercel/Netlify deploy hooks
    rebuild_github_repo: Optional[str]     # Pour GitHub Actions
    rebuild_github_branch: str = "main"

    # Acces fichiers (pour modifier pubDate/draft)
    content_directory: Optional[str]       # Ex: "src/data" pour Astro
    frontmatter_date_field: str = "pubDate"
    frontmatter_draft_field: str = "draft"


class SSGFramework(str, Enum):
    ASTRO = "astro"
    NEXT = "next"
    HUGO = "hugo"
    JEKYLL = "jekyll"
    ELEVENTY = "eleventy"
    CUSTOM = "custom"


class GatingMethod(str, Enum):
    """Comment le SSG filtre le contenu non publie."""
    FUTURE_DATE = "future_date"     # pubDate > now → exclu du build (Astro GoCharbon)
    DRAFT_FLAG = "draft_flag"       # draft: true → exclu du build
    BOTH = "both"                   # Les deux mecanismes combines
    CUSTOM = "custom"               # Script custom de l'utilisateur


class RebuildMethod(str, Enum):
    WEBHOOK = "webhook"             # POST vers un deploy hook (Vercel, Netlify, Cloudflare)
    GITHUB_ACTIONS = "github_actions"  # Trigger un workflow GitHub Actions
    MANUAL = "manual"               # L'utilisateur rebuild manuellement
    LOCAL_SCRIPT = "local_script"   # Executer un script local (dev/self-hosted)
```

#### GSCConfig (optionnel)

Integration Google Search Console pour la soumission d'URLs et le monitoring d'indexation.

```python
class GSCConfig(BaseModel):
    enabled: bool = False
    site_url: str                    # Ex: "https://gocharbon.com"
    credentials_method: GSCAuthMethod

    # Soumission
    submit_urls: bool = True         # Soumettre les URLs nouvellement publiees
    max_submissions_per_day: int = 200  # Limite API GSC

    # Monitoring
    check_indexation: bool = True    # Verifier l'indexation apres publication
    indexation_check_delay_hours: int = 48  # Attendre N heures avant de verifier


class GSCAuthMethod(str, Enum):
    SERVICE_ACCOUNT = "service_account"   # Google Service Account JSON
    OAUTH = "oauth"                       # OAuth2 (plus complexe)
```

---

### Detection automatique des cocons semantiques

C'est la partie IA de la feature. Objectif : prendre N articles et les regrouper en clusters thematiques pour les publier ensemble.

#### Sources de signal pour le clustering

```
SIGNAL                FIABILITE    METHODE
══════                ═════════    ═══════

1. Arborescence       ★★★★★       Structure des dossiers = structure semantique
   fichiers                       Ex: seo/contenu/*.md = un cluster

2. Tags/categories    ★★★★☆       Frontmatter tags, categories
   frontmatter                    Ex: tags: [SEO, Contenu]

3. Liens internes     ★★★★☆       Articles qui se lient entre eux
   existants                      = probablement meme cluster

4. Similarite         ★★★☆☆       Embedding cosine similarity des titres/contenus
   semantique                     Utile quand les autres signaux manquent

5. Topical Mesh       ★★★★★       Agent existant dans ContentFlow
   Architect                      Deja capable de detecter piliers + spokes
```

#### Algorithme de clustering

```
Etape 1 — Clustering primaire
    SI mode = DIRECTORY → utiliser l'arborescence (chaque dossier = cluster)
    SI mode = TAGS → grouper par tag principal (premier tag ou tag le plus specifique)
    SI mode = AUTO → combiner tous les signaux :
        a) Arborescence comme base
        b) Raffiner avec les tags
        c) Detecter les piliers via le Topical Mesh Architect
        d) Rattacher les orphelins par similarite semantique

Etape 2 — Identification des piliers
    Pour chaque cluster :
    - Le fichier index.md / page avec le plus de liens entrants = pilier
    - Sinon le fichier le plus long / le plus general (titre court, sujet large)

Etape 3 — Ordonnancement des clusters
    Priorite :
    1. Clusters "fondamentaux" d'abord (plus gros, plus de liens internes)
    2. Clusters de support ensuite
    3. Orphelins en dernier (articles isoles, pas dans un cocon)

Etape 4 — Ordonnancement intra-cluster
    1. Pilier en premier (si pillar_first = true)
    2. Spokes par pertinence decroissante ou par maillage logique
```

#### Integration avec le Topical Mesh Architect existant

Le Topical Mesh Architect (`/api/mesh/analyze`) sait deja :
- Detecter les pages piliers
- Identifier les clusters et leur densite de liens
- Trouver les pages orphelines
- Calculer un score d'autorite

On l'appelle **une seule fois** au debut de la planification pour obtenir la carte des clusters. Le Content Drip ne refait pas ce travail — il consomme le resultat du Mesh Architect.

```
                ┌──────────────────┐
                │  Topical Mesh    │
                │  Architect       │
                │  (existant)      │
                └────────┬─────────┘
                         │ clusters, piliers, orphelins
                         ▼
                ┌──────────────────┐
                │  Content Drip    │
                │  Planner         │ ◄── CadenceConfig + ClusterStrategy
                │  (nouveau)       │
                └────────┬─────────┘
                         │ DripPlan avec dates
                         ▼
                ┌──────────────────┐
                │  Drip Executor   │
                │  (nouveau)       │ ──▶ modifier pubDate/draft
                │                  │ ──▶ trigger rebuild
                └────────┬─────────┘ ──▶ soumettre GSC
                         │
                         ▼
                ┌──────────────────┐
                │  Calendar View   │
                │  (existant,      │
                │   enrichi)       │
                └──────────────────┘
```

---

### API Endpoints

#### Drip Plans CRUD

```
POST   /api/drip/plans                    Creer un plan de drip
GET    /api/drip/plans                    Lister les plans
GET    /api/drip/plans/{plan_id}          Detail d'un plan
PATCH  /api/drip/plans/{plan_id}          Modifier un plan (cadence, strategie)
DELETE /api/drip/plans/{plan_id}          Supprimer un plan
```

#### Drip Planning (analyse + scheduling)

```
POST   /api/drip/plans/{plan_id}/analyze    Lancer l'analyse des clusters
                                            (appelle Topical Mesh Architect)

POST   /api/drip/plans/{plan_id}/schedule   Generer le calendrier de publication
                                            (assigner les dates selon cadence + clusters)

GET    /api/drip/plans/{plan_id}/preview    Dry-run : voir le calendrier sans l'appliquer
                                            Retourne la liste des items avec dates

POST   /api/drip/plans/{plan_id}/approve    Valider et activer le plan
```

#### Drip Execution

```
POST   /api/drip/plans/{plan_id}/start      Demarrer l'execution
POST   /api/drip/plans/{plan_id}/pause      Mettre en pause
POST   /api/drip/plans/{plan_id}/resume     Reprendre
POST   /api/drip/plans/{plan_id}/cancel     Annuler

GET    /api/drip/plans/{plan_id}/status     Statut temps reel
                                            (items publies / en attente / indexes)
```

#### Drip Items

```
GET    /api/drip/plans/{plan_id}/items              Lister les items du plan
PATCH  /api/drip/plans/{plan_id}/items/{item_id}    Modifier un item (changer date, skip)
POST   /api/drip/plans/{plan_id}/items/{item_id}/publish-now   Forcer la publication immediate
```

#### GSC Integration

```
POST   /api/drip/gsc/submit-urls          Soumettre des URLs a Google
GET    /api/drip/gsc/indexation-status     Verifier le statut d'indexation
```

---

### Execution : comment le drip fonctionne au quotidien

#### Cron job principal

Un job cron tourne **toutes les heures** (configurable) et execute :

```python
async def drip_cron_tick():
    """Execute toutes les heures. Publie les items dont la date est arrivee."""

    plans = get_active_drip_plans()

    for plan in plans:
        now = datetime.now(tz=plan.cadence.timezone)
        today = now.date()

        # 1. Trouver les items a publier aujourd'hui
        items_due = [
            item for item in plan.items
            if item.scheduled_date <= today
            and item.status == DripItemStatus.SCHEDULED
        ]

        if not items_due:
            continue

        # 2. Publier chaque item
        for item in items_due:
            await publish_drip_item(plan, item)

        # 3. Trigger un rebuild SSG (un seul par batch quotidien)
        await trigger_ssg_rebuild(plan.ssg_config)

        # 4. Soumettre les URLs a GSC (si configure)
        if plan.gsc_config and plan.gsc_config.submit_urls:
            urls = [item_to_url(item) for item in items_due]
            await submit_to_gsc(plan.gsc_config, urls)

        # 5. Mettre a jour le plan
        plan.last_drip_at = now
        plan.next_drip_at = compute_next_drip(plan)

        if all(i.status != DripItemStatus.SCHEDULED for i in plan.items):
            plan.status = DripPlanStatus.COMPLETED
```

#### Publication d'un item (SSG)

```python
async def publish_drip_item(plan: DripPlan, item: DripItem):
    """Publie un item en modifiant le frontmatter du fichier source."""

    match plan.ssg_config.gating_method:

        case GatingMethod.FUTURE_DATE:
            # Mettre la pubDate a aujourd'hui (etait dans le futur)
            update_frontmatter(
                item.content_ref,
                {plan.ssg_config.frontmatter_date_field: date.today().isoformat()}
            )

        case GatingMethod.DRAFT_FLAG:
            # Passer draft de true a false
            update_frontmatter(
                item.content_ref,
                {plan.ssg_config.frontmatter_draft_field: False}
            )

        case GatingMethod.BOTH:
            update_frontmatter(
                item.content_ref,
                {
                    plan.ssg_config.frontmatter_date_field: date.today().isoformat(),
                    plan.ssg_config.frontmatter_draft_field: False,
                }
            )

    item.status = DripItemStatus.PUBLISHED
    item.published_at = datetime.now()
```

#### Trigger rebuild SSG

```python
async def trigger_ssg_rebuild(config: SSGConfig):
    """Declenche un rebuild du site statique."""

    match config.rebuild_method:

        case RebuildMethod.WEBHOOK:
            # Vercel / Netlify / Cloudflare deploy hook
            async with httpx.AsyncClient() as client:
                await client.post(config.rebuild_webhook_url)

        case RebuildMethod.GITHUB_ACTIONS:
            # Trigger un workflow via GitHub API
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.github.com/repos/{config.rebuild_github_repo}"
                    f"/actions/workflows/daily-drip.yml/dispatches",
                    headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
                    json={"ref": config.rebuild_github_branch}
                )

        case RebuildMethod.MANUAL:
            # Notifier l'utilisateur qu'un rebuild est necessaire
            notify_user("Drip: articles publies, rebuild necessaire")

        case RebuildMethod.LOCAL_SCRIPT:
            # Executer un script local
            subprocess.run(config.local_rebuild_command, shell=True)
```

---

### Flutter UI

#### Nouveau ecran "Content Drip"

Ajouter un ecran dans la navigation scrollable, section "Content" :

```
┌─────────────────────────────────────────────────────┐
│  Content Drip                              + New    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  GoCharbon Launch              ● Active       │  │
│  │  290 articles · 3/jour · Clusters auto        │  │
│  │  ████████████████░░░░░░  187/290 (64%)        │  │
│  │  Prochain drip: demain 06:00                  │  │
│  │  Derniere indexation: 12 articles confirmes   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Blog Perso Migration          ○ Draft        │  │
│  │  45 articles · 1/jour · Par dossiers          │  │
│  │  Preview disponible                           │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### Detail d'un plan

```
┌─────────────────────────────────────────────────────┐
│  ← GoCharbon Launch                    ⏸ Pause     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Progression    187/290 articles publies             │
│  ████████████████░░░░░░░░░░  64%                    │
│                                                     │
│  Indexation     142/187 confirmes par GSC            │
│  ████████████████████░░░░░░  76%                    │
│                                                     │
├─── Clusters ────────────────────────────────────────┤
│                                                     │
│  ✅ SEO Fondamentaux (12/12)        Tout indexe     │
│  ✅ Copywriting (14/14)             13/14 indexes   │
│  🔄 Marketing Outils (8/23)        En cours        │
│  ⏳ Business Admin (0/18)           A venir         │
│  ⏳ Tech Hebergement (0/15)         A venir         │
│  ...                                                │
│                                                     │
├─── Aujourd'hui ─────────────────────────────────────┤
│                                                     │
│  09:00  ✅ "Les meilleurs CRM gratuits"             │
│  09:00  ✅ "Jobphoning : avis et test"              │
│  09:00  ✅ "Cold email : la methode"                │
│                                                     │
├─── Demain ──────────────────────────────────────────┤
│                                                     │
│  06:00  ⏳ "Kaspr : test complet"                   │
│  06:00  ⏳ "Pharow : avis honnete"                  │
│  06:00  ⏳ "Emelia : prospection email"             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### Creation d'un plan (wizard)

```
Step 1/4 — Source du contenu
┌─────────────────────────────────────────┐
│  ○ Dossier de fichiers Markdown         │
│    Chemin: [src/data/________________]  │
│                                         │
│  ○ ContentRecords existants             │
│    Projet: [dropdown_______________]    │
│                                         │
│  ○ Sitemap XML                          │
│    URL: [https://___________________]   │
└─────────────────────────────────────────┘

Step 2/4 — Cadence
┌─────────────────────────────────────────┐
│  Articles par jour:                     │
│                                         │
│  [1]  [3]  [5]  [10]  [custom]          │
│         ▲                               │
│    Recommande pour ~290 articles        │
│    → Publication en ~97 jours           │
│                                         │
│  ○ Cadence fixe (3/jour constant)       │
│  ○ Montee progressive (1→3→5/jour)      │
│  ○ Calendrier custom                    │
│                                         │
│  Jours de publication:                  │
│  [x]L [x]M [x]M [x]J [x]V [ ]S [ ]D   │
│                                         │
│  Heure: [06:00]  Fuseau: [Europe/Paris] │
│  Date de debut: [2026-04-07]            │
└─────────────────────────────────────────┘

Step 3/4 — Clustering
┌─────────────────────────────────────────┐
│  Strategie de regroupement:             │
│                                         │
│  ● Auto (IA detecte les cocons)         │
│  ○ Par dossiers                         │
│  ○ Par tags                             │
│  ○ Manuel                               │
│  ○ Aucun (ordre alphabetique)           │
│                                         │
│  [x] Publier le pilier avant les spokes │
│  Jours entre clusters: [0]              │
└─────────────────────────────────────────┘

Step 4/4 — Deploiement
┌─────────────────────────────────────────┐
│  Framework SSG:                         │
│  [Astro ▼]                              │
│                                         │
│  Methode de gating:                     │
│  ● pubDate dans le futur (recommande)   │
│  ○ Flag draft: true                     │
│  ○ Les deux                             │
│                                         │
│  Rebuild automatique:                   │
│  ○ Webhook (Vercel/Netlify)             │
│    URL: [______________________________]│
│  ● GitHub Actions                       │
│    Repo: [owner/repo________________]   │
│                                         │
│  Google Search Console:                 │
│  [x] Soumettre les URLs apres rebuild   │
│  [x] Monitorer l'indexation             │
│  Credentials: [Uploader JSON___________]│
└─────────────────────────────────────────┘
```

---

### Cas d'usage GoCharbon (premier utilisateur)

Configuration concrete pour le lancement GoCharbon :

```python
gocharbon_plan = DripPlan(
    name="GoCharbon Launch",
    cadence=CadenceConfig(
        mode=CadenceMode.RAMP_UP,
        ramp_schedule=[
            RampStep(from_day=0, items_per_day=1),    # Semaine 1: 1/jour
            RampStep(from_day=7, items_per_day=3),    # Semaines 2-3: 3/jour
            RampStep(from_day=21, items_per_day=5),   # Ensuite: 5/jour
        ],
        publish_days=[0, 1, 2, 3, 4],  # Lundi-vendredi
        publish_time="06:00",
        timezone="Europe/Paris",
        start_date=date(2026, 4, 7),
    ),
    cluster_strategy=ClusterStrategy(
        mode=ClusterMode.DIRECTORY,     # src/data/ est deja bien structure
        pillar_first=True,
        cluster_gap_days=0,
    ),
    ssg_config=SSGConfig(
        framework=SSGFramework.ASTRO,
        gating_method=GatingMethod.FUTURE_DATE,  # filterBuildVisiblePosts() existe deja
        rebuild_method=RebuildMethod.GITHUB_ACTIONS,
        rebuild_github_repo="diane/gocharbon",
        content_directory="src/data",
        frontmatter_date_field="pubDate",
    ),
    gsc_config=GSCConfig(
        enabled=True,
        site_url="https://gocharbon.com",
        credentials_method=GSCAuthMethod.SERVICE_ACCOUNT,
        submit_urls=True,
        check_indexation=True,
    ),
)
```

Ordre de publication resultant :

```
Semaine 1 (1/jour, lun-ven) — Pages fondatrices
  J1:  seo/index.md (pilier SEO)
  J2:  seo/fondamentaux/fonctionnement-moteurs.md
  J3:  seo/fondamentaux/bonnes-pratiques.md
  J4:  strategies/acquisition.md
  J5:  strategies/content-marketing.md

Semaine 2 (3/jour) — Cocon SEO Contenu
  J8:  seo/contenu/strategie.md (pilier)
  J8:  seo/contenu/redaction-web.md
  J8:  seo/contenu/champ-semantique.md
  J9:  seo/contenu/cocon-semantique.md
  J9:  seo/contenu/eat-ymyl.md
  J9:  seo/netlinking/strategie.md
  ...

Semaine 4+ (5/jour) — Fiches outils par categorie
  J22: outils/marketing/prospection/kaspr.md
  J22: outils/marketing/prospection/pharow.md
  J22: outils/marketing/prospection/emelia.md
  J22: outils/marketing/prospection/la-growth-machine.md
  J22: outils/marketing/prospection/leadin.md
  ...
```

---

## Implementation plan

### Phase 1 — MVP Backend (Lab) ✅ DONE (2026-04-06)

| Tache | Status |
|-------|--------|
| Modeles Pydantic — 13 enums + 8 modeles (`api/models/drip.py`) | ✅ |
| Store SQLite — table `drip_plans` + DripService CRUD (`api/services/drip_service.py`) | ✅ |
| Router `/api/drip/` — 15 endpoints plans CRUD + import + cluster + schedule + lifecycle + execute (`api/routers/drip.py`) | ✅ |
| `SourceRobot.DRIP` ajoute a `publishing_schemas.py` | ✅ |
| Frontmatter parser/writer (`api/services/frontmatter.py`) | ✅ |
| Clustering par dossiers (mode DIRECTORY) avec detection piliers | ✅ |
| Scheduling fixe + ramp_up avec skip weekends | ✅ |
| Preview endpoint (dry-run sans ecriture) | ✅ |
| Cron tick executor (pubDate/draft update + lifecycle transitions) | ✅ |
| Rebuild trigger webhook + GitHub Actions (`api/services/rebuild_trigger.py`) | ✅ |
| Plan lifecycle : activate / pause / resume / cancel | ✅ |

**Decision d'integration cle :** les items du drip sont des `ContentRecord` existants avec `source_robot='drip'` et `metadata.drip_plan_id`. Pas de nouveau modele DripItem — tout reutilise le systeme existant (calendar, stats, audit trail).

### Phase 1b — Clustering avance ✅ DONE (2026-04-06)

| Tache | Status |
|-------|--------|
| `cluster_by_tags()` — grouper par tag primaire, pilier = item avec le plus de tags | ✅ |
| `cluster_auto()` — integration ExistingMeshAnalyzer avec fallback gracieux si crewai absent | ✅ |
| Endpoint `/cluster` unifie avec parametre `mode` (directory/tags/auto) | ✅ |

### Phase 1c — GSC Integration ✅ DONE (2026-04-06)

| Tache | Status |
|-------|--------|
| `GSCClient` — Google Indexing API (submit URL_UPDATED) + URL Inspection API (check indexation) | ✅ |
| Batch submit avec respect du quota (200/jour par defaut) | ✅ |
| Endpoints `/gsc/submit-urls` et `/gsc/indexation-status` | ✅ |
| Auto-submit dans `execute-tick` quand GSC est configure | ✅ |
| Fallback gracieux si google-auth/google-api-python-client non installe | ✅ |

### Phase 2 — Flutter UI

| Tache | Effort | Dependance |
|-------|--------|------------|
| Ecran liste des plans (avec progression) | M | API CRUD |
| Wizard creation (4 steps) | L | API CRUD |
| Detail plan (clusters + timeline) | M | API preview |
| Actions (start/pause/resume/cancel) | S | API execution |

### Phase 3 — Intelligence

| Tache | Effort | Dependance |
|-------|--------|------------|
| Clustering AUTO (integration Topical Mesh) | L | Mesh Architect |
| Clustering par TAGS (lecture frontmatter) | M | — |
| Detection automatique des piliers | M | Clustering AUTO |
| Mode RAMP_UP (cadence progressive) | S | Scheduling |

### Phase 4 — GSC Integration

| Tache | Effort | Dependance |
|-------|--------|------------|
| Google Search Console OAuth/Service Account | M | — |
| Soumission URLs (Indexing API) | M | Auth GSC |
| Monitoring indexation (URL Inspection API) | M | Auth GSC |
| Dashboard indexation dans Flutter | M | Monitoring |

### Phase 5 — Polish

| Tache | Effort | Dependance |
|-------|--------|------------|
| Notifications (drip quotidien, erreurs, milestones) | S | — |
| Export calendrier (iCal, CSV) | S | Preview |
| Statistiques (vitesse d'indexation, taux succes) | M | GSC |
| Multi-plan (plusieurs drips en parallele) | S | — |

---

## Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Google rate-limit sur l'Indexing API (200/jour) | Moyen | Respecter la limite, repartir les soumissions |
| Rebuild SSG echoue silencieusement | Haut | Verifier le deploy status apres webhook, alerter si echec |
| Frontmatter mal parse (format de date, encoding) | Moyen | Parser robuste avec fallback, dry-run obligatoire avant start |
| Plan interrompu (crash serveur, redemarrage) | Moyen | Reentrance : le cron reprend ou il en etait grace au status par item |
| Clustering AUTO produit des groupes incoherents | Moyen | Preview + approbation manuelle avant activation |
| Modification manuelle de fichiers pendant un drip actif | Moyen | Verifier le hash du fichier avant modification, alerter si conflit |

---

## Questions ouvertes

1. **Acces aux fichiers source** — ContentFlow Lab tourne sur un serveur. Comment accede-t-il aux fichiers Markdown du repo GoCharbon ? Options : git clone du repo, API GitHub pour modifier les fichiers, ou agent local sur la machine de build.

2. **Multi-repo** — Si l'utilisateur a plusieurs sites (GoCharbon, blog perso, site client), chaque plan pointe vers un repo different. Faut-il un systeme de "connected repos" ?

3. **Rollback** — Si on veut retirer un article deja publie (erreur, contenu sensible), faut-il un mecanisme de "un-drip" qui remet le draft flag ?

4. **Bing/Yandex** — Faut-il supporter la soumission a d'autres moteurs que Google des le debut ?

5. **Analytics post-publication** — Faut-il integrer Google Analytics / PostHog pour tracker la performance de chaque article publie par le drip ?

---

## Decision log

| Date | Decision | Raison |
|------|----------|--------|
| 2026-04-06 | Le Content Drip est un module ContentFlow, pas un outil standalone | Reutilisable pour tous les projets, s'integre au scheduler et au mesh existants |
| 2026-04-06 | Clustering par DIRECTORY comme MVP, AUTO en Phase 3 | GoCharbon a deja une arborescence bien structuree, pas besoin d'IA pour le premier usage |
| 2026-04-06 | pubDate future comme methode de gating par defaut | GoCharbon a deja `filterBuildVisiblePosts()` — zero code a ecrire cote SSG |
| 2026-04-06 | Cron horaire (pas quotidien) | Permet de publier a une heure precise, pas juste "dans la journee" |
| 2026-04-06 | GSC en Phase 4, pas MVP | Fonctionnel sans GSC (Google crawle le sitemap), GSC accelere mais n'est pas bloquant |
| 2026-04-06 | DripItems = ContentRecords avec source_robot='drip' | Reutilise calendar, stats, audit trail, lifecycle existants. Zero nouvelle table pour les items. |
| 2026-04-06 | Phase 1 complete en une session | 6 fichiers crees, 3 modifies. 17 endpoints API. Pipeline teste end-to-end (import → cluster → schedule → activate → execute → frontmatter updated). |
| 2026-04-06 | Clustering avance : tags + auto avec fallback | cluster_by_tags utilise le premier tag comme cluster key. cluster_auto appelle ExistingMeshAnalyzer si disponible, sinon fallback directory. |
| 2026-04-06 | GSC integre dans execute-tick | Auto-submit des URLs publiees si GSC configure. Fallback gracieux si google libs absentes. |

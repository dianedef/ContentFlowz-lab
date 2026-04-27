---
artifact: content_map
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-26"
updated: "2026-04-26"
status: draft
scope: content_map
source_skill: sf-docs
owner: "Diane"
confidence: low
risk_level: medium
security_impact: unknown
docs_impact: yes
evidence:
  - README.md
  - CLAUDE.md
  - specs/DRIP_IMPLEMENTATION.md
  - specs/ANALYSIS-drip-integration-with-existing.md
  - specs/SPEC-backend-persona-autofill-repo-understanding-user-keys.md
  - specs/social-listener.md
  - api/routers/*.py
  - agents/
  - tests/
depends_on:
  - BUSINESS.md@0.1.0
  - BRANDING.md@0.1.0
  - GUIDELINES.md@0.1.0
supersedes: []
content_surfaces:
  - api_endpoints
  - agent_modules
  - status_and_scheduler
  - docs_and_specs
  - integration_points
next_review: "2026-07-26"
next_step: /sf-docs audit CONTENT_MAP.md
---

# CONTENT_MAP.md

## Contexte global

Ce document mappe les surfaces de contenu/contrat de `contentflow_lab` utiles aux équipes produit, docs et opérations.

## 1. Points d’entrée de documentation

- `README.md` — vue produit + démarrage.
- `CLAUDE.md` — conventions de travail et limites opérationnelles.
- `BUSINESS.md`, `BRANDING.md`, `GUIDELINES.md` — contrats décisionnels.
- `docs` technique manquant (non présent dans ce repo).
- `specs/*.md` — spécifications d’implémentation et d’évolution.
- `tests/README.md` — stratégie de validation.

## 2. Surface API (FastAPI)

### Endpoints racine

- `GET /health`, `GET /version`, `GET /` (monitoring, sans préfixe `/api`).

### Routers publics (`/api`)

- Auth / webhook : `api/routers/auth_web.py`, `api/routers/integrations.py`
- Compte utilisateur / settings : `api/routers/me.py`, `api/routers/settings.py`, `api/routers/settings_integrations.py`
- Projet / contenu métier : `api/routers/projects.py`, `api/routers/content.py`, `api/routers/work_domains.py`, `api/routers/creator_profile.py`, `api/routers/personas.py`
- Idées / veille : `api/routers/idea_pool.py`
- Pipeline IA / generation : `api/routers/mesh.py`, `api/routers/research.py`, `api/routers/psychology.py`, `api/routers/newsletter.py`, `api/routers/deployment.py`
- Publication / distribution : `api/routers/publish.py`, `api/routers/reels.py`
- Statut / scheduler / jobs : `api/routers/status.py`, `api/routers/scheduler.py`, `api/routers/runs.py`, `api/routers/drip.py`
- Observabilité : `api/routers/activity.py`, `api/routers/analytics.py`, `api/routers/feedback.py`, `api/routers/health.py`

### Router public alternatif

- `/a/*` exposé via `api/routers/analytics.py` (router `analytics_public_router`) pour surfaces externes.

## 3. Surfaces d’agents et logique métier

### Domaines principaux

- `agents/seo/` : topical mesh, stratégie SEO, analyse de contenu.
- `agents/psychology/` : génération/raffinement de personas, angles narratifs.
- `agents/newsletter/` : composition de newsletter.
- `agents/short/` : génération short.
- `agents/social/` : parcours réseau.
- `agents/reels/` : génération médias/flux courts.
- `agents/scheduler/` : planification et règles de calendrier.
- `agents/images/` : profils visuels et génération optimisée.
- `agents/sources/` : ingestion de signaux externes (par ex. social).

### Services applicatifs

- `api/services/*.py` centralise l’accès externe (LLM, auth runtime, statut, jobs, frontmatter, feedback, rebuild).
- `status/` gère le lifecycle content, calendrier, audit et files d’attente persistées.

## 4. Surfaces de test et preuve

- `tests/` (structure catégorisée) pour validation métier (psy, SEO, search, workflow, newsletter, job status).
- `tests/README.md` décrit les entrées de commande de validation.
- `test_runner.py` agit comme runner de session (unit / integration / agents / tools).

## 5. Entrées de build, scripts et déploiement

- Runtime : `main.py`, `run_seo_deployment.py`, `run_seo_tools.sh`.
- Déploiement : `render.yaml`, `ecosystem.config.cjs`, scripts de setup.
- Secrets/ops : configuration via `requirements.txt` + environnement (Doppler / variables), et scripts de synchronisation.

## 6. Relations inter-repo

- `contentflow_app` consomme ce backend pour la couche auth/projets/flux de contenu.
- `contentflow_site` peut consommer les points d’entrée de dashboard/auth/web.

## 7. Cartographie des documents à maintenir

- Chaque surface fonctionnelle ci-dessus doit être couverte par une documentation active (README/README partiel + specs + tests).
- Après changement de contrat API, la documentation d’usage et les specs associées doivent être mises à jour sans attendre.
- Si une surface devient obsolète, elle doit être marquée explicitement dans le changelog et/ou la specification de migration.

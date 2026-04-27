---
artifact: gtm
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-26"
updated: "2026-04-26"
status: draft
scope: gtm
source_skill: sf-docs
owner: "Diane"
confidence: low
risk_level: medium
security_impact: none
docs_impact: yes
evidence:
  - README.md
  - CLAUDE.md
  - BUSINESS.md
  - BRANDING.md
  - specs/SPEC-branding.md
  - specs/SPEC-workflow-visualization.md
  - specs/social-listener.md
depends_on:
  - BUSINESS.md@0.1.0
  - BRANDING.md@0.1.0
  - GUIDELINES.md@0.1.0
supersedes: []
next_review: "2026-07-26"
next_step: /sf-docs audit GTM.md
---

# GTM.md

## Positionnement commercial (backend observé)

`contentflow_lab` n’est pas un produit final consommé directement par les utilisateurs finaux. C’est un **moteur de services** qui rend disponibles :

- API stables pour l’application et les expériences web,
- orchestration asynchrone des workflows IA,
- planification et publication progressive,
- monitoring opérationnel des jobs et des statuts.

La promesse produit doit donc être formulée comme :

- « une couche API fiable qui supporte la production de contenu et la coordination des pipelines, avec des contrats contractés et observables ».

## Public prioritaire (hypothèse)

- Équipes qui pilotent du contenu automatisé et ont besoin d’un point d’entrée unique (applications mobiles, sites, scripts).
- Fondateurs/chefs de produit qui veulent conserver des flux éditoriaux reproductibles au lieu d’outils siloés.
- Organisations qui dépendent d’intégrations tierces (LMS, CMS statique, outils SEO, services de messagerie).

## Segmentation de message

### Message principal

- Mise en avant de la **fiabilité contractuelle** (routes, statuts, idempotence, migration sûre).
- Mise en avant de la **traçabilité** (jobs, statut, scheduler, health, tests).
- Transparence sur les limites techniques réelles (BYOK, dépendances externes, délais asynchrones).

### Canaux de preuve les plus crédibles

- API docs et OpenAPI (`/docs`, `/redoc`).
- Journaux de status (`/api/health`, `/api/health/{check}`).
- Contrats explicites dans `README.md`, `CLAUDE.md`, specs et logs métier.
- Cas d’usage prouvés par routes : personas, projets, idea pool, drip, planification, recherche.

## Offre de départ (version projet)

- Point d’entrée FastAPI pour toutes les opérations de contenu.
- Pipelines IA : recherche/veille, rédaction, planification, publication.
- Planification et rappel par scheduler.
- Contrôles utilisateur via app Flutter (`contentflow_app`) et surfaces web (`contentflow_site`).

## Objections & réponses

- **« Mon flux IA est trop opaque »** → Les jobs et statuts sont explicitement exposés, et les contrats route sont centralisés.
- **« Les intégrations cassent en production »** → Les tables critiques sont bootstrapées à l’init ; les préconditions d’exécution existent par routes et tests.
- **« Les coûts sont incontrôlés »** → Les specs de coût/observabilité existent et doivent être activés/monitorés via les flux pipeline et reporting.
- **« Le risque de régression API »** → Les interfaces sont versionnées par code/contrats existants et doivent être validées par les audits et tests.

## Preuves non disponibles à ce stade

- Pricing final et conditions commerciales formelles.
- KPI produit consolidés (taux de rétention, CAC/ARPU, coûts opérationnels consolidés).
- Feuille de route GTM officielle multi-canal.

## Révisions recommandées

- Mettre à jour ces pages quand un plan commercial, un segment prioritaire réel et une stratégie d’onboarding public sont validés.

---
artifact: spec
metadata_schema_version: "1.0"
artifact_version: "0.1.0"
project: contentflow_lab
created: "2026-04-25"
updated: "2026-04-25"
status: draft
source_skill: sf-docs
scope: feature
owner: unknown
confidence: low
risk_level: medium
security_impact: unknown
docs_impact: yes
user_story: "unknown (legacy spec migrated to ShipFlow metadata)"
linked_systems: []
depends_on: []
supersedes: []
evidence: []
next_step: "/sf-docs audit specs/SPEC-backend-persona-autofill-repo-understanding-user-keys.md"
---
# Backend persona autofill + repo understanding + user keys

## Problème

Le backend actuel permet de créer des personas, gérer un creator profile, connecter GitHub et lancer des agents `psychology`, mais il ne permet pas de générer de manière fiable un brouillon de persona à partir d’un projet.

Les causes principales sont :

- contrat persona non unifié entre app, API et agents
- endpoints `psychology` non authentifiés et jobs non persistés
- clés utilisateur prévues mais non utilisables
- analyse repo limitée à la structure technique, sans compréhension sémantique produit/audience

## Solution

Mettre en place une fondation backend unifiée pour `personas/creator/psychology`, ajouter un sous-domaine sécurisé de clés utilisateur `OpenRouter`, persister les jobs IA dans `jobs`, puis introduire un service `repo understanding` consommé par un nouveau flux asynchrone `POST /api/personas/draft` qui retourne un brouillon non persisté avec preuves et score de confiance.

## Décisions verrouillées

- Provider LLM V1 : `OpenRouter` uniquement
- Source primaire : projets GitHub
- Source secondaire V1 : `manual_url` via GitHub public ou crawl `Firecrawl`
- Le draft persona est toujours non persisté
- Le format canonique interne du domaine persona est `snake_case`
- `UserProviderCredential` devient la source de vérité pour les secrets utilisateur
- `job_store` devient la persistance unique des jobs IA `psychology` et `persona draft`

## Scope in

- normalisation des modèles persona/creator
- sécurisation et persistance des jobs `psychology`
- bootstrap DB des tables persona/creator
- stockage chiffré des clés utilisateur OpenRouter
- endpoints `/api/settings/integrations/*`
- service d’analyse sémantique repo/site
- brouillon persona asynchrone non persisté
- support source `project_repo`, `connected_github`, `manual_url`
- support `manual_url` GitHub public ou site public via Firecrawl

## Scope out

- refonte complète de l’UI Flutter
- auto-save du brouillon persona en base
- support user-managed keys pour Firecrawl/Exa/Groq en V1
- génération finale d’angles ou de contenu au-delà des adaptations de contrat nécessaires
- cache analytique longue durée séparé du `job_store`

## Contexte technique

### Stack

- Backend : `FastAPI`, `Pydantic v2`, `libsql/Turso`
- Agents : `CrewAI`
- LLM : `OpenAI SDK via OpenRouter`
- Crawl externe : `firecrawl-py`
- Tests : `pytest`, `pytest-asyncio`, `AsyncMock`

### Patterns à suivre

- Routers fins dans `api/routers/`
- Logique métier dans `api/services/`
- Tables idempotentes bootstrappées depuis `api.main`
- Contrats Pydantic dans `api/models/`
- Tests de router par import isolé + stubs/mocks

### Contrat canonique interne

```json
{
  "project_id": "optional",
  "name": "Solopreneur SaaS pragmatique",
  "avatar": "🛠️",
  "demographics": {
    "role": "Founder",
    "industry": "B2B SaaS",
    "age_range": "30-45",
    "experience_level": "5-10 years"
  },
  "pain_points": ["..."],
  "goals": ["..."],
  "language": {
    "vocabulary": ["..."],
    "objections": ["..."],
    "triggers": {
      "emotional": ["..."],
      "functional": ["..."]
    }
  },
  "content_preferences": {
    "formats": ["article", "newsletter"],
    "channels": ["blog", "linkedin"],
    "frequency": "weekly"
  },
  "confidence": 72
}
```

### Règles de compatibilité

- `api/models/user_data.py` accepte `painPoints` et `pain_points`
- `api/models/user_data.py` accepte `contentPreferences` et `content_preferences`
- `api/models/user_data.py` accepte `projectId` et `project_id`
- Tous les services et agents reçoivent uniquement le format normalisé `snake_case`
- Les endpoints CRUD legacy `personas` peuvent continuer à répondre en camelCase si nécessaire pour compat app, mais la normalisation doit être centralisée dans le backend

### Contrat job standard

Tout job persistant IA stocké dans `jobs` doit exposer :

```json
{
  "job_id": "uuid",
  "job_type": "psychology.generate_angles|psychology.refine_persona|psychology.synthesize_narrative|personas.draft",
  "status": "pending|running|completed|failed",
  "progress": 0,
  "message": "human-readable status",
  "user_id": "owner",
  "result": {},
  "error": null
}
```

### Contrat `POST /api/personas/draft`

```json
{
  "project_id": "optional-project-id",
  "repo_source": "project_repo|connected_github|manual_url",
  "repo_url": "required for connected_github and optional for manual_url",
  "manual_url": "optional non-github site url",
  "mode": "blank_form|suggest_from_repo|refresh_from_repo",
  "existing_creator_profile": {
    "display_name": "optional",
    "voice": {},
    "positioning": {},
    "values": []
  }
}
```

### Règles source

- `project_repo`
  - exige `project_id`
  - lit `Project.settings.local_repo_path`
- `connected_github`
  - exige `repo_url`
  - exige intégration GitHub valide pour l’utilisateur
  - lit le repo via token GitHub
- `manual_url`
  - si `repo_url` GitHub public fourni : lecture GitHub sans OAuth utilisateur
  - sinon exige `manual_url` et utilise Firecrawl

### Budget de crawl V1

- `manual_url` non-GitHub`
  - `map_site` puis sélection max `5` pages
  - priorité : homepage, about, pricing, docs start, blog index
  - fallback : homepage seule si le mapping échoue
- snippets `evidence.snippet` limités à `300` caractères

## Tâches d’implémentation

- [ ] Tâche 1 : Garantir les tables `CreatorProfile` et `CustomerPersona`
  - Fichier : `contentflow_lab/api/services/user_data_store.py`
  - Action : Ajouter `ensure_creator_profile_table()` et `ensure_customer_persona_table()`
  - Notes : schémas strictement alignés avec les méthodes CRUD existantes

- [ ] Tâche 2 : Garantir la table des credentials utilisateur
  - Fichier : `contentflow_lab/api/services/user_key_store.py`
  - Action : Créer `UserProviderCredential` et son `ensure_table()`
  - Notes : colonnes `userId`, `provider`, `encryptedSecret`, `maskedSecret`, `createdAt`, `updatedAt`, `lastValidatedAt`, `validationStatus`

- [ ] Tâche 3 : Brancher toutes les garanties de bootstrap
  - Fichier : `contentflow_lab/api/main.py`
  - Action : appeler `ensure_user_settings_table()`, `ensure_creator_profile_table()`, `ensure_customer_persona_table()`, `user_key_store.ensure_table()`, `job_store.ensure_table()`
  - Notes : ne pas dépendre d’une migration externe cachée

- [ ] Tâche 4 : Introduire le chiffrement applicatif
  - Fichier : `contentflow_lab/api/services/crypto.py`
  - Action : Ajouter un service Fernet basé sur `USER_SECRETS_MASTER_KEY`
  - Notes : lever une erreur explicite si la variable n’est pas configurée

- [ ] Tâche 5 : Déclarer OpenRouter comme seule intégration user key V1
  - Fichier : `contentflow_lab/api/models/user_data.py`
  - Action : Ne plus étendre le write-path à tout `apiKeys`; créer un modèle dédié `OpenRouterCredentialStatus`
  - Notes : `UserSettings.apiKeys` reste legacy/read-only et ne doit plus piloter le runtime

- [ ] Tâche 6 : Unifier le contrat persona/creator
  - Fichier : `contentflow_lab/api/models/user_data.py`
  - Action : Ajouter les alias `validation_alias/serialization_alias` nécessaires et une méthode de normalisation canonique
  - Notes : tous les services backend doivent travailler en `snake_case`

- [ ] Tâche 7 : Unifier les modèles `psychology`
  - Fichier : `contentflow_lab/api/models/psychology.py`
  - Action : faire dépendre `PersonaRefinementRequest` et `AngleGenerationRequest` de modèles normalisés
  - Notes : compat temporaire acceptée pour l’ancien payload `{"persona": ...}` sur `refine-persona`

- [ ] Tâche 8 : Sécuriser et migrer les jobs `psychology`
  - Fichier : `contentflow_lab/api/routers/psychology.py`
  - Action : ajouter auth obligatoire, remplacer `_tasks` par `job_store`, stocker `user_id`, uniformiser le format des réponses de job
  - Notes : polling restreint au propriétaire du job

- [ ] Tâche 9 : Exposer les endpoints d’intégration OpenRouter
  - Fichier : `contentflow_lab/api/routers/settings_integrations.py`
  - Action : ajouter `GET`, `PUT`, `DELETE`, `POST validate` pour OpenRouter
  - Notes : aucune clé en clair dans les réponses

- [ ] Tâche 10 : Créer le service runtime LLM utilisateur
  - Fichier : `contentflow_lab/api/services/user_llm_service.py`
  - Action : résoudre la clé OpenRouter depuis `UserProviderCredential`, construire le client OpenRouter, fournir une erreur métier si absent/invalide
  - Notes : pas de fallback env serveur pour `personas.draft`

- [ ] Tâche 11 : Créer le service `repo_understanding`
  - Fichier : `contentflow_lab/api/services/repo_understanding_service.py`
  - Action : résoudre la source, collecter le contenu, extraire `project_summary`, `target_audiences`, `icp_hypotheses`, `personal_story_signals`, `positioning_hypotheses`, `persona_candidates`, `evidence`
  - Notes : support local repo, GitHub connecté, GitHub public, site crawlé Firecrawl

- [ ] Tâche 12 : Définir les modèles draft persona
  - Fichier : `contentflow_lab/api/models/persona_draft.py`
  - Action : créer `PersonaDraftRequest`, `PersonaDraftJobResponse`, `PersonaDraftResult`, `RepoUnderstandingResult`, `EvidenceItem`
  - Notes : `persona_draft` toujours non persisté

- [ ] Tâche 13 : Ajouter les routes draft persona
  - Fichier : `contentflow_lab/api/routers/personas.py`
  - Action : ajouter `POST /api/personas/draft` et `GET /api/personas/draft-jobs/{job_id}`
  - Notes : chargement auto du `creator_profile` si non fourni

- [ ] Tâche 14 : Enregistrer les nouveaux routers
  - Fichier : `contentflow_lab/api/routers/__init__.py`
  - Action : exporter `settings_integrations_router`
  - Notes : garder le pattern centralisé

- [ ] Tâche 15 : Inclure le router dans l’app
  - Fichier : `contentflow_lab/api/main.py`
  - Action : `app.include_router(settings_integrations_router)`

- [ ] Tâche 16 : Couvrir la normalisation de contrat
  - Fichier : `contentflow_lab/tests/test_persona_contracts.py`
  - Action : tester alias input/output et normalisation finale

- [ ] Tâche 17 : Couvrir OpenRouter user keys
  - Fichier : `contentflow_lab/tests/test_settings_integrations_router.py`
  - Action : tester write/read/delete/validate et absence de fuite du secret

- [ ] Tâche 18 : Couvrir les jobs `psychology`
  - Fichier : `contentflow_lab/tests/test_psychology_auth_jobs.py`
  - Action : tester auth, persistance job, ownership, migration hors mémoire

- [ ] Tâche 19 : Couvrir le draft persona
  - Fichier : `contentflow_lab/tests/test_persona_draft_route.py`
  - Action : tester `project_repo`, `connected_github`, GitHub public, `manual_url` Firecrawl, absence de clé, mode `blank_form`

## Critères d’acceptation

- [ ] CA 1 : Given un environnement neuf avec Turso configuré, when l’API démarre, then `UserSettings`, `CreatorProfile`, `CustomerPersona`, `UserProviderCredential` et `jobs` existent sans migration manuelle.
- [ ] CA 2 : Given un payload persona en `camelCase`, when il est validé par l’API, then il est converti en format canonique `snake_case` avant stockage ou exécution agent.
- [ ] CA 3 : Given un payload persona en `snake_case`, when il traverse le même flow, then il produit exactement la même représentation interne que le payload `camelCase`.
- [ ] CA 4 : Given un appel non authentifié à un endpoint `psychology`, when il est reçu, then l’API répond `401`.
- [ ] CA 5 : Given un job `psychology` ou `personas.draft` appartenant à un utilisateur A, when un utilisateur B tente de le lire, then il n’obtient aucun résultat exploitable.
- [ ] CA 6 : Given une clé OpenRouter stockée, when elle est relue depuis l’API d’intégration, then seule la version masquée est exposée.
- [ ] CA 7 : Given une clé OpenRouter invalide, when `validate` est appelé, then `validation_status=invalid` et aucun secret en clair n’est renvoyé.
- [ ] CA 8 : Given un utilisateur sans clé OpenRouter valide, when il soumet un draft persona hors mode `blank_form`, then l’API répond `409`.
- [ ] CA 9 : Given `mode=blank_form`, when un draft persona est soumis, then l’API peut produire un brouillon sans analyse repo.
- [ ] CA 10 : Given `repo_source=project_repo` avec un `project_id` valide et `local_repo_path` présent, when le job tourne, then il analyse les fichiers prioritaires du repo local.
- [ ] CA 11 : Given `repo_source=connected_github` avec `repo_url` et intégration GitHub valide, when le job tourne, then il analyse le repo ciblé avec le token utilisateur.
- [ ] CA 12 : Given un `repo_url` GitHub public en source manuelle, when le job tourne, then il n’exige pas d’intégration GitHub connectée.
- [ ] CA 13 : Given une URL site publique non-GitHub, when le job tourne avec Firecrawl configuré, then il limite la collecte à 5 pages maximum et retourne des `evidence` traçables.
- [ ] CA 14 : Given un job draft terminé, when le résultat est lu, then il contient `persona_draft`, `repo_understanding`, `evidence`, `confidence`, et ne crée aucun `CustomerPersona` tant qu’un CRUD explicite n’est pas appelé.

## Dépendances

- Ajouter `cryptography>=42,<44` à `contentflow_lab/requirements.txt`
- Ajouter `USER_SECRETS_MASTER_KEY` à la doc d’environnement backend
- Réutiliser `firecrawl-py` existant pour les sites publics
- Réutiliser `job_store` existant comme persistance unique de job

## Stratégie de test

- Unit tests Pydantic pour alias et normalisation
- Unit tests store/service pour chiffrement, masquage et résolution de source
- Router tests FastAPI isolés avec `AsyncMock`
- Intégration mockée pour polling de jobs
- Test manuel minimal :
  1. connecter GitHub
  2. enregistrer une clé OpenRouter
  3. lancer `POST /api/personas/draft` avec `project_repo`
  4. poller jusqu’à `completed`
  5. vérifier que le draft n’apparaît pas dans `GET /api/personas` avant sauvegarde explicite

## Risques

- Migration contrat : casser l’app Flutter si la compat de lecture/écriture n’est pas testée
- Secrets : mauvaise rotation ou clé maître absente au runtime
- Coût crawl : Firecrawl trop large si la limite de pages n’est pas imposée en code
- Ambiguïté source : `connected_github` sans `repo_url`
- Dette legacy : laisser `UserSettings.apiKeys` actif en parallèle et créer une double source de vérité

## Fichiers à modifier/créer

- `contentflow_lab/api/main.py`
- `contentflow_lab/api/routers/__init__.py`
- `contentflow_lab/api/routers/psychology.py`
- `contentflow_lab/api/routers/personas.py`
- `contentflow_lab/api/models/user_data.py`
- `contentflow_lab/api/models/psychology.py`
- `contentflow_lab/api/services/user_data_store.py`
- `contentflow_lab/requirements.txt`
- `contentflow_lab/api/services/crypto.py`
- `contentflow_lab/api/services/user_key_store.py`
- `contentflow_lab/api/routers/settings_integrations.py`
- `contentflow_lab/api/services/user_llm_service.py`
- `contentflow_lab/api/services/repo_understanding_service.py`
- `contentflow_lab/api/models/persona_draft.py`
- `contentflow_lab/tests/test_persona_contracts.py`
- `contentflow_lab/tests/test_settings_integrations_router.py`
- `contentflow_lab/tests/test_persona_draft_route.py`
- `contentflow_lab/tests/test_psychology_auth_jobs.py`

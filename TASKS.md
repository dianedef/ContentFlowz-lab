# ContentFlowz Lab — Tasks

## Completed

| Task | Status |
|------|--------|
| Social Listener — multi-platform ingestion (Reddit, X, HN, YouTube) | Done |
| Content Quality Scoring — textstat integration + fix broken Flesch | Done |
| OG Preview service — OpenGraph extraction for link previews | Done |
| Social Listener spec — `specs/social-listener.md` | Done |
| Feature documentation on ContentFlowz site (3 pages + index update) | Done |

## In Progress

| Pri | Task | Status |
|-----|------|--------|
| P0 | P0.1 — Externalize agent prompts (role/goal/backstory/tasks) to YAML files | ✅ done |

### Audit: Code (2026-04-07)

| Sev | Issue | Location | Status |
|-----|-------|----------|--------|
| 🔴 | Command injection — f-string + shell=True in git/npm commands | `publishing_tools.py`, `tech_audit_tools.py` | **FIXED** |
| 🔴 | 12 API routers have NO authentication | 12 routers | **FIXED** |
| 🔴 | Global exception handler leaks `str(exc)` to clients | `api/main.py` | **FIXED** |
| 🔴 | shell=True with interpolated paths in tech audit tools | `tech_audit_tools.py` | **FIXED** |
| 🟠 | 7 bare `except:` clauses mask all errors | `repo_analyzer.py`, `seo_research_tools.py` | **FIXED** |
| 🟠 | Drip router hardcodes `user_id="system"` — no tenant isolation | `api/routers/drip.py` | **FIXED** |
| 🟠 | CORS regex allows any `*.vercel.app` subdomain | `api/main.py` | **FIXED** |
| 🟠 | In-memory state lost on restart (deployment, templates) | `api/routers/deployment.py`, `api/routers/templates.py` | Open |
| 🟠 | Loose dependency pins (`>=` with no upper bound) | `requirements.txt` | **FIXED** |
| 🟠 | God file: 3512 lines, 140 functions | `agents/seo/tools/internal_linking/` | **FIXED** |
| 🟡 | No CI/CD pipeline to run existing tests | Project-wide | Deferred — tests need API keys, no value until pure unit tests exist |
| 🟡 | Multiple 500+ line files (8 files over 500 lines) | `ingest.py`, `dataforseo_client.py`, `status/service.py`, etc. | Open |
| 🟡 | No structured logging for production | Project-wide | **FIXED** |
| 🟡 | No rate limiting on any endpoint | `api/main.py` | **FIXED** |
| 🟡 | No DB health check in health endpoint | `api/routers/health.py` | **FIXED** |
| 🟡 | In-memory state (deployment, templates routers) | `api/services/job_store.py` | **FIXED** |
| 🟡 | test_runner.py user input sanitization | `test_runner.py` | **FIXED** |

## Backlog

| Pri | Task | Notes |
|-----|------|-------|
| P2 | Social Listener v2 — TikTok, Instagram, Bluesky | Needs ScrapeCreators API key |
| P2 | Readability endpoint — `POST /api/content/{id}/readability` | Score existing content from calendar |
| P3 | OG Preview caching — avoid refetching same URLs | Simple dict or store-based cache |
| P3 | Unsplash API integration — stock photos for content | Nice-to-have complement to AI images |

---

## Architecture : Refonte Intelligence des Agents IA

### Contexte du diagnostic (2026-04-02)

Audit complet du code des agents dans `agents/`. Sur ~21 agents définis, environ la moitié n'utilisent jamais le LLM (Scheduler, Images). Ceux qui l'utilisent (SEO, Newsletter, Psychology, Social, Short) le font de manière rigide : pipeline linéaire, tools vides, zéro collaboration inter-agents. Le potentiel d'intelligence est là (CrewAI, Mem0, DataForSEO sont installés) mais sous-exploité.

- **Score d'intelligence actuel estimé :** 3/10
- **Score cible :** 8/10

---

### P0 — Court terme (quick wins, pas de refactoring majeur)

#### P0.1 — Externaliser les prompts dans des fichiers YAML

- [ ] **Créer le dossier `agents/{robot}/prompts/` pour chaque robot**

**Problème :** Tous les prompts (role, goal, backstory, `Task.description`) sont des f-strings hardcodées dans le code Python. Impossible de modifier un prompt sans toucher au code. Pas de versioning, pas d'A/B testing, pas de feedback loop.

**Solution détaillée :**

1. Créer un dossier `agents/{robot}/prompts/` pour chaque robot ayant des agents CrewAI
2. Créer un fichier YAML par agent à l'intérieur, nommé d'après l'agent : `research_analyst.yaml`, `strategy_expert.yaml`, etc.
3. Structure YAML attendue :
   ```yaml
   role: "SEO Research Analyst"
   goal: "Conduct comprehensive competitive intelligence..."
   backstory: "You are an expert SEO analyst with 10+ years..."
   tasks:
     research:
       description: "Analyze the competitive landscape for {topic}..."
       expected_output: "A structured research report with..."
   ```
4. Les variables dynamiques (`{topic}`, `{brand}`, `{url}`) restent en placeholder dans le YAML — elles seront injectées au runtime via `.format()` ou `str.format_map()`
5. Créer un helper `load_prompt(robot, agent_name)` dans `agents/shared/prompt_loader.py` qui :
   - Charge le fichier YAML correspondant
   - Retourne un dict avec `role`, `goal`, `backstory`, `tasks`
   - Gère les erreurs (fichier manquant, clé manquante) avec des messages explicites

**Fichiers à modifier :**
- [ ] `agents/seo/seo_crew.py` — extraire les 6 agents + leurs tasks vers YAML
- [ ] `agents/newsletter/newsletter_crew.py` — extraire les 2 agents vers YAML
- [ ] `agents/psychology/psychology_crew.py` — extraire les 3 agents vers YAML
- [ ] `agents/social/social_crew.py` — extraire l'agent vers YAML
- [ ] `agents/short/short_crew.py` — extraire l'agent vers YAML
- [ ] Créer `agents/shared/prompt_loader.py` — helper de chargement YAML

**Bénéfice :** Itération rapide sur les prompts sans risquer de casser le code Python. Versioning Git des prompts séparément du code. Possibilité future d'A/B testing de prompts.

---

#### P0.2 — Assumer les faux agents comme pipelines Python ✅

- [x] **Nettoyer la confusion sémantique agents/pipelines**

**Problème :** Les agents Scheduler (`agents/scheduler/scheduler_crew.py`) et Images (`agents/images/image_robot_crew.py`) instancient des objets `Agent()` CrewAI avec `role`/`goal`/`backstory` mais ne font JAMAIS `crew.kickoff()`. Ce sont des scripts Python classiques déguisés en "agents IA". Les méthodes sont appelées directement :
```python
schedule_result = self.calendar_manager.schedule_content(content_data)
publish_result = self.publishing_agent.publish_content(content_path, ...)
```

**Solution détaillée :**

1. Retirer les objets `Agent()` CrewAI inutilisés de ces fichiers — supprimer les imports CrewAI (`from crewai import Agent, Task, Crew`) et les instanciations `Agent(role=..., goal=..., backstory=...)`
2. Renommer les classes pour refléter leur vraie nature :
   - `SchedulerCrew` → `SchedulerPipeline`
   - `ImageRobotCrew` → `ImagePipeline`
3. Mettre à jour tous les imports dans les routers FastAPI qui référencent ces classes (chercher `from agents.scheduler.scheduler_crew import` et `from agents.images.image_robot_crew import`)
4. Documenter clairement dans un commentaire en tête de fichier que ces modules sont des **pipelines déterministes**, pas des agents IA
5. **NE PAS changer la logique métier** — uniquement nettoyer la confusion sémantique

**Fichiers à modifier :**
- [ ] `agents/scheduler/scheduler_crew.py` — retirer Agent/Crew, renommer classe
- [ ] `agents/scheduler/agents/` (4 fichiers d'agents) — retirer les instanciations Agent() inutilisées
- [ ] `agents/images/image_robot_crew.py` — retirer Agent/Crew, renommer classe
- [ ] `agents/images/agents/` (4 fichiers d'agents) — retirer les instanciations Agent() inutilisées
- [ ] Les routers FastAPI qui importent ces classes — mettre à jour les imports

**Bénéfice :** Clarté architecturale. On sait immédiatement ce qui est "intelligent" (utilise le LLM) et ce qui est déterministe (pipeline Python classique).

---

#### P0.3 — Supprimer ou enrichir les tools coquilles vides ✅

- [x] **Auditer et corriger chaque tool factice du robot SEO**

**Problème :** Les tools des agents SEO renvoient des données statiques ou des templates hardcodés au lieu d'utiliser le LLM ou des APIs réelles :

| Tool | Fichier | Problème |
|------|---------|----------|
| `ContentWriter.write_content()` | `agents/seo/tools/writing_tools.py` | Renvoie un dict de "guidelines" sans générer de contenu |
| `ToneAdapter.adapt_tone()` | `agents/seo/tools/writing_tools.py` | Renvoie des templates pré-définis (professional, casual) |
| `KeywordIntegrator.integrate_keywords()` | `agents/seo/tools/writing_tools.py` | Fait du regex basique (`re.findall`) |
| `MetadataGenerator.generate_metadata()` | `agents/seo/tools/writing_tools.py` | Concatène des strings avec des templates |
| `TopicClusterBuilder.build_topic_cluster()` | `agents/seo/tools/strategy_tools.py` | Contient des branches `if "marketing" in pillar_topic.lower()` hardcodées |

**Solution — 2 options par tool :**
- **Option A : Supprimer le tool** → laisser le LLM raisonner seul (il est meilleur que du regex pour l'analyse de mots-clés ou la génération de contenu)
- **Option B : Connecter à une vraie API** → les tools DataForSEO existent et sont bien intégrés dans `agents/seo/tools/`, les étendre aux tools de writing/strategy

**Recommandation par tool :**
- [ ] `ContentWriter` → **Option A (supprimer)** — le LLM avec le bon prompt génère du contenu bien meilleur qu'un dict de guidelines
- [ ] `ToneAdapter` → **Option A (supprimer)** — le LLM adapte le ton naturellement via le prompt
- [ ] `MetadataGenerator` → **Option A (supprimer)** — le LLM génère des meta descriptions et titles de meilleure qualité
- [ ] `KeywordIntegrator` → **Option B (connecter à DataForSEO)** — le connecter aux données de volume de recherche et difficulté de mots-clés réelles via les tools DataForSEO déjà existants
- [ ] `TopicClusterBuilder` → **Option A (supprimer)** — le LLM avec le bon prompt fait des topic clusters bien meilleurs que des branches `if/else` hardcodées

**Fichiers à modifier :**
- [ ] `agents/seo/tools/writing_tools.py` — supprimer ContentWriter, ToneAdapter, MetadataGenerator ; enrichir KeywordIntegrator
- [ ] `agents/seo/tools/strategy_tools.py` — supprimer TopicClusterBuilder
- [ ] `agents/seo/seo_crew.py` — retirer les tools supprimés de la liste des tools assignés aux agents

---

#### P0.4 — Brancher Firecrawl et Exa comme tools CrewAI ✅

**Problème :** Les packages `firecrawl-py` et `exa-py` sont dans `requirements.txt`, les clés API sont configurées dans `.env.example` et `sync_env_to_doppler.sh`, des specs existent (SPEC-content-crawling.md, SPEC-competitor-analysis.md), mais AUCUN agent n'utilise Firecrawl et seulement 1 agent utilise Exa (Newsletter content curator dans `agents/newsletter/tools/content_tools.py`). Tout est prêt, il manque le câblage.

**Solution :**

1. Créer `agents/shared/tools/firecrawl_tools.py` — Wrappers `@tool` CrewAI autour du SDK Firecrawl :
   - [ ] `scrape_url(url: str)` — scraper une page et retourner le contenu structuré
   - [ ] `crawl_site(url: str, max_pages: int)` — crawler un site entier
   - [ ] `map_site(url: str)` — cartographier la structure d'un site
   - [ ] `search_web(query: str)` — recherche web via Firecrawl
   - [ ] `extract_structured(url: str, schema: dict)` — extraction de données structurées selon un schéma

2. Créer `agents/shared/tools/exa_tools.py` — Wrappers `@tool` CrewAI généralisés (le pattern existe déjà dans `content_tools.py`, le généraliser) :
   - [ ] `exa_search(query: str)` — recherche sémantique web
   - [ ] `exa_find_similar(url: str)` — trouver des pages similaires à une URL
   - [ ] `exa_get_contents(urls: list)` — récupérer le contenu de plusieurs URLs

3. Brancher sur les agents existants — Ajouter ces tools dans les listes `tools=[]` :
   - [ ] SEO Research Analyst (`agents/seo/agents/research_agent.py`) : `exa_search` + `firecrawl_crawl` pour l'analyse concurrentielle
   - [ ] SEO Copywriter (`agents/seo/agents/copywriter_agent.py`) : `firecrawl_scrape` pour analyser le contenu concurrent avant d'écrire
   - [ ] Newsletter Research Agent (`agents/newsletter/`) : généraliser les tools Exa existants dans `content_tools.py` vers les shared tools
   - [ ] Social Platform Adapter (`agents/social/`) : `exa_search` pour analyser les posts concurrents

**Prérequis :** Aucun — les packages et clés API sont déjà en place.
**Effort estimé :** ~2h
**Bénéfice :** Les agents accèdent enfin au web de manière structurée, sans passer par des tokens LLM coûteux pour le scraping.

---

### P1 — Moyen terme (restructuration de l'orchestration)

#### P1.1 — Passer à un vrai Crew multi-agents (pipeline SEO)

- [ ] **Refactorer le pipeline SEO en un seul Crew multi-agents**

**Problème :** Le pipeline SEO dans `seo_crew.py` crée 6 Crews séparées d'1 agent chacune, lancées séquentiellement :
```python
research_crew = Crew(agents=[self.research_agent.agent], tasks=[research_task])
research_output = research_crew.kickoff()
strategy_crew = Crew(agents=[self.strategy_agent.agent], tasks=[strategy_task])
# etc.
```
C'est l'**anti-pattern de CrewAI**. L'intérêt de CrewAI c'est justement l'orchestration multi-agents avec délégation, mémoire partagée et collaboration.

**Solution détaillée :**

1. Remplacer les 6 Crews séparées par **UN SEUL Crew** avec les 6 agents
2. Utiliser `Process.sequential` pour commencer (le plus simple, le plus prévisible), puis évaluer `Process.hierarchical` (avec un agent Manager qui décide de l'ordre) une fois que le sequential fonctionne bien
3. Code cible :
   ```python
   from crewai import Crew, Process

   seo_crew = Crew(
       agents=[research, strategy, copywriter, technical, marketing, editor],
       tasks=[research_task, strategy_task, writing_task, technical_task, marketing_task, editing_task],
       process=Process.hierarchical,
       manager_llm=llm,
       verbose=True
   )
   result = seo_crew.kickoff(inputs={"topic": topic, "url": url})
   ```
4. Tester avec des inputs connus pour vérifier que la qualité de l'output est au moins égale à l'approche actuelle

**Fichiers à modifier :**
- [ ] `agents/seo/seo_crew.py` — refactoring majeur : fusionner les 6 Crews en 1

---

#### P1.2 — Activer la délégation inter-agents

- [ ] **Permettre la collaboration entre agents via `allow_delegation=True`**

**Problème :** `allow_delegation=False` est mis sur **TOUS les 21 agents** sans exception. Aucun agent ne peut demander à un autre de l'aider ou de corriger son travail. Cela empêche toute collaboration intelligente.

**Solution détaillée :**

Mettre `allow_delegation=True` sur les agents qui bénéficient de collaboration :

| Agent | Robot | Pourquoi activer la délégation |
|-------|-------|-------------------------------|
| Editor SEO | SEO | Devrait pouvoir renvoyer au copywriter pour corrections |
| Strategy Expert | SEO | Devrait pouvoir demander des données au research analyst |
| Audience Analyst | Psychology | Devrait pouvoir consulter le research analyst SEO |
| Marketing Strategist | SEO | Devrait pouvoir valider avec le technical SEO |

Garder `allow_delegation=False` sur les agents terminaux (ceux qui produisent l'output final, comme le copywriter ou le technical SEO analyst).

**Fichiers à modifier :**
- [ ] `agents/seo/agents/*.py` — tous les fichiers d'agents SEO
- [ ] `agents/psychology/agents/*.py` — les fichiers d'agents Psychology
- [ ] `agents/newsletter/agents/*.py` — les fichiers d'agents Newsletter
- [ ] `agents/social/agents/*.py` — le fichier d'agent Social
- [ ] `agents/short/agents/*.py` — le fichier d'agent Short

---

#### P1.3 — Remplacer `str(output)` par des schémas Pydantic entre stages

- [ ] **Structurer les échanges inter-agents avec des modèles Pydantic**

**Problème :** Le passage de données entre stages est brutal : `str(research_output)` sérialisé en texte brut, tronqué (`outline[:2000]`), collé dans le prompt suivant. Perte d'information massive à chaque transition.

**Solution détaillée :**

1. Définir des schémas Pydantic pour chaque output d'agent :
   ```python
   from pydantic import BaseModel

   class ResearchOutput(BaseModel):
       competitors: list[CompetitorAnalysis]
       keywords: list[KeywordData]
       content_gaps: list[str]
       market_position: str

   class StrategyOutput(BaseModel):
       pillar_pages: list[PillarPage]
       topic_clusters: list[TopicCluster]
       content_calendar: list[CalendarEntry]
       priority_keywords: list[str]
   ```
2. Utiliser `output_pydantic=ResearchOutput` sur les Tasks CrewAI — ce pattern existe **déjà** dans le code pour les schémas d'images (`agents/images/`), donc le mécanisme est validé
3. L'agent suivant reçoit des données structurées au lieu de texte brut — plus de `str()` ni de troncature `[:2000]`
4. Chaque schéma doit documenter ses champs avec des `Field(description=...)` pour guider le LLM

**Fichiers à créer :**
- [ ] `agents/seo/schemas/research_output.py` — schéma de sortie de l'agent Research Analyst
- [ ] `agents/seo/schemas/strategy_output.py` — schéma de sortie de l'agent Strategy Expert
- [ ] `agents/seo/schemas/writing_output.py` — schéma de sortie de l'agent Copywriter
- [ ] `agents/seo/schemas/technical_output.py` — schéma de sortie de l'agent Technical SEO
- [ ] `agents/seo/schemas/marketing_output.py` — schéma de sortie de l'agent Marketing Strategist
- [ ] `agents/seo/schemas/editing_output.py` — schéma de sortie de l'agent Editor

**Fichier à modifier :**
- [ ] `agents/seo/seo_crew.py` — ajouter `output_pydantic=...` sur chaque Task

---

### P2 — Long terme (intelligence avancée)

#### P2.1 — Boucle d'évaluation et auto-correction

- [ ] **Ajouter un agent Évaluateur avec feedback loop dans chaque Crew**

**Problème :** Les agents génèrent du contenu mais ne l'évaluent jamais. Pas de feedback loop. Le premier jet est le jet final.

**Solution détaillée :**

1. Ajouter un agent **Évaluateur** dans chaque Crew qui note la qualité (score 1-10 sur des critères définis)
2. Si le score est < 7, renvoyer automatiquement à l'agent producteur avec le feedback détaillé
3. Limiter à **2 itérations max** pour éviter les boucles infinies et les coûts LLM excessifs
4. Critères d'évaluation par robot :

| Robot | Critères d'évaluation |
|-------|----------------------|
| SEO | Pertinence mots-clés, structure H1-H6, meta description, lisibilité Flesch |
| Newsletter | Qualité du hook, valeur ajoutée, CTA clair, longueur appropriée |
| Psychology | Profondeur d'analyse, actionabilité des insights, rigueur des sources |

**Fichiers à créer :**
- [ ] `agents/seo/agents/evaluator_agent.py`
- [ ] `agents/newsletter/agents/evaluator_agent.py`
- [ ] `agents/psychology/agents/evaluator_agent.py`

---

#### P2.2 — Convertir Scheduler et Images en vrais agents IA

- [ ] **Rendre le Scheduler et le pipeline Images intelligents**

**Problème :** Ces pipelines sont purement déterministes. Le Scheduler publie toujours de la même façon. L'Image pipeline génère toujours avec les mêmes paramètres, sans adaptation au contexte.

**Solution détaillée :**

- **Scheduler :** Un agent IA qui raisonne sur le **meilleur moment** de publication en analysant :
  - L'audience cible (fuseau horaire, habitudes de consommation)
  - L'historique de performance (quels jours/heures ont le meilleur engagement)
  - Les tendances actuelles (sujets trending à capitaliser rapidement)
  - Au lieu de suivre un calendrier fixe
- **Images :** Un agent IA qui choisit le style visuel, le cadrage, les couleurs en fonction :
  - Du contenu de l'article (ton, sujet, audience)
  - De la brand identity du projet
  - Des tendances visuelles du secteur
  - Au lieu d'appliquer des paramètres fixes

**Fichiers à modifier :**
- [ ] `agents/scheduler/scheduler_crew.py` — ajouter un vrai agent IA avec `crew.kickoff()`
- [ ] `agents/images/image_robot_crew.py` — ajouter un vrai agent IA pour le choix créatif

---

#### P2.3 — Orchestrateur avec branchement conditionnel

- [ ] **Évaluer LangGraph ou un state machine pour orchestration flexible**

**Problème :** Le pipeline est toujours linéaire (1→2→3→4→5→6). Certains stages pourraient tourner en parallèle (Technical SEO + Marketing SEO), et certains pourraient être skippés selon le contexte (pas besoin d'analyse technique si le contenu est une newsletter).

**Solution détaillée :**

1. Évaluer **LangGraph** ou un **state machine Python** (comme `transitions`) pour un orchestrateur plus flexible
2. Capacités visées :
   - **Parallélisme** — Technical SEO et Marketing SEO tournent en même temps
   - **Branchement conditionnel** — si le contenu est court, skipper l'analyse technique
   - **Boucles de feedback** — l'évaluateur peut renvoyer à n'importe quel agent
   - **Skip de stages** — selon le type de contenu, certains agents ne sont pas pertinents
3. Garder **CrewAI pour l'exécution des agents individuels**, mais gérer l'orchestration au niveau supérieur avec LangGraph

**Fichiers à créer :**
- [ ] `agents/shared/orchestrator.py` — orchestrateur avec state machine ou LangGraph
- [ ] `agents/shared/graph_definitions/` — définitions de graphes par robot

---

### Ce qui fonctionne bien (à préserver)

> Ces briques sont bien conçues et doivent être préservées telles quelles lors de la refonte :

- **Mémoire sémantique Mem0** (`memory/memory_service.py`) — recherche sémantique, scoping par projet, anti-duplication. Brique IA-native bien conçue.
- **RunHistory SQLite** (`agents/shared/run_history.py`) — les robots consultent leur historique. Bon pattern à étendre.
- **Status tracking** avec machine à états (`in_progress` → `generated` → `pending_review` → `approved` → `published`) — bon pour le workflow humain.
- **Agents Psychology** — les mieux conçus, utilisent vraiment le raisonnement IA qualitatif. **Modèle à suivre** pour les autres robots.
- **Schémas Pydantic images** — le pattern `output_pydantic` existe déjà dans `agents/images/`, il faut l'étendre aux autres robots (cf. P1.3).
- **Intégration DataForSEO** — les tools de données sont bien connectés aux APIs réelles, contrairement aux tools de writing/strategy qui sont factices.

---

## Veille stratégique

### OpenAI Skills in API — Compatibilité multi-LLM

**Lien :** https://developers.openai.com/cookbook/examples/skills_in_api
**Pertinence :** ContentFlowz ne doit pas être verrouillé sur un seul LLM. Le pattern "skills" d'OpenAI montre comment encapsuler des agents comme des bundles réutilisables avec un manifeste. Ce pattern est LLM-agnostique dans son concept : un skill = instructions + fichiers + outils, monté sur n'importe quel runtime.

**Actions à explorer :**
- [ ] Étudier comment rendre les agents CrewAI compatibles avec plusieurs LLMs (Claude, GPT, Codex, Gemini)
- [ ] Évaluer si le format manifeste SKILL.md pourrait standardiser la définition des agents indépendamment du LLM
- [ ] Tester CrewAI avec `llm` parameter pointant vers OpenAI GPT-5/Codex en plus de Claude
- [ ] Documenter les différences de comportement entre LLMs pour chaque agent (certains prompts marchent mieux sur Claude, d'autres sur GPT)
- [ ] Considérer un router intelligent qui choisit le meilleur LLM selon la tâche (ex: Claude pour le raisonnement éthique/psychology, Codex pour le code/technical SEO)

**Priorité :** Backlog — à considérer lors de la refonte P1

---

### ~~Minexa AI — Scraping IA structuré pour agents~~ → IGNORÉ

**Raison :** Redondant avec Firecrawl et Exa déjà connectés en MCP servers. Pas besoin d'un troisième outil de scraping.
- Firecrawl couvre : scraping, crawl, extract, search
- Exa couvre : recherche web sémantique, code context
- À la place, intégrer Firecrawl et Exa comme tools CrewAI dans les agents existants

---

### Codex Prompting Guide — Patterns de prompt engineering avancés

**Lien :** https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide
**Pertinence :** Guide complet de prompting pour agents IA autonomes. Patterns transposables à tous les LLMs :

**Patterns à transposer :**
- [ ] **Parallélisme multi-tools** — lancer plusieurs agents simultanément au lieu de séquentiellement (applicable au pipeline SEO P1.1)
- [ ] **Compaction de contexte** — pour les agents qui analysent de gros corpus (SEO, content analysis), maintenir le contexte sur de longues sessions sans exploser les tokens
- [ ] **Personnalité calibrée** — le pattern "friendly" (langage "nous", affirmation des progrès) est directement alignable avec les agents Psychology et le coach IA Quit Coke
- [ ] **Meta-prompting** — demander au LLM d'identifier ses propres points faibles et de proposer des corrections de prompts. Applicable aux agents les moins performants.
- [ ] **Plan management** — le pattern update_plan avec statuts (pending/in_progress/completed) est transposable à l'orchestration des pipelines CrewAI

**Priorité :** Backlog — à intégrer progressivement lors de l'externalisation des prompts (P0.1)

# TOOLS.md - Analyse des outils potentiels pour contentflow_lab

## Top 5 Prioritaires

| Priorité | Outil              | Raison                                                    |
| -------- | ------------------ | --------------------------------------------------------- |
| 1        | **MCP Python SDK** | Exposer contentflow_lab comme serveur MCP standardisé           |
| 2        | **GPT Researcher** | Améliorer le Research Analyst avec recherche multi-source |
| 3        | **Jina AI**        | Reader API + embeddings pour content analysis             |
| 4        | **Vestige**        | Mémoire cognitive MCP pour Claude (alternative Letta)     |
| 5        | **TokenTap**       | Monitoring tokens/coûts LLM en temps réel                 |
| 6        | **Veritas Kanban** | Orchestration visuelle pour agents IA                     |
| 7        | **Dash**           | Data agent self-learning avec 6 couches de contexte       |

---

https://bunny.net/blog/meet-bunny-database-the-sql-service-that-just-works/
https://www.qodo.ai/
https://www.sourcery.ai/
https://www.mintlify.com/
https://pipedream.com/
https://www.windmill.dev/

## Outils analysés

### 1. Augment Code

- **URL:** https://docs.augmentcode.com/introduction
- **Description:** Plateforme IA pour développeurs avec compréhension contextuelle du codebase, autocomplétion et agent de codage autonome.
- **Pertinence pour Content Flows:** Pas pertinent. Concurrent de Claude Code/Cursor. Déjà couvert par les outils existants.

---

### 2. BookTutor AI (Docling + RAG)

- **URL:** https://github.com/AI-Engineer-Skool/booktutor-ai
- **Description:** Transforme des PDFs en tuteurs IA interactifs via RAG. Crée une knowledge base interrogeable à partir de livres/documents avec LM Studio local.
- **Pertinence pour Content Flows:** Potentiellement intéressant pour le Newsletter Agent ou l'Article Generator. Permettrait d'ingérer des ebooks SEO/marketing comme sources de connaissance. Pattern RAG similaire à Exa AI.

---

### 3. Krafna

- **URL:** https://github.com/7sedam7/krafna
- **Description:** CLI Rust pour requêter des fichiers Markdown avec syntaxe SQL-like. Extrait frontmatter, liens, tâches. Ultra-rapide (5000 fichiers en 100ms).
- **Pertinence pour Content Flows:** Très pertinent pour le Scheduling Robot et l'analyse de contenu. Peut auditer la topical flow et les liens internes des projets Astro (webinde, etc.).

---

### 4. MarkdownDB

- **URL:** https://markdowndb.com/
- **Description:** Bibliothèque JS qui indexe le Markdown en SQLite. Extrait frontmatter, tags, liens, tâches avec API Node.js.
- **Pertinence pour Content Flows:** Excellent pour l'intégration Astro. Le Technical SEO Analyzer pourrait analyser la structure de contenu, détecter les orphan pages, valider les topic clusters. Complémentaire à Krafna (JS vs Rust).

---

### 5. Languine

- **URL:** https://github.com/languine-ai/languine
- **Description:** CLI de traduction automatique avec détection Git diff. Supporte JSON, YAML, MD. 100+ langues via IA.
- **Pertinence pour Content Flows:** Peu pertinent directement, mais utile pour les projets bilingues (velvet, webinde). Pourrait être intégré au Scheduling Robot pour automatiser la traduction de contenus publiés.

---

### 6. ClickRank

- **URL:** https://appsumo.com/products/clickrank/
- **Description:** Outil SEO pour visibilité dans les moteurs IA (ChatGPT, Claude, Perplexity). Vérifie l'indexation par les crawlers IA, audit automatisé.
- **Pertinence pour Content Flows:** Très pertinent pour le SEO Robot. L'optimisation pour les "AI search engines" est une évolution naturelle du SEO. Pourrait enrichir le Technical SEO Specialist avec un nouveau type d'audit.

---

### 7. KWHero

- **URL:** https://appsumo.com/products/kwhero/
- **Description:** Plateforme SEO avec keyword research, génération de contenu IA (GPT-4), et analyse de concurrents. 80+ langues.
- **Pertinence pour Content Flows:** Redondant. Le SEO Robot + Article Generator font déjà ça. Peut servir de benchmark pour comparer les fonctionnalités.

---

### 8. Grigora

- **URL:** https://appsumo.com/products/grigora/
- **Description:** Website builder no-code avec outils SEO intégrés, blog, newsletter, drag-and-drop.
- **Pertinence pour Content Flows:** Pas pertinent. Astro est déjà utilisé et bien plus flexible. Grigora cible les non-développeurs.

---

### 9. Model Context Protocol - Python SDK

- **URL:** https://github.com/modelcontextprotocol/python-sdk
- **Description:** SDK officiel MCP pour créer des serveurs exposant Resources, Tools et Prompts aux LLMs. Transports stdio, SSE, HTTP.
- **Pertinence pour Content Flows:** TRÈS PERTINENT. Permettrait d'exposer les capacités de Content Flows (SEO analysis, newsletter generation) comme MCP server. Les agents CrewAI seraient accessibles via MCP à Claude Code ou d'autres clients LLM.

---

### 10. Model Context Protocol - TypeScript SDK

- **URL:** https://github.com/modelcontextprotocol/typescript-sdk
- **Description:** Même SDK en TypeScript avec intégration Express/Hono. Monorepo avec packages client/server.
- **Pertinence pour Content Flows:** Moins pertinent car Content Flows est Python. Utile pour exposer des outils MCP depuis tubeflow (TypeScript).

---

### 11. Box Platform

- **URL:** https://developer.box.com/platform/use-cases
- **Description:** API de gestion documentaire pour workflows de contenu, stockage sécurisé, ML sur documents. Enterprise-focused.
- **Pertinence pour Content Flows:** Peu pertinent. Content Flows gère du contenu Markdown/web, pas des documents d'entreprise (claims, compliance).

---

### 12. GPT4Free

- **URL:** https://github.com/xtekky/gpt4free
- **Description:** Agrégateur de providers LLM sans auth individuelle. API OpenAI-compatible. 65k+ stars.
- **Pertinence pour Content Flows:** NON RECOMMANDÉ. Zone grise légale/éthique. Risques de fiabilité et TOS violations. Pas adapté pour usage production.

---

### 13. Huginn

- **URL:** https://github.com/huginn/huginn
- **Description:** Plateforme d'automatisation self-hosted avec agents connectables (IFTTT/Zapier-like). Events propagent en graphe dirigé. Custom JS/CoffeeScript.
- **Pertinence pour Content Flows:** Très pertinent comme orchestrateur externe. Peut coordonner les workflows : trigger newsletter sur RSS, alertes SEO, monitoring compétiteurs. Complémentaire à CrewAI (Huginn = orchestration externe, CrewAI = agents IA internes).

---

### 14. GPT Researcher

- **URL:** https://docs.gptr.dev/docs/gpt-researcher/getting-started/introduction
- **Description:** Agent autonome de recherche web. Génère des rapports 2000+ mots avec 20+ sources. Multi-agent (planner + executors). ~$0.10/recherche.
- **Pertinence pour Content Flows:** EXCELLENT pour le Research Analyst du SEO Robot. Peut remplacer ou enrichir Exa AI avec une approche plus complète. Architecture multi-agent similaire à CrewAI.

---

### 15. TurboSeek

- **URL:** https://github.com/Nutlope/turboseek
- **Description:** Moteur de recherche IA open-source style Perplexity. Utilise Exa.ai + Together AI + Llama 3.1.
- **Pertinence pour Content Flows:** Référence d'architecture intéressante. Montre comment combiner recherche + LLM + follow-up questions. Peut inspirer des améliorations du Newsletter Agent.

---

### 16. InvokeAI

- **URL:** https://github.com/invoke-ai/InvokeAI
- **Description:** Plateforme de génération d'images (Stable Diffusion, FLUX). WebUI React, canvas unifié, workflows nodes. Apache 2.0.
- **Pertinence pour Content Flows:** Pertinence limitée actuellement. Utile si génération d'images pour articles/newsletters ajoutée plus tard. À garder en tête pour une future "Image Generation Crew".

---

### 17. Letta Platform

- **URL:** https://docs.letta.com/
- **Description:** Framework pour agents IA stateful avec mémoire persistante. Core memory, archival memory, multi-agent, human-in-the-loop.
- **Pertinence pour Content Flows:** TRÈS PERTINENT pour évoluer les agents. CrewAI est stateless par défaut. Letta permettrait aux agents de mémoriser les analyses précédentes, préférences client, historique SEO. Upgrade significatif.

---

### 18. Pew Pew Plaza Packs

- **URL:** https://github.com/appboypov/pew-pew-plaza-packs
- **Description:** Framework de gestion de projet IA modulaire. Agents, workflows, templates réutilisables. Système WikiLink pour références dynamiques.
- **Pertinence pour Content Flows:** Intéressant pour structurer documentation et prompts. Le système de composants pourrait organiser les prompts des agents CrewAI. Plus méthodologique que technique.

---

### 19. Jina AI

- **URL:** https://jina.ai/
- **Description:** Infrastructure de recherche : Reader API (URL→Markdown), Embeddings multimodaux multilangues, Reranker. Serveur MCP disponible. 8.3T tokens/mois.
- **Pertinence pour Content Flows:** TRÈS PERTINENT. Reader API parfait pour l'Article Generator (extraction propre de contenu concurrent). Embeddings pour améliorer la topical flow analysis avec semantic search.

---

### 20. Triplo AI

- **URL:** https://documentation.triplo.ai/faq/local-models-and-its-strengths
- **Description:** Assistant IA tout-en-un avec support de 80+ modèles locaux (3B à 405B params). Génération, traduction, webhooks.
- **Pertinence pour Content Flows:** Peu pertinent comme produit. Le guide des modèles locaux est utile si besoin de runner LLMs localement pour réduire les coûts. Content Flows utilise déjà OpenAI/Anthropic via API.

---

### 21. Matomo

- **URL:** https://matomo.org/faq/on-premise/installing-matomo/
- **Description:** Analytics web self-hosted avec respect RGPD, ownership données, tracking temps réel. Alternative à Google Analytics.
- **Pertinence pour Content Flows:** Pertinent pour le monitoring post-publication. Le Publishing Agent pourrait intégrer Matomo pour tracker les performances des articles publiés sur les sites Astro. API disponible.

---

### 22. LingBot-World

- **URL:** https://github.com/Robbyant/lingbot-world
- **Description:** Simulateur de monde open-source basé sur génération vidéo. Génère des séquences jusqu'à 1 minute avec cohérence long-terme. Temps réel (<1s latence, 16fps).
- **Pertinence pour Content Flows:** Peu pertinent. Orienté génération vidéo/simulation, pas SEO ou contenu textuel. Pourrait être intéressant pour une future génération de vidéos marketing, mais hors scope actuel.

---

### 23. Qwen3-ASR

- **URL:** https://github.com/QwenLM/Qwen3-ASR
- **Description:** Modèles ASR open-source d'Alibaba. Reconnaissance parole/musique/chant en 30 langues + 22 dialectes chinois. Streaming et batch, timestamps inclus.
- **Pertinence pour Content Flows:** Potentiellement intéressant pour transcription de podcasts/vidéos comme source de contenu pour l'Article Generator ou Newsletter Agent. Permettrait d'extraire du contenu audio concurrent.

---

### 24. TokenTap

- **URL:** https://github.com/jmuncor/tokentap
- **Description:** CLI Python qui intercepte le trafic API LLM et affiche un dashboard temps réel. Jauge de tokens colorée, archive des prompts en Markdown/JSON, statistiques de session.
- **Pertinence pour Content Flows:** TRÈS PERTINENT pour le monitoring des coûts. Les agents CrewAI consomment beaucoup de tokens. TokenTap permettrait de debugger les prompts, tracker les coûts par agent, et optimiser l'usage. Zero config (proxy HTTP local).

---

### 25. Kimi-K2.5

- **URL:** https://github.com/MoonshotAI/Kimi-K2.5
- **Description:** Modèle multimodal de Moonshot AI. 1T params (32B activés), 256K contexte. Architecture "Agent Swarm" avec décomposition en sous-tâches parallèles. Vision + code natifs.
- **Pertinence pour Content Flows:** Intéressant comme alternative LLM. L'architecture swarm multi-agent est similaire à CrewAI. Pourrait être utilisé pour des tâches nécessitant compréhension visuelle (analyse de screenshots SEO, UI competitors).

---

### 26. Moltworker / OpenClaw

- **URL:** https://github.com/cloudflare/moltworker
- **Description:** Framework pour déployer un assistant IA personnel sur Cloudflare Workers. Intégrations Telegram/Discord/Slack, persistance R2, browser automation via CDP.
- **Pertinence pour Content Flows:** Moyennement pertinent. Pourrait servir à exposer les agents Content Flows via chat (Telegram/Discord) pour notifications et commandes. L'aspect serverless est intéressant mais expérimental.

---

### 27. evlog

- **URL:** https://github.com/HugoRCD/evlog
- **Description:** Framework de logging structuré "wide events". Un log par requête avec tout le contexte. Erreurs avec what/why/how. Intégration Nuxt/Nitro native.
- **Pertinence pour Content Flows:** Pertinence limitée car Content Flows est Python, pas Nuxt/Nitro. Le concept de "wide events" est intéressant pour le logging des agents, mais nécessiterait un équivalent Python (structlog, loguru).

---

### 28. Vestige

- **URL:** https://github.com/samvallad33/vestige
- **Description:** Serveur MCP de mémoire cognitive pour Claude. FSRS-6 (spaced repetition), spreading activation, synaptic tagging. Mémoires qui décroissent naturellement, ingestion intelligente avec détection de duplicats.
- **Pertinence pour Content Flows:** TRÈS PERTINENT. Alternative à Letta mais via MCP. Permettrait à Claude Code d'avoir une mémoire persistante des analyses SEO, préférences, historique de projets. Basé sur 130 ans de recherche en mémoire cognitive. 100% local.

---

### 29. Dex

- **URL:** https://github.com/dcramer/dex
- **Description:** Système de task tracking conçu pour agents IA. Tasks avec description, background/requirements, et summary d'implémentation. Stockage JSONL compatible Git.
- **Pertinence pour Content Flows:** TRÈS PERTINENT pour coordination multi-session. Les agents CrewAI pourraient utiliser Dex pour tracker les tâches SEO en cours, maintenir le contexte entre sessions, et collaborer sur des projets long-terme.

---

### 30. Veritas Kanban

- **URL:** https://github.com/BradGroux/veritas-kanban
- **Description:** Kanban local-first pour l'ère agentique. Orchestration d'agents autonomes, git worktree par tâche, code review UI, sync GitHub Issues, analytics. Stack React 19 + Express, stockage Markdown.
- **Pertinence pour Content Flows:** TRÈS PERTINENT comme interface visuelle d'orchestration. Pourrait servir de dashboard pour superviser les agents CrewAI, assigner des tâches SEO, reviewer le contenu généré. Intégration native avec OpenClaw.

---

### 31. Dash (agno-agi)

- **URL:** https://github.com/agno-agi/dash
- **Description:** Data agent self-learning avec 6 couches de contexte (schemas, business rules, SQL patterns, knowledge, error patterns, live introspection). Transforme questions en SQL. Auto-amélioration sans retraining.
- **Pertinence pour Content Flows:** TRÈS PERTINENT pour analytics SEO. Pourrait permettre d'interroger les données de performance (Matomo, Search Console) en langage naturel. L'architecture à 6 couches de contexte est un pattern réutilisable pour les agents CrewAI.

---

### 32. MOVA

- **URL:** https://github.com/OpenMOSS/MOVA
- **Description:** Modèle open-source de génération vidéo+audio synchronisée. Lip-sync multilingue, effets sonores contextuels. 360p et 720p disponibles. Fully open-source (poids, code, training).
- **Pertinence pour Content Flows:** Peu pertinent actuellement. Pourrait devenir utile pour générer des vidéos marketing avec voiceover pour les articles/newsletters. Alternative open-source à Sora/Veo. Hors scope immédiat.

---

### 33. Nanobot

- **URL:** https://github.com/HKUDS/nanobot
- **Description:** Assistant IA ultra-léger (~4000 lignes vs 430k pour Clawdbot). Market analysis, software engineering, task management, knowledge assistant. Multi-LLM (OpenRouter, Claude, GPT, etc.). Telegram/WhatsApp/Feishu.
- **Pertinence pour Content Flows:** Intéressant comme référence d'architecture minimaliste. Pourrait inspirer une version "lite" des agents CrewAI. L'intégration multi-plateforme chat est utile pour exposer les robots via messaging.

---

### 34. MARVIN

- **URL:** https://github.com/SterlingChin/marvin-template
- **Description:** Assistant IA personnel "Chief of Staff". Mémoire persistante, goal tracking, task management, daily briefings. Intégrations Google/Microsoft/Atlassian. Slash commands (/start, /end, /report, /sync).
- **Pertinence pour Content Flows:** Pattern intéressant pour l'orchestration. Le concept de "daily briefing" pourrait être adapté pour un rapport SEO quotidien. L'architecture workspace séparé (data vs code) est une bonne pratique.

---

### 35. Manim Skill

- **URL:** https://github.com/adithya-s-k/manim_skill
- **Description:** Skills pour créer des animations mathématiques style 3Blue1Brown. Support Manim Community Edition et ManimGL. Best practices, patterns, exemples testés. Intégration Claude Code via skills.sh.
- **Pertinence pour Content Flows:** Peu pertinent pour SEO/newsletter. Pourrait être utile si génération de vidéos éducatives/explicatives ajoutée plus tard. Niche mais de qualité.

---

### 36. Launchpad (trycua)

- **URL:** https://github.com/trycua/launchpad
- **Description:** Monorepo pour créer des vidéos de lancement produit avec React/Remotion. Composants d'animation réutilisables (FadeIn, SlideUp, TextReveal). AI-assisted via Claude Code.
- **Pertinence pour Content Flows:** Intéressant pour le contenu vidéo marketing. Pourrait automatiser la création de vidéos promotionnelles pour les articles générés. L'approche "code as video" est moderne et maintenable.

---

### 37. Frame

- **URL:** https://github.com/66HEX/frame
- **Description:** GUI FFmpeg rapide en Tauri v2/Rust. H.264/H.265/VP9/AV1, accélération GPU (Apple Silicon, NVIDIA). Presets sauvegardables, multi-langue.
- **Pertinence pour Content Flows:** Peu pertinent directement. Utile si traitement vidéo en batch nécessaire (compression vidéos générées par MOVA/Launchpad). Outil desktop, pas API.

---

### 38. pdf2video

- **URL:** https://github.com/DangJin/pdf2video
- **Description:** Convertit PDFs en présentations vidéo avec animations (stack, focus, switch, fan). Titres, descriptions avec effet typing, progress bar. React + Remotion + PDF.js. Skill Claude Code inclus.
- **Pertinence pour Content Flows:** Intéressant pour repurposing de contenu. Les guides/whitepapers SEO générés pourraient être convertis en vidéos pour YouTube/LinkedIn. Automatisation via skill Claude Code.

---

### 39. You.com Python SDK

- **URL:** https://docs.you.com/developer-resources/python-sdk
- **Description:** SDK officiel pour l'API You.com. Search web + news unifié, filtrage par fraîcheur/géo, métadonnées structurées (URLs, thumbnails, latency). Gestion d'erreurs intégrée.
- **Pertinence pour Content Flows:** PERTINENT comme alternative/complément à Exa AI pour le Research Analyst. Combine résultats web et news. Pourrait enrichir le Newsletter Agent avec des sources d'actualités fraîches.

---

### 40. Palo Santo AI (Inspiration)

- **URL:** https://www.palosanto.ai/
- **Description:** Agence marketing digital avec suite "Forge" : Programmatic Forge (landing pages auto), Semantic Flow (topic graphs, schema), Performance Forge (paid media), Analytics Lab, Landing Ops, Automation Graph.
- **Pertinence pour Content Flows:** INSPIRATION plutôt qu'outil. Leur architecture modulaire (Forge Suite) valide l'approche Content Flows. Concepts à emprunter : topic graphs, entity markup, demand clustering, automation guardrails.

---

### 41. Cerebras Automated User Research

- **URL:** https://inference-docs.cerebras.ai/cookbook/agents/automate-user-research
- **Description:** Système multi-agent LangGraph pour recherche utilisateur automatisée. Génération de personas, interviews simulées, routing conditionnel, synthèse d'insights. Cycle complet en <60s via Cerebras inference.
- **Pertinence pour Content Flows:** TRÈS PERTINENT pour validation de contenu. Avant publication, les articles pourraient être "testés" sur des personas générées pour valider la pertinence. Pattern multi-agent transposable à CrewAI.

---

## Mentions honorables

- **Krafna/MarkdownDB** : Audit contenu Astro
- **ClickRank** : AI search SEO (nouveau paradigme)
- **Matomo** : Analytics post-publication
- **BookTutor AI** : RAG sur documents PDF
- **Vestige** : Mémoire cognitive MCP (alternative Letta)
- **TokenTap** : Monitoring coûts LLM
- **Dex** : Task tracking pour agents
- **Veritas Kanban** : Orchestration visuelle agents
- **Dash** : Data agent self-learning SQL
- **You.com SDK** : Alternative Exa AI pour recherche
- **Cerebras User Research** : Validation contenu via personas
- **pdf2video/Launchpad** : Repurposing contenu en vidéo

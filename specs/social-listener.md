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
next_step: "/sf-docs audit specs/social-listener.md"
---
# SPEC : Social Listener — Veille sociale multi-plateforme pour l'Idea Pool

**Date** : 2026-03-29
**Statut** : Approuve
**Branche** : main

---

## Contexte

L'Idea Pool est alimente par 4 sources : SEO keywords (DataForSEO), newsletters (IMAP), competitor watch (DataForSEO), weekly ritual (manuel). Il manque le signal **social/trending** : ce dont les gens parlent *maintenant* sur les reseaux et communautes.

Inspire de [last30days-skill](https://github.com/mvanhorn/last30days-skill), ce module ajoute un 5e niveau d'ingestion qui scrape Reddit, X, Hacker News et YouTube, rank les resultats par engagement + recence, detecte les questions recurrentes, et injecte des idees dans l'Idea Pool.

## Solution

Un module `agents/sources/social_listener.py` avec 4 collecteurs (Reddit, X, HN, YouTube) qui passent par Exa AI (deja dans les deps) + scraping direct HN. Chaque collecteur retourne des items normalises, un ranking pipeline les score, et `bulk_create_ideas()` les injecte.

## Scope

**In :**
- Collecte Reddit, X, HN, YouTube via Exa + scraping HN
- Ranking par engagement velocity + recence + convergence cross-plateforme
- Detection de questions recurrentes (signal de demande)
- Injection Idea Pool avec `trending_signals` rempli
- Job type `ingest_social` dans le scheduler
- Endpoint `POST /api/ideas/ingest/social` pour trigger manuel

**Out :**
- TikTok, Instagram, Bluesky (v2)
- Posting/auto-commenting
- UI/frontend
- ScrapeCreators API (v2)

---

## Taches d'implementation

- [ ] Tache 1 : Ajouter IdeaSource.SOCIAL_LISTENING a l'enum
  - Fichier : `api/models/idea_pool.py`
  - Action : Ajouter `SOCIAL_LISTENING = "social_listening"` dans IdeaSource

- [ ] Tache 2 : Creer le module social_listener.py
  - Fichier : `agents/sources/social_listener.py` (nouveau)
  - Action : Creer le module avec :
    - `_search_exa(query, platform_filter, days_back)` — wrapper Exa commun
    - `_collect_reddit(topics, days_back)` — Exa search filtree sur reddit.com
    - `_collect_x(topics, days_back)` — Exa search filtree sur x.com/twitter.com
    - `_collect_hn(topics, days_back)` — HTTP direct sur HN Algolia API (gratuit, pas d'auth)
    - `_collect_youtube(topics, days_back)` — Exa search filtree sur youtube.com
    - `_normalize_results(raw_items)` — normalise tous les resultats en format commun
    - `_rank_results(items)` — score par engagement + recence + convergence
    - `_detect_convergence(items)` — trigram Jaccard sur titres cross-plateforme
    - `_detect_questions(items)` — filtre les items qui sont des questions
    - `_deduplicate(items)` — supprime les doublons par similarite de titre
    - `ingest_social_listening(topics, days_back, max_ideas, project_id)` — orchestrateur principal

  Notes d'implementation :
  - HN Algolia API : `GET http://hn.algolia.com/api/v1/search?query=...&tags=story&numericFilters=created_at_i>TIMESTAMP`
  - Exa `search_and_contents` avec domain filter : `include_domains=["reddit.com"]`
  - Ranking formula : `score = (engagement_norm * 0.4) + (recency_score * 0.3) + (convergence_bonus * 0.3)`
  - Convergence : meme sujet detecte sur 2+ plateformes -> bonus x1.5
  - Questions : detectees par "?" dans le titre ou prefixes "How", "Why", "What", "Is there"

- [ ] Tache 3 : Ajouter job_type "ingest_social" au scheduler
  - Fichier : `scheduler/scheduler_service.py`
  - Action :
    - Ajouter `"ingest_social"` dans le dispatch `_tick` (elif block)
    - Creer `_run_ingest_social(job)` qui importe et appelle `ingest_social_listening()`
    - Configuration attendue : `{ topics: [...], days_back: 30, max_ideas: 50 }`

- [ ] Tache 4 : Ajouter endpoint trigger manuel
  - Fichier : `api/routers/idea_pool.py`
  - Action : Ajouter `POST /api/ideas/ingest/social`
    - Body : `{ topics: list[str], days_back: int = 30, max_ideas: int = 50, project_id: str | None }`
    - Lance `ingest_social_listening()` via `asyncio.to_thread()`
    - Retourne `{ count: int, sources: dict[str, int] }`

- [ ] Tache 5 : Ecrire les tests
  - Fichier : `tests/tools/test_social_listener.py` (nouveau)
  - Action :
    - `test_normalize_results` — format commun respecte
    - `test_rank_results` — scoring correct (engagement + recence + convergence)
    - `test_detect_convergence` — bonus applique quand meme sujet sur 2+ plateformes
    - `test_detect_questions` — detection "?" et prefixes interrogatifs
    - `test_ingest_social_listening_mocked` — mock Exa + HN, verifie appel bulk_create_ideas
    - `test_hn_api_parsing` — parse correct de la reponse HN Algolia
    - `test_deduplicate` — titres quasi-identiques fusionnes

---

## Format des items normalises

```python
{
    "title": "How to use AI for content marketing",
    "url": "https://reddit.com/r/marketing/...",
    "platform": "reddit",          # reddit | x | hn | youtube
    "engagement": 342,             # upvotes, likes, points, views
    "comment_count": 47,
    "author": "u/marketingpro",
    "published_at": "2026-03-15T...",
    "snippet": "First 300 chars of content...",
    "is_question": True,
}
```

## Format injection Idea Pool

```python
{
    "title": "How to use AI for content marketing",
    "raw_data": {
        "url": "https://reddit.com/r/marketing/...",
        "platform": "reddit",
        "engagement": 342,
        "comment_count": 47,
        "author": "u/marketingpro",
        "snippet": "...",
        "is_question": True,
        "convergence_platforms": ["reddit", "hn"],
    },
    "trending_signals": {
        "source": "social_listening",
        "platforms_found": ["reddit", "hn"],
        "total_engagement": 520,
        "engagement_velocity": 17.3,
        "convergence_score": 1.5,
        "question_signal": True,
    },
    "priority_score": 72.5,
    "tags": ["social_listening", "reddit", "hn", "question", "converging"],
}
```

---

## Dependances

- **Exa AI** (`exa-py`) — deja dans requirements.txt, EXA_API_KEY configure
- **httpx** — deja dans deps (pour HN Algolia API)
- **Aucune nouvelle dependance**

## APIs externes

| API | Auth | Cout | Usage |
|-----|------|------|-------|
| Exa `search_and_contents` | EXA_API_KEY (existant) | Inclus dans plan existant | Reddit, X, YouTube |
| HN Algolia | Aucune | Gratuit | Hacker News stories |

## Strategie de test

- **Unit** : normalisation, ranking, convergence, questions — tout mockable
- **Integration** : mock Exa + mock httpx pour HN, verifie le flow complet jusqu'a `bulk_create_ideas()`
- **Pas de test network** : tout mocke, pas de calls reels dans les tests

## Risques

| Risque | Mitigation |
|--------|-----------|
| Rate limit Exa (4 calls par run : reddit, x, youtube, general) | 1 seul call par plateforme, respecter les limites |
| HN Algolia rate limit | Max 10k req/h — largement suffisant |
| Resultats Exa pauvres pour X (x.com bloque certains crawlers) | Fallback gracieux : si 0 resultats X, on continue avec les autres |
| Doublons dans l'Idea Pool (meme sujet de 2 plateformes) | Deduplication par similarite de titre avant bulk_create |

---

## Criteres d'acceptation

- [ ] CA 1 : Given des topics ["ai content marketing"], when `ingest_social_listening()` est appele, then des idees sont creees dans l'Idea Pool avec source="social_listening"

- [ ] CA 2 : Given un sujet qui apparait sur Reddit ET HN, when le ranking est applique, then l'idee recoit un convergence_score >= 1.5 et le tag "converging"

- [ ] CA 3 : Given un post Reddit avec "?" dans le titre, when la detection de questions tourne, then l'idee a is_question=True dans raw_data et le tag "question"

- [ ] CA 4 : Given EXA_API_KEY non configure, when `ingest_social_listening()` est appele, then la fonction retourne 0 et print un warning (pas de crash)

- [ ] CA 5 : Given un job_type="ingest_social" dans le scheduler, when le job est du, then `_run_ingest_social()` est dispatche et appelle `ingest_social_listening()`

- [ ] CA 6 : Given `POST /api/ideas/ingest/social` avec topics=["seo tools"], when l'endpoint est appele, then il retourne `{count: N, sources: {reddit: X, hn: Y, ...}}`

- [ ] CA 7 : Given 2 posts Reddit avec des titres quasi-identiques, when la deduplication tourne, then un seul est injecte dans l'Idea Pool (pas de doublon)

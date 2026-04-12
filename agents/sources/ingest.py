"""Source ingestion — pulls ideas from external sources into the Idea Pool.

Each function reads from one source and calls bulk_create_ideas().
Called by the scheduler on a recurring basis.

Levels:
  1. ingest_seo_keywords     — DFS keyword ideas with real volume/difficulty/CPC
  2. enrich_ideas             — batch-enrich raw ideas with DFS keyword_overview
  3. ingest_competitor_watch  — DFS competitor gaps → Idea Pool
  4. track_serp_positions     — post-publication SERP ranking tracker
"""

import logging
import time
from collections import defaultdict
from typing import Optional


DFS_STANDARD_ENRICH_THRESHOLD = 25
DFS_STANDARD_KEYWORD_SEED_THRESHOLD = 3
DFS_STANDARD_COMPETITOR_RANKED_LIMIT = 30

logger = logging.getLogger(__name__)
DATAFORSEO_COST_PER_TASK = {"standard": 0.05, "live": 0.075}

DATAFORSEO_USAGE_METRICS: dict[str, dict[str, float]] = defaultdict(
    lambda: {
        "standard_calls": 0,
        "live_calls": 0,
        "standard_time": 0.0,
        "live_time": 0.0,
        "estimated_cost": 0.0,
    }
)


def _record_metric(pipeline: str, mode: str, duration: float, task_count: int = 1) -> None:
    metrics = DATAFORSEO_USAGE_METRICS[pipeline]
    metrics[f"{mode}_calls"] += 1
    metrics[f"{mode}_time"] += duration
    cost = DATAFORSEO_COST_PER_TASK.get(mode, 0.075) * task_count
    metrics["estimated_cost"] += cost
    logger.debug(
        "DataForSEO %s %s call took %.3fs (%d tasks ≈ $%.3f) (total: std=%d live=%d ≈ $%.2f)",
        pipeline,
        mode,
        duration,
        task_count,
        cost,
        metrics["standard_calls"],
        metrics["live_calls"],
        metrics["estimated_cost"],
    )


def _log_pipeline_metrics(pipeline: str) -> None:
    metrics = DATAFORSEO_USAGE_METRICS.get(pipeline)
    if not metrics:
        return
    logger.info(
        "DataForSEO %s metrics → standard: %d calls %.2fs; live: %d calls %.2fs; estimated cost: $%.3f",
        pipeline,
        metrics["standard_calls"],
        metrics["standard_time"],
        metrics["live_calls"],
        metrics["live_time"],
        metrics["estimated_cost"],
    )


def get_total_estimated_cost() -> float:
    """Return the total estimated DataForSEO cost across all pipelines."""
    return sum(m["estimated_cost"] for m in DATAFORSEO_USAGE_METRICS.values())


def flush_metrics() -> dict[str, dict[str, float]]:
    """Return current DFS usage metrics and reset counters.

    Call after each job run to capture costs for persistence.
    The scheduler uses this to feed status.cost_tracker.log_job_costs().
    """
    snapshot = {k: dict(v) for k, v in DATAFORSEO_USAGE_METRICS.items()}
    DATAFORSEO_USAGE_METRICS.clear()
    return snapshot


def _measure_call(pipeline: str, mode: str, call_fn, task_count: int = 1):
    start = time.perf_counter()
    try:
        result = call_fn()
    except Exception:
        _record_metric(pipeline, mode, time.perf_counter() - start, task_count)
        raise
    else:
        _record_metric(pipeline, mode, time.perf_counter() - start, task_count)
        return result


# ─────────────────────────────────────────────────────────────────────
# Newsletter inbox ingestion — LLM-powered idea extraction
# ─────────────────────────────────────────────────────────────────────


def ingest_newsletter_inbox(
    days_back: int = 7,
    folder: str = "Newsletters",
    max_results: int = 20,
    project_id: Optional[str] = None,
    persona_context: Optional[str] = None,
    archive_folder: str = "CONTENTFLOW_DONE",
) -> int:
    """Read newsletters via IMAP, extract ideas with LLM, and archive.

    Uses LLM to analyze full newsletter content and extract multiple
    actionable ideas per email, scored by relevance to persona/niche.
    Falls back to subject-line extraction if LLM is unavailable.

    Args:
        days_back: How many days back to fetch.
        folder: IMAP folder to read from.
        max_results: Max emails to fetch.
        project_id: Optional project scope.
        persona_context: Pre-formatted persona/niche text for LLM scoring.
        archive_folder: Gmail label to move processed emails to.

    Returns:
        Number of ideas created.
    """
    from status import get_status_service

    try:
        from agents.newsletter.tools.imap_tools import IMAPNewsletterReader
    except ImportError:
        print("⚠ imap-tools not installed, skipping newsletter inbox ingestion")
        return 0

    try:
        reader = IMAPNewsletterReader()
    except (ValueError, ImportError) as e:
        print(f"⚠ IMAP not configured: {e}")
        return 0

    emails = reader.fetch_newsletters(
        days_back=days_back,
        folder=folder,
        max_results=max_results,
    )

    if not emails:
        print("ℹ️  No newsletters found")
        return 0

    print(f"📬 Found {len(emails)} newsletters, extracting ideas...")

    # Try LLM extraction, fall back to naive subject-line approach
    items = _extract_with_llm(emails, persona_context)
    _log_pipeline_metrics("competitor.domain_intersection")
    _log_pipeline_metrics("competitor.ranked_keywords")

    if not items:
        print("⚠ LLM extraction returned no results, falling back to subject-line mode")
        items = _extract_naive(emails)

    if not items:
        print("ℹ️  No ideas extracted")
        return 0

    svc = get_status_service()
    count = svc.bulk_create_ideas(
        source="newsletter_inbox",
        items=items,
        project_id=project_id,
    )
    print(f"✅ Ingested {count} ideas from newsletter inbox")

    # Archive processed emails
    uids = [e.uid for e in emails if e.uid]
    if uids:
        try:
            archived = reader.archive_multiple(
                uids,
                archive_folder=archive_folder,
                source_folder=folder,
            )
            print(f"📁 Archived {archived} emails to {archive_folder}")
        except Exception as e:
            print(f"⚠ Archiving failed (ideas still saved): {e}")

    return count


def _extract_with_llm(emails: list, persona_context: Optional[str]) -> list[dict]:
    """Extract ideas using LLM analysis of newsletter content."""
    try:
        from agents.sources.newsletter_extractor import extract_ideas_from_newsletters
    except ImportError as e:
        print(f"⚠ Newsletter extractor not available: {e}")
        return []

    try:
        extracted = extract_ideas_from_newsletters(
            emails=emails,
            persona_context=persona_context or "",
        )
    except Exception as e:
        print(f"⚠ LLM extraction failed: {e}")
        return []

    if not extracted:
        return []

    items = []
    for idea in extracted:
        title = (idea.get("title") or "").strip()
        if not title:
            continue

        items.append({
            "title": title[:200],
            "raw_data": {
                "angle": idea.get("angle", ""),
                "source_newsletter": idea.get("source_newsletter", ""),
                "source_email": idea.get("source_email", ""),
                "source_name": idea.get("source_name", ""),
                "source_date": idea.get("source_date"),
                "relevance_reasoning": idea.get("relevance_reasoning", ""),
                "extraction_method": "llm",
            },
            "priority_score": idea.get("relevance_score"),
            "tags": ["newsletter_inbox"]
            + [t for t in idea.get("tags", []) if isinstance(t, str)][:4],
        })

    return items


def _extract_naive(emails: list) -> list[dict]:
    """Fallback: use email subject as idea title (old behavior)."""
    items = []
    for email in emails:
        subject = email.subject.strip()
        for prefix in ["Re:", "Fwd:", "[Newsletter]", "📧", "📬"]:
            subject = subject.removeprefix(prefix).strip()

        if not subject:
            continue

        preview = (email.text or "")[:500].strip()

        items.append({
            "title": subject,
            "raw_data": {
                "from_email": email.from_email,
                "from_name": email.from_name,
                "date": email.date.isoformat() if email.date else None,
                "preview": preview,
                "is_newsletter": email.is_newsletter,
                "extraction_method": "naive",
            },
            "tags": ["newsletter_inbox", email.from_name or email.from_email],
        })
    return items


# ─────────────────────────────────────────────────────────────────────
# Weekly ritual ingestion (unchanged)
# ─────────────────────────────────────────────────────────────────────


def ingest_weekly_ritual(
    entries: list[dict],
    narrative_summary: Optional[str] = None,
    project_id: Optional[str] = None,
) -> int:
    """Convert weekly ritual entries into ideas.

    Args:
        entries: List of ritual entry dicts (entry_type, content, tags)
        narrative_summary: Optional narrative synthesis text

    Returns:
        Number of ideas created.
    """
    from status import get_status_service

    items = []
    for entry in entries:
        content = entry.get("content", "").strip()
        if not content:
            continue

        entry_type = entry.get("entry_type", "reflection")
        if entry_type in ("idea", "pivot"):
            items.append({
                "title": content[:120],
                "raw_data": {
                    "entry_type": entry_type,
                    "full_content": content,
                    "tags": entry.get("tags", []),
                },
                "tags": ["weekly_ritual", entry_type],
            })

    if narrative_summary:
        items.append({
            "title": f"Narrative: {narrative_summary[:100]}",
            "raw_data": {
                "entry_type": "narrative_summary",
                "full_content": narrative_summary,
            },
            "tags": ["weekly_ritual", "narrative"],
        })

    if not items:
        return 0

    svc = get_status_service()
    count = svc.bulk_create_ideas(
        source="weekly_ritual",
        items=items,
        project_id=project_id,
    )
    print(f"✅ Ingested {count} ideas from weekly ritual")
    return count


# ─────────────────────────────────────────────────────────────────────
# Level 1: SEO keyword ingestion via DataForSEO
# ─────────────────────────────────────────────────────────────────────


def _get_dfs_client():
    """Lazy-import DFS client to avoid import errors when not configured."""
    from agents.seo.tools.dataforseo_client import DataForSEOClient
    return DataForSEOClient()


def ingest_seo_keywords(
    seed_keywords: list[str],
    max_keywords: int = 50,
    location: str = "us",
    language: str = "en",
    project_id: Optional[str] = None,
    force_standard: bool = False,
) -> int:
    """Discover SEO keyword opportunities via DataForSEO and ingest into Idea Pool.

    Uses keyword_ideas for discovery + keyword_overview for metrics.
    Each idea gets real seo_signals: volume, difficulty, cpc, intent.

    Args:
        seed_keywords: Base keywords to expand (e.g. ["ai content marketing"])
        max_keywords: Max keywords to ingest
        location: Country code (us, fr, uk, de)
        language: Language code (en, fr, de)

    Returns:
        Number of ideas created.
    """
    from status import get_status_service

    try:
        client = _get_dfs_client()
    except (ValueError, ImportError) as e:
        print(f"⚠ DataForSEO not configured: {e}")
        return 0

    print(f"🔍 Discovering keywords for: {seed_keywords}")
    use_standard = force_standard or len(seed_keywords) >= DFS_STANDARD_KEYWORD_SEED_THRESHOLD

    # Step 1: Get keyword ideas from DFS (all seeds in one call — 1 task instead of N)
    all_keywords = []
    seeds = seed_keywords[:5]
    try:
        if use_standard:
            print(f"⏳ Using DataForSEO Standard for keyword ideas: {seeds}")
            ideas = _measure_call(
                "seo_keywords.ideas",
                "standard",
                lambda: client.keyword_ideas_standard(
                    keywords=seeds,
                    location=location,
                    language=language,
                    limit=max_keywords,
                    timeout_seconds=30,
                    poll_interval_seconds=2.0,
                ),
            )
        else:
            ideas = _measure_call(
                "seo_keywords.ideas",
                "live",
                lambda: client.keyword_ideas(
                    keywords=seeds,
                    location=location,
                    language=language,
                    limit=max_keywords,
                ),
            )
        for item in ideas:
            kd = item.get("keyword_data", {})
            ki = kd.get("keyword_info", {})
            kw = kd.get("keyword", "")
            if kw and ki.get("search_volume", 0) > 0:
                all_keywords.append({
                    "keyword": kw,
                    "volume": ki.get("search_volume", 0),
                    "difficulty": ki.get("keyword_difficulty", 0),
                    "cpc": ki.get("cpc", 0),
                    "competition": ki.get("competition"),
                    "intent": ki.get("search_intent"),
                    "monthly_searches": ki.get("monthly_searches", []),
                })
    except Exception as e:
        if use_standard:
            print(f"⚠ keyword_ideas standard failed, falling back to live: {e}")
            try:
                ideas = _measure_call(
                    "seo_keywords.ideas",
                    "live",
                    lambda: client.keyword_ideas(
                        keywords=seeds,
                        location=location,
                        language=language,
                        limit=max_keywords,
                    ),
                )
                for item in ideas:
                    kd = item.get("keyword_data", {})
                    ki = kd.get("keyword_info", {})
                    kw = kd.get("keyword", "")
                    if kw and ki.get("search_volume", 0) > 0:
                        all_keywords.append({
                            "keyword": kw,
                            "volume": ki.get("search_volume", 0),
                            "difficulty": ki.get("keyword_difficulty", 0),
                            "cpc": ki.get("cpc", 0),
                            "competition": ki.get("competition"),
                            "intent": ki.get("search_intent"),
                            "monthly_searches": ki.get("monthly_searches", []),
                        })
            except Exception as live_error:
                print(f"⚠ keyword_ideas failed: {live_error}")
        else:
            print(f"⚠ keyword_ideas failed: {e}")

    # Step 2: Also get keyword suggestions (autocomplete-style) — batched in 1 POST
    suggestion_seeds = seed_keywords[:3]
    try:
        if use_standard:
            print(f"⏳ Using DataForSEO Standard for keyword suggestions: {suggestion_seeds}")
            suggestions = _measure_call(
                "seo_keywords.suggestions",
                "standard",
                lambda: client.keyword_suggestions_batch_standard(
                    keywords=suggestion_seeds,
                    location=location,
                    language=language,
                    limit=20,
                    timeout_seconds=30,
                    poll_interval_seconds=2.0,
                ),
                task_count=len(suggestion_seeds),
            )
        else:
            suggestions = _measure_call(
                "seo_keywords.suggestions",
                "live",
                lambda: client.keyword_suggestions_batch(
                    keywords=suggestion_seeds,
                    location=location,
                    language=language,
                    limit=20,
                ),
                task_count=len(suggestion_seeds),
            )
        for item in suggestions:
            kd = item.get("keyword_data", {})
            ki = kd.get("keyword_info", {})
            kw = kd.get("keyword", "")
            if kw and ki.get("search_volume", 0) > 0:
                all_keywords.append({
                    "keyword": kw,
                    "volume": ki.get("search_volume", 0),
                    "difficulty": ki.get("keyword_difficulty", 0),
                    "cpc": ki.get("cpc", 0),
                    "competition": ki.get("competition"),
                    "intent": ki.get("search_intent"),
                    "keyword_type": "suggestion",
                })
    except Exception as e:
        if use_standard:
            print(f"⚠ keyword_suggestions standard failed, falling back to live: {e}")
            try:
                suggestions = _measure_call(
                    "seo_keywords.suggestions",
                    "live",
                    lambda: client.keyword_suggestions_batch(
                        keywords=suggestion_seeds,
                        location=location,
                        language=language,
                        limit=20,
                    ),
                    task_count=len(suggestion_seeds),
                )
                for item in suggestions:
                    kd = item.get("keyword_data", {})
                    ki = kd.get("keyword_info", {})
                    kw = kd.get("keyword", "")
                    if kw and ki.get("search_volume", 0) > 0:
                        all_keywords.append({
                            "keyword": kw,
                            "volume": ki.get("search_volume", 0),
                            "difficulty": ki.get("keyword_difficulty", 0),
                            "cpc": ki.get("cpc", 0),
                            "competition": ki.get("competition"),
                            "intent": ki.get("search_intent"),
                            "keyword_type": "suggestion",
                        })
            except Exception as live_error:
                print(f"⚠ keyword_suggestions failed: {live_error}")
        else:
            print(f"⚠ keyword_suggestions failed: {e}")

    if not all_keywords:
        print("ℹ️  No keywords discovered")
        return 0

    # Deduplicate by keyword
    seen = set()
    unique_keywords = []
    for kw_data in all_keywords:
        k = kw_data["keyword"].lower()
        if k not in seen:
            seen.add(k)
            unique_keywords.append(kw_data)

    # Sort by opportunity: high volume + low difficulty
    unique_keywords.sort(
        key=lambda x: (x["volume"] / 1000) * ((100 - x["difficulty"]) / 100),
        reverse=True,
    )
    unique_keywords = unique_keywords[:max_keywords]

    print(f"📊 Found {len(unique_keywords)} keywords with real metrics")

    # Step 3: Build idea items with rich seo_signals
    items = []
    for kw_data in unique_keywords:
        opportunity_score = round(
            (kw_data["volume"] / 1000) * ((100 - kw_data["difficulty"]) / 100),
            2,
        )
        items.append({
            "title": kw_data["keyword"],
            "raw_data": {
                "keyword_type": kw_data.get("keyword_type", "idea"),
                "seed_keywords": seed_keywords,
            },
            "seo_signals": {
                "source": "dataforseo",
                "volume": kw_data["volume"],
                "difficulty": kw_data["difficulty"],
                "cpc": kw_data["cpc"],
                "competition": kw_data["competition"],
                "intent": kw_data["intent"],
                "opportunity_score": opportunity_score,
            },
            "priority_score": opportunity_score,
            "tags": _build_seo_tags(kw_data),
        })

    svc = get_status_service()
    count = svc.bulk_create_ideas(
        source="seo_keywords",
        items=items,
        project_id=project_id,
    )
    _log_pipeline_metrics("seo_keywords.ideas")
    _log_pipeline_metrics("seo_keywords.suggestions")
    print(f"✅ Ingested {count} SEO keyword ideas (DataForSEO)")
    return count


def _build_seo_tags(kw_data: dict) -> list[str]:
    """Build tags from keyword data."""
    tags = ["seo_keyword"]
    intent = kw_data.get("intent")
    if intent:
        tags.append(f"intent:{intent.lower()}" if isinstance(intent, str) else "intent:mixed")
    if kw_data.get("difficulty", 100) < 30:
        tags.append("low_difficulty")
    if kw_data.get("volume", 0) > 5000:
        tags.append("high_volume")
    if kw_data.get("keyword_type") == "suggestion":
        tags.append("autocomplete")
    return tags


# ─────────────────────────────────────────────────────────────────────
# Level 2: Idea enrichment — batch-enrich raw ideas with DFS data
# ─────────────────────────────────────────────────────────────────────


def enrich_ideas(
    batch_size: int = 50,
    location: str = "us",
    language: str = "en",
    project_id: Optional[str] = None,
    force_standard: bool = False,
) -> int:
    """Enrich raw ideas in the Idea Pool with real SEO metrics from DataForSEO.

    Takes ideas with status="raw", batches them through keyword_overview,
    updates seo_signals + priority_score, and transitions to status="enriched".

    Args:
        batch_size: Max ideas to enrich per run
        location: Country code
        language: Language code

    Returns:
        Number of ideas enriched.
    """
    from status import get_status_service

    svc = get_status_service()

    # Get raw ideas that need enrichment
    ideas, total = svc.list_ideas(status="raw", limit=batch_size, project_id=project_id)

    if not ideas:
        print("ℹ️  No raw ideas to enrich")
        return 0

    print(f"🔬 Enriching {len(ideas)} raw ideas (of {total} total)")

    try:
        client = _get_dfs_client()
    except (ValueError, ImportError) as e:
        print(f"⚠ DataForSEO not configured: {e}")
        return 0

    # Batch keywords for overview (DFS supports up to 1000 per call)
    keywords = [idea["title"] for idea in ideas]

    use_standard = force_standard or len(keywords) >= DFS_STANDARD_ENRICH_THRESHOLD
    try:
        if use_standard:
            print(f"⏳ Using DataForSEO Standard mode for {len(keywords)} keyword overviews")
            overview_results = _measure_call(
                "enrich.keyword_overview",
                "standard",
                lambda: client.keyword_overview_standard(
                    keywords=keywords,
                    location=location,
                    language=language,
                    timeout_seconds=30,
                    poll_interval_seconds=2.0,
                ),
            )
        else:
            overview_results = _measure_call(
                "enrich.keyword_overview",
                "live",
                lambda: client.keyword_overview(
                    keywords=keywords,
                    location=location,
                    language=language,
                ),
            )
    except Exception as e:
        if use_standard:
            print(f"⚠ keyword_overview standard failed, falling back to live: {e}")
            try:
                overview_results = _measure_call(
                    "enrich.keyword_overview",
                    "live",
                    lambda: client.keyword_overview(
                        keywords=keywords,
                        location=location,
                        language=language,
                    ),
                )
            except Exception as live_error:
                print(f"⚠ keyword_overview failed: {live_error}")
                return 0
        else:
            print(f"⚠ keyword_overview failed: {e}")
            return 0

    # Build lookup: keyword → metrics
    metrics_map = {}
    for item in overview_results:
        kd = item.get("keyword_data", {})
        ki = kd.get("keyword_info", {})
        kw = kd.get("keyword", "").lower()
        if kw:
            metrics_map[kw] = {
                "volume": ki.get("search_volume", 0),
                "difficulty": ki.get("keyword_difficulty", 0),
                "cpc": ki.get("cpc", 0),
                "competition": ki.get("competition"),
                "intent": ki.get("search_intent"),
                "monthly_searches": ki.get("monthly_searches", []),
            }

    # Update each idea
    enriched_count = 0
    for idea in ideas:
        title_lower = idea["title"].lower()
        metrics = metrics_map.get(title_lower)

        if not metrics:
            # No DFS data for this keyword — still mark as enriched with empty signals
            svc.update_idea(
                idea["id"],
                seo_signals={"source": "dataforseo", "no_data": True},
                priority_score=0.0,
                status="enriched",
            )
            enriched_count += 1
            continue

        volume = metrics["volume"] or 0
        difficulty = metrics["difficulty"] or 0
        opportunity = round(
            (volume / 1000) * ((100 - difficulty) / 100), 2
        ) if volume > 0 else 0.0

        seo_signals = {
            "source": "dataforseo",
            "volume": volume,
            "difficulty": difficulty,
            "cpc": metrics["cpc"],
            "competition": metrics["competition"],
            "intent": metrics["intent"],
            "opportunity_score": opportunity,
        }

        # Merge with existing seo_signals if any
        existing = idea.get("seo_signals") or {}
        if isinstance(existing, dict):
            existing.update(seo_signals)
            seo_signals = existing

        svc.update_idea(
            idea["id"],
            seo_signals=seo_signals,
            priority_score=opportunity,
            status="enriched",
            tags=_build_seo_tags(metrics),
        )
    enriched_count += 1
    print(f"✅ Enriched {enriched_count} ideas with DataForSEO metrics")
    _log_pipeline_metrics("enrich.keyword_overview")
    return enriched_count


# ─────────────────────────────────────────────────────────────────────
# Level 3: Competitor intelligence feed
# ─────────────────────────────────────────────────────────────────────


def ingest_competitor_watch(
    target_domain: str,
    competitor_domains: list[str],
    max_gaps: int = 50,
    location: str = "us",
    language: str = "en",
    project_id: Optional[str] = None,
    force_standard: bool = False,
) -> int:
    """Analyze competitor domains via DataForSEO and ingest content gaps as ideas.

    Uses domain_intersection to find keywords where competitors rank but you don't.
    Uses ranked_keywords to discover high-value keywords competitors target.

    Args:
        target_domain: Your domain (e.g. "mysite.com")
        competitor_domains: List of competitor domains
        max_gaps: Max gap ideas to ingest
        location: Country code
        language: Language code

    Returns:
        Number of ideas created.
    """
    from status import get_status_service

    try:
        client = _get_dfs_client()
    except (ValueError, ImportError) as e:
        print(f"⚠ DataForSEO not configured: {e}")
        return 0

    print(f"🔎 Analyzing competitors: {competitor_domains}")
    use_standard_domain = force_standard or max_gaps >= DFS_STANDARD_COMPETITOR_RANKED_LIMIT
    use_standard_ranked = force_standard or max_gaps >= DFS_STANDARD_COMPETITOR_RANKED_LIMIT
    items = []

    # Strategy 1: Domain intersection — find gaps
    if target_domain:
        targets = {"1": target_domain}
        for i, comp in enumerate(competitor_domains[:19], 2):
            targets[str(i)] = comp

        intersection = []
        try:
            if use_standard_domain:
                print("⏳ Using DataForSEO Standard mode for competitor domain intersection")
                intersection = _measure_call(
                    "competitor.domain_intersection",
                    "standard",
                    lambda: client.domain_intersection_standard(
                        targets=targets,
                        location=location,
                        language=language,
                        limit=max_gaps * 2,
                        timeout_seconds=30,
                        poll_interval_seconds=2.0,
                    ),
                )
            else:
                intersection = _measure_call(
                    "competitor.domain_intersection",
                    "live",
                    lambda: client.domain_intersection(
                        targets=targets,
                        location=location,
                        language=language,
                        limit=max_gaps * 2,
                    ),
                )
        except Exception as e:
            if use_standard_domain:
                print(f"⚠ Domain intersection standard failed, falling back to live: {e}")
                try:
                    intersection = _measure_call(
                        "competitor.domain_intersection",
                        "live",
                        lambda: client.domain_intersection(
                            targets=targets,
                            location=location,
                            language=language,
                            limit=max_gaps * 2,
                        ),
                    )
                except Exception as live_error:
                    print(f"⚠ Domain intersection failed: {live_error}")
                    intersection = []
            else:
                print(f"⚠ Domain intersection failed: {e}")
                intersection = []

        for item in intersection:
            kd = item.get("keyword_data", {})
            ki = kd.get("keyword_info", {})
            kw = kd.get("keyword", "")
            intersections = item.get("intersection_result", {})

            # Target position
            target_pos = intersections.get("1")
            target_rank = target_pos.get("rank_absolute") if target_pos else None

            # Only gaps: target doesn't rank (or ranks > 50)
            if target_rank is not None and target_rank <= 50:
                continue

            volume = ki.get("search_volume", 0)
            difficulty = ki.get("keyword_difficulty", 0)
            if volume < 10:
                continue

            # Which competitors rank for this?
            ranking_comps = []
            for key, val in intersections.items():
                if key == "1" or not val:
                    continue
                idx = int(key) - 2
                if 0 <= idx < len(competitor_domains):
                    pos = val.get("rank_absolute", 100)
                    ranking_comps.append({
                        "domain": competitor_domains[idx],
                        "position": pos,
                    })

            opportunity = round(
                (volume / 1000) * ((100 - difficulty) / 100), 2
            )

            items.append({
                "title": kw,
                "raw_data": {
                    "gap_type": "domain_intersection",
                    "target_domain": target_domain,
                    "competitors_ranking": ranking_comps,
                    "target_rank": target_rank,
                },
                "seo_signals": {
                    "source": "dataforseo",
                    "volume": volume,
                    "difficulty": difficulty,
                    "cpc": ki.get("cpc", 0),
                    "intent": ki.get("search_intent"),
                    "opportunity_score": opportunity,
                },
                "priority_score": opportunity,
                "tags": ["competitor_gap", f"vs:{competitor_domains[0]}"],
            })

        print(f"  Found {len(items)} gaps from domain intersection")
    # Strategy 2: Competitor ranked keywords — discover what they target
    for comp_domain in competitor_domains[:3]:
        try:
            if use_standard_ranked:
                print(f"⏳ Using DataForSEO Standard mode for ranked keywords: {comp_domain}")
                ranked = _measure_call(
                    "competitor.ranked_keywords",
                    "standard",
                    lambda: client.ranked_keywords_standard(
                        target=comp_domain,
                        location=location,
                        language=language,
                        limit=DFS_STANDARD_COMPETITOR_RANKED_LIMIT,
                        timeout_seconds=30,
                        poll_interval_seconds=2.0,
                    ),
                )
            else:
                ranked = _measure_call(
                    "competitor.ranked_keywords",
                    "live",
                    lambda: client.ranked_keywords(
                        target=comp_domain,
                        location=location,
                        language=language,
                        limit=DFS_STANDARD_COMPETITOR_RANKED_LIMIT,
                    ),
                )

            for item in ranked:
                kd = item.get("keyword_data", {})
                ki = kd.get("keyword_info", {})
                kw = kd.get("keyword", "")
                volume = ki.get("search_volume", 0)
                difficulty = ki.get("keyword_difficulty", 0)
                rank_pos = item.get("ranked_serp_element", {}).get("serp_item", {}).get("rank_absolute", 0)

                if volume < 50 or not kw:
                    continue

                if any(i["title"].lower() == kw.lower() for i in items):
                    continue

                opportunity = round(
                    (volume / 1000) * ((100 - difficulty) / 100), 2
                )

                items.append({
                    "title": kw,
                    "raw_data": {
                        "gap_type": "competitor_ranked",
                        "competitor_domain": comp_domain,
                        "competitor_position": rank_pos,
                    },
                    "seo_signals": {
                        "source": "dataforseo",
                        "volume": volume,
                        "difficulty": difficulty,
                        "cpc": ki.get("cpc", 0),
                        "intent": ki.get("search_intent"),
                        "opportunity_score": opportunity,
                    },
                    "priority_score": opportunity,
                    "tags": ["competitor_keyword", f"from:{comp_domain}"],
                })

            print(f"  Found keywords from {comp_domain}")

        except Exception as e:
            if use_standard_ranked:
                print(f"⚠ ranked_keywords standard failed for {comp_domain}, falling back to live: {e}")
                try:
                    ranked = _measure_call(
                        "competitor.ranked_keywords",
                        "live",
                        lambda: client.ranked_keywords(
                            target=comp_domain,
                            location=location,
                            language=language,
                            limit=DFS_STANDARD_COMPETITOR_RANKED_LIMIT,
                        ),
                    )
                except Exception as live_error:
                    print(f"⚠ ranked_keywords failed for {comp_domain}: {live_error}")
                    continue
            else:
                print(f"⚠ ranked_keywords failed for {comp_domain}: {e}")
                continue

            for item in ranked:
                kd = item.get("keyword_data", {})
                ki = kd.get("keyword_info", {})
                kw = kd.get("keyword", "")
                volume = ki.get("search_volume", 0)
                difficulty = ki.get("keyword_difficulty", 0)
                rank_pos = item.get("ranked_serp_element", {}).get("serp_item", {}).get("rank_absolute", 0)

                if volume < 50 or not kw:
                    continue

                if any(i["title"].lower() == kw.lower() for i in items):
                    continue

                opportunity = round(
                    (volume / 1000) * ((100 - difficulty) / 100), 2
                )

                items.append({
                    "title": kw,
                    "raw_data": {
                        "gap_type": "competitor_ranked",
                        "competitor_domain": comp_domain,
                        "competitor_position": rank_pos,
                    },
                    "seo_signals": {
                        "source": "dataforseo",
                        "volume": volume,
                        "difficulty": difficulty,
                        "cpc": ki.get("cpc", 0),
                        "intent": ki.get("search_intent"),
                        "opportunity_score": opportunity,
                    },
                    "priority_score": opportunity,
                    "tags": ["competitor_keyword", f"from:{comp_domain}"],
                })
    if not items:
        print("ℹ️  No competitor gaps found")
        return 0

    # Deduplicate and sort by opportunity
    seen = set()
    unique_items = []
    for item in items:
        k = item["title"].lower()
        if k not in seen:
            seen.add(k)
            unique_items.append(item)

    unique_items.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    unique_items = unique_items[:max_gaps]

    svc = get_status_service()
    count = svc.bulk_create_ideas(
        source="competitor_watch",
        items=unique_items,
        project_id=project_id,
    )
    print(f"✅ Ingested {count} competitor intelligence ideas")
    return count


# ─────────────────────────────────────────────────────────────────────
# Level 4: SERP position tracking post-publication
# ─────────────────────────────────────────────────────────────────────


def track_serp_positions(
    location: str = "us",
    language: str = "en",
    project_id: Optional[str] = None,
) -> int:
    """Track SERP positions for published content.

    Finds published content with an seo_keyword in metadata,
    checks current Google ranking via DFS SERP, and stores
    position history in content metadata.

    Returns:
        Number of content items tracked.
    """
    from status import get_status_service
    from datetime import datetime

    svc = get_status_service()

    # Get published content
    published = svc.list_content(status="published", project_id=project_id, limit=100)

    if not published:
        print("ℹ️  No published content to track")
        return 0

    # Filter to items that have a target keyword
    trackable = []
    for item in published:
        meta = item.metadata or {}
        keyword = meta.get("seo_keyword") or meta.get("target_keyword")
        target_url = item.target_url
        if keyword and target_url:
            trackable.append({
                "content_id": item.id,
                "keyword": keyword,
                "target_url": target_url,
                "domain": _extract_domain(target_url),
                "metadata": meta,
            })

    if not trackable:
        print("ℹ️  No published content with SEO keywords to track")
        return 0

    print(f"📈 Tracking SERP positions for {len(trackable)} items")

    try:
        client = _get_dfs_client()
    except (ValueError, ImportError) as e:
        print(f"⚠ DataForSEO not configured: {e}")
        return 0

    tracked = 0
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Submit all SERP tasks in one batch via Standard queue ($0.05 vs $0.075/task)
    keywords_to_track = [item["keyword"] for item in trackable]
    try:
        task_ids = client.serp_google_organic_batch_task_post(
            keywords=keywords_to_track,
            location=location,
            language=language,
            depth=100,
        )
    except Exception as e:
        print(f"⚠ SERP batch submission failed: {e}")
        return 0

    task_map = dict(zip(task_ids, trackable))
    print(f"  Submitted {len(task_ids)} SERP tasks (Standard queue)")
    time.sleep(5)  # Initial wait for Standard queue processing

    for task_id, item in task_map.items():
        try:
            serp_results = client.wait_for_task_results(
                f"serp/google/organic/task_get/advanced/{task_id}",
                timeout_seconds=30,
                poll_interval_seconds=3.0,
            )
            serp = serp_results[0] if serp_results else {}

            # Find our position
            position = None
            our_url = None
            domain = item["domain"]

            for serp_item in serp.get("items", []):
                if serp_item.get("type") != "organic":
                    continue
                serp_domain = serp_item.get("domain", "")
                if domain in serp_domain or serp_domain in domain:
                    position = serp_item.get("rank_absolute")
                    our_url = serp_item.get("url")
                    break

            # Build position history
            meta = item["metadata"].copy()
            history = meta.get("serp_history", [])
            history.append({
                "date": today,
                "position": position,
                "url_found": our_url,
                "keyword": item["keyword"],
            })
            history = history[-90:]
            meta["serp_history"] = history
            meta["last_serp_check"] = today
            meta["current_position"] = position

            svc.update_content(item["content_id"], metadata=meta)
            tracked += 1

            status = f"#{position}" if position else "not ranked"
            print(f"  '{item['keyword']}' → {status}")

        except Exception as e:
            print(f"⚠ SERP check failed for '{item['keyword']}': {e}")

    print(f"✅ Tracked SERP positions for {tracked} items")

    # Evaluate SERP data and create refresh ideas for underperforming content
    try:
        refresh_count = _evaluate_serp_feedback(project_id=project_id)
        if refresh_count:
            print(f"🔄 Created {refresh_count} SERP feedback refresh ideas")
    except Exception as e:
        print(f"⚠ SERP feedback evaluation failed (non-critical): {e}")

    return tracked


# ─────────────────────────────────────────────────────────────────────
# SERP feedback loop — create refresh ideas for underperforming content
# ─────────────────────────────────────────────────────────────────────


def _evaluate_serp_feedback(
    project_id: Optional[str] = None,
) -> int:
    """Evaluate SERP tracking data and create refresh ideas for underperforming content.

    Triggers:
      - never_ranked:      published > 3 checks, never indexed → priority 30
      - ranking_declined:  was top 10, dropped below 20 → priority 70
      - stuck_page_two:    positions 11-20 for 3+ consecutive checks → priority 50

    Returns:
        Number of refresh ideas created.
    """
    from status import get_status_service

    svc = get_status_service()
    published = svc.list_content(status="published", project_id=project_id, limit=100)

    if not published:
        return 0

    refresh_items = []
    for item in published:
        meta = item.metadata or {}
        keyword = meta.get("seo_keyword") or meta.get("target_keyword")
        history = meta.get("serp_history", [])
        current_pos = meta.get("current_position")

        if not keyword or len(history) < 2:
            continue

        reason = None
        priority = 0.0

        # Trigger 1: Never ranked after 3+ checks
        if current_pos is None and len(history) >= 3:
            if all(h.get("position") is None for h in history):
                reason = "never_ranked"
                priority = 30.0

        # Trigger 2: Significant decline (was top 10, now below 20)
        if not reason and len(history) >= 5:
            older_positions = [h["position"] for h in history[:-3] if h.get("position")]
            recent_positions = [h["position"] for h in history[-3:] if h.get("position")]
            if older_positions and recent_positions:
                best_old = min(older_positions)
                worst_recent = max(recent_positions)
                if best_old <= 10 and worst_recent > 20:
                    reason = "ranking_declined"
                    priority = 70.0

        # Trigger 3: Stuck at positions 11-20 (page 2) for 3+ checks
        if not reason and len(history) >= 3:
            last_3 = [h.get("position") for h in history[-3:]]
            if all(p is not None and 11 <= p <= 20 for p in last_3):
                reason = "stuck_page_two"
                priority = 50.0

        if reason:
            refresh_items.append({
                "title": f"Refresh: {keyword}",
                "raw_data": {
                    "refresh_reason": reason,
                    "content_id": item.id,
                    "content_title": item.title,
                    "target_url": item.target_url,
                    "current_position": current_pos,
                    "serp_history_summary": [
                        {"date": h["date"], "position": h.get("position")}
                        for h in history[-5:]
                    ],
                },
                "seo_signals": meta.get("seo_signals") or {
                    "keyword": keyword,
                    "current_position": current_pos,
                },
                "priority_score": priority,
                "tags": ["serp_feedback", reason, f"content:{item.id[:8]}"],
            })

    if not refresh_items:
        return 0

    # Deduplicate: don't create refresh idea if one already exists for same content
    existing_refresh, _ = svc.list_ideas(
        source="serp_feedback",
        status="raw",
        project_id=project_id,
        limit=200,
    )
    existing_content_ids = set()
    for existing in existing_refresh:
        cid = (existing.get("raw_data") or {}).get("content_id")
        if cid:
            existing_content_ids.add(cid)

    new_items = [
        item for item in refresh_items
        if item["raw_data"]["content_id"] not in existing_content_ids
    ]

    if not new_items:
        return 0

    count = svc.bulk_create_ideas(
        source="serp_feedback",
        items=new_items,
        project_id=project_id,
    )
    return count


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "")

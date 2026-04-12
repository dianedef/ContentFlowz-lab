"""
Scheduler Service - Background task that runs scheduled jobs.

Runs as an asyncio background task inside FastAPI's lifespan.
Checks every 60s for jobs whose next_run_at <= now and dispatches them.
Also auto-transitions scheduled content whose scheduledFor has passed.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from status.service import get_status_service, ContentNotFoundError

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Background scheduler that processes due jobs and auto-publishes
    scheduled content.
    """

    def __init__(self):
        self._running = False
        self._check_interval = 60  # seconds

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        print("📅 Scheduler service started (checking every 60s)")

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                print(f"⚠ Scheduler tick error: {e}")

            await asyncio.sleep(self._check_interval)

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        print("📅 Scheduler service stopped")

    async def _tick(self) -> None:
        """Single scheduler tick: process due jobs + auto-transition scheduled content."""
        svc = get_status_service()

        # 1. Process due schedule jobs
        due_jobs = svc.get_due_jobs()
        for job in due_jobs:
            await self._dispatch_job(job)

        # 2. Auto-transition scheduled content whose scheduledFor has passed
        await self._auto_transition_scheduled(svc)

        # 3. Reconcile frequency config with schedule jobs (every 10 ticks ~ 10 min)
        if not hasattr(self, "_reconcile_counter"):
            self._reconcile_counter = 0
        self._reconcile_counter += 1
        if self._reconcile_counter >= 10:
            self._reconcile_counter = 0
            await self._reconcile_frequency_jobs(svc)

    _DFS_JOB_TYPES = {"ingest_seo", "enrich_ideas", "ingest_competitors", "track_serp"}

    async def _dispatch_job(self, job: dict) -> None:
        """Dispatch a due job to the appropriate robot."""
        svc = get_status_service()
        job_id = job["id"]
        job_type = job["job_type"]

        print(f"📅 Dispatching job {job_id} (type={job_type})")

        # Mark as running
        svc.update_schedule_job(
            job_id,
            last_run_at=datetime.utcnow().isoformat(),
            last_run_status="running",
        )

        # Reset DFS metrics before DFS jobs so we capture only this job's costs
        if job_type in self._DFS_JOB_TYPES:
            try:
                from agents.sources.ingest import flush_metrics
                flush_metrics()
            except ImportError:
                pass

        try:
            if job_type == "newsletter":
                await self._run_newsletter_job(job)
            elif job_type == "seo":
                await self._run_seo_job(job)
            elif job_type == "article":
                await self._run_article_job(job)
            elif job_type == "short":
                await self._run_short_job(job)
            elif job_type == "social":
                await self._run_social_job(job)
            elif job_type == "ingest_newsletters":
                await self._run_ingest_newsletters(job)
            elif job_type == "ingest_seo":
                await self._run_ingest_seo(job)
            elif job_type == "enrich_ideas":
                await self._run_enrich_ideas(job)
            elif job_type == "ingest_competitors":
                await self._run_ingest_competitors(job)
            elif job_type == "track_serp":
                await self._run_track_serp(job)
            elif job_type == "ingest_social":
                await self._run_ingest_social(job)
            else:
                print(f"⚠ Unknown job type: {job_type}")

            # Persist DFS API costs for this job
            self._persist_dfs_costs(job)

            # Mark completed and calculate next run
            next_run = self._calculate_next_run(job)
            svc.update_schedule_job(
                job_id,
                last_run_status="completed",
                next_run_at=next_run,
            )
            print(f"✅ Job {job_id} completed. Next run: {next_run}")

        except Exception as e:
            # Still capture costs even on failure
            self._persist_dfs_costs(job)

            print(f"❌ Job {job_id} failed: {e}")
            next_run = self._calculate_next_run(job)
            svc.update_schedule_job(
                job_id,
                last_run_status="failed",
                next_run_at=next_run,
            )

    def _persist_dfs_costs(self, job: dict) -> None:
        """Flush in-memory DFS metrics and persist to cost log DB."""
        if job["job_type"] not in self._DFS_JOB_TYPES:
            return
        try:
            from agents.sources.ingest import flush_metrics
            from status.cost_tracker import log_job_costs

            metrics = flush_metrics()
            if metrics:
                log_job_costs(
                    job_id=job["id"],
                    project_id=job.get("project_id"),
                    job_type=job["job_type"],
                    metrics=metrics,
                )
        except Exception as e:
            logger.warning("Failed to persist DFS costs for job %s: %s", job["id"], e)

    async def _run_newsletter_job(self, job: dict) -> None:
        """Run a newsletter generation job."""
        config = job.get("configuration", {})
        generator_id = job.get("generator_id")

        # Import and call the newsletter agent
        try:
            from agents.newsletter.newsletter_agent import generate_newsletter

            result = await asyncio.to_thread(
                generate_newsletter,
                topics=config.get("topics", []),
                target_audience=config.get("target_audience", "general"),
                tone=config.get("tone", "professional"),
                max_sections=config.get("max_sections", 5),
            )

            if result:
                # Create a content record for the generated newsletter
                svc = get_status_service()
                record = svc.create_content(
                    title=result.get("subject_line", "Scheduled Newsletter"),
                    content_type="newsletter",
                    source_robot="newsletter",
                    status="generated",
                    project_id=job.get("project_id"),
                    content_preview=str(result.get("subject_line", ""))[:500],
                    metadata={
                        "generator_id": generator_id,
                        "scheduled_job_id": job["id"],
                    },
                )
                # Save body
                html_content = result.get("html", "")
                if html_content:
                    svc.save_content_body(
                        record.id,
                        html_content,
                        edited_by="scheduler",
                        edit_note="Scheduled generation",
                    )
                # Transition to pending_review
                svc.transition(record.id, "pending_review", "scheduler")

        except ImportError:
            print("⚠ Newsletter agent not available for scheduled generation")
        except Exception as e:
            raise RuntimeError(f"Newsletter generation failed: {e}") from e

    async def _run_seo_job(self, job: dict) -> None:
        """Run an SEO content generation job using the SEO Crew pipeline."""
        config = job.get("configuration", {})

        try:
            from agents.seo.seo_crew import SEOContentCrew

            crew = SEOContentCrew()
            result = await asyncio.to_thread(
                crew.generate_content,
                target_keyword=config.get("target_keyword", ""),
                competitor_domains=config.get("competitor_domains"),
                sector=config.get("sector"),
                word_count=config.get("word_count", 2500),
            )
            print(f"✅ SEO job {job['id']} completed: {len(str(result))} chars output")

        except ImportError:
            print("⚠ SEO crew not available for scheduled generation")
        except Exception as e:
            raise RuntimeError(f"SEO generation failed: {e}") from e

    async def _is_idea_pool_enabled(self, job: dict) -> bool:
        """Check if idea pool curation is enabled for the user who owns this job."""
        user_id = job.get("user_id")
        if not user_id or user_id == "system":
            return False
        try:
            from api.services.user_data_store import user_data_store
            settings = await user_data_store.get_user_settings(user_id)
            robot_settings = settings.get("robotSettings") or {}
            return bool(robot_settings.get("ideaPoolEnabled", False))
        except Exception:
            return False

    async def _run_article_job(self, job: dict) -> None:
        """Run an article generation job. Picks the best idea from the pool."""
        config = job.get("configuration", {})
        svc = get_status_service()

        idea_pool_enabled = await self._is_idea_pool_enabled(job)

        idea = None
        angle = config.get("angle", {})

        if idea_pool_enabled:
            # CURATION MODE: require an enriched, user-curated idea
            try:
                ideas, _ = svc.list_ideas(
                    status="enriched", min_score=50.0,
                    project_id=job.get("project_id"),
                    user_id=job.get("user_id"),
                    limit=1,
                )
            except Exception:
                ideas = []
            if not ideas and not angle:
                print(f"ℹ️  Article job {job['id']}: idea pool enabled but no curated ideas, skipping")
                return
            if ideas and not angle:
                idea = ideas[0]
                angle = {
                    "title": idea["title"],
                    "hook": idea.get("raw_data", {}).get("hook", idea["title"]),
                    "angle": idea.get("raw_data", {}).get("angle", ""),
                    "pain_point_addressed": "",
                    "seo_keyword": idea["title"],
                    "source": idea.get("source"),
                    "source_idea_ids": [idea["id"]],
                }
                svc.update_idea(idea["id"], status="used")
        else:
            # AUTO MODE: best-effort from pool, same as previous behavior
            try:
                ideas, _ = svc.list_ideas(status="enriched", min_score=50.0, limit=1)
            except Exception:
                ideas = []
            if ideas and not angle:
                idea = ideas[0]
                angle = {
                    "title": idea["title"],
                    "hook": idea.get("raw_data", {}).get("hook", idea["title"]),
                    "angle": idea.get("raw_data", {}).get("angle", ""),
                    "pain_point_addressed": "",
                    "seo_keyword": idea["title"],
                    "source": idea.get("source"),
                    "source_idea_ids": [idea["id"]],
                }
                svc.update_idea(idea["id"], status="used")

        # Pre-generation dedup check
        if angle.get("title"):
            try:
                from utils.dedup import check_content_duplicate
                duplicate = check_content_duplicate(
                    title=angle["title"],
                    project_id=job.get("project_id"),
                )
                if duplicate:
                    print(f"⏭ Skipping duplicate: '{duplicate['title']}' already exists (status={duplicate['status']})")
                    return
            except Exception as e:
                print(f"⚠ Dedup check failed (proceeding): {e}")

        # Extract competitor domains from idea data (competitor_watch ideas)
        idea_competitor_domains = None
        if idea:
            raw = idea.get("raw_data", {})
            rankings = raw.get("competitors_ranking", [])
            if rankings:
                idea_competitor_domains = [r["domain"] for r in rankings if r.get("domain")]
            elif raw.get("competitor_domain"):
                idea_competitor_domains = [raw["competitor_domain"]]

        # Optional: Run the Angle Strategist for richer angles
        if idea and config.get("use_angle_strategist", False):
            try:
                from agents.psychology.angle_strategist import run_angle_generation

                seo_signals_list = []
                if idea.get("seo_signals"):
                    seo_signals_list.append({"keyword": idea["title"], **idea["seo_signals"]})

                trending_list = []
                if idea.get("trending_signals"):
                    trending_list.append(idea["trending_signals"])

                angle_result = await asyncio.to_thread(
                    run_angle_generation,
                    creator_voice=config.get("creator_voice", {}),
                    creator_positioning=config.get("creator_positioning", {}),
                    narrative_summary=config.get("narrative_summary"),
                    persona_data=config.get("persona_data", {}),
                    content_type="article",
                    count=1,
                    seo_signals=seo_signals_list or None,
                    trending_signals=trending_list or None,
                )

                generated_angles = angle_result.get("angles", [])
                if generated_angles:
                    best = generated_angles[0]
                    angle = {
                        "title": best.get("title", idea["title"]),
                        "hook": best.get("hook", ""),
                        "angle": best.get("angle", ""),
                        "pain_point_addressed": best.get("pain_point_addressed", ""),
                        "seo_keyword": best.get("seo_keyword", idea["title"]),
                        "content_type": best.get("content_type", "article"),
                        "narrative_thread": best.get("narrative_thread", ""),
                        "confidence": best.get("confidence", 70),
                    }
                    print(f"🎯 Angle Strategist produced: {angle['title']}")

            except ImportError:
                print("ℹ️  Angle Strategist not available, using direct idea")
            except Exception as e:
                print(f"⚠ Angle Strategist failed (falling back to direct idea): {e}")

        if not angle.get("title"):
            print(f"ℹ️  Article job {job['id']}: no angle or enriched idea available, skipping")
            return

        target_keyword = angle.get("seo_keyword", angle.get("title", ""))

        try:
            from agents.seo.seo_crew import SEOContentCrew

            crew = SEOContentCrew()
            result = await asyncio.to_thread(
                crew.generate_content,
                target_keyword=target_keyword,
                competitor_domains=idea_competitor_domains or config.get("competitor_domains"),
                sector=config.get("sector"),
                business_goals=config.get("business_goals"),
                brand_voice=config.get("brand_voice"),
                target_audience=config.get("target_audience"),
                word_count=config.get("word_count", 2500),
                tone=config.get("tone", "professional"),
            )

            # Create content record with enriched metadata
            body = result.get("outputs", {}).get("article", str(result))
            record = svc.create_content(
                title=angle.get("title", "Scheduled Article"),
                content_type="article",
                source_robot="seo",
                status="generated",
                project_id=job.get("project_id"),
                content_preview=body[:500] if body else "",
                metadata={
                    "scheduled_job_id": job["id"],
                    "angle": angle,
                    "target_keyword": target_keyword,
                    "seo_signals": idea.get("seo_signals") if idea else None,
                    "source_idea_id": idea["id"] if idea else None,
                },
            )
            if body:
                svc.save_content_body(record.id, body, edited_by="scheduler")
            svc.transition(record.id, "pending_review", "scheduler")

        except ImportError:
            print("⚠ SEO crew not available for article generation")
        except Exception as e:
            raise RuntimeError(f"Article generation failed: {e}") from e

    async def _run_short_job(self, job: dict) -> None:
        """Run a short-form content generation job."""
        config = job.get("configuration", {})

        try:
            from agents.short.short_crew import ShortContentCrew

            crew = ShortContentCrew()
            result = await asyncio.to_thread(
                crew.generate_short,
                angle=config.get("angle", {"title": "Trending topic", "hook": ""}),
                creator_voice=config.get("creator_voice", {}),
                platform=config.get("platform", "tiktok"),
                max_duration=config.get("max_duration", 60),
                project_id=job.get("project_id"),
            )
            print(f"✅ Short job {job['id']} completed")

        except ImportError:
            print("⚠ Short crew not available for scheduled generation")
        except Exception as e:
            raise RuntimeError(f"Short generation failed: {e}") from e

    async def _run_social_job(self, job: dict) -> None:
        """Run a social post generation job."""
        config = job.get("configuration", {})

        try:
            from agents.social.social_crew import SocialPostCrew

            crew = SocialPostCrew()
            result = await asyncio.to_thread(
                crew.generate_social_post,
                angle=config.get("angle", {"title": "Daily insight", "hook": ""}),
                creator_voice=config.get("creator_voice", {}),
                platforms=config.get("platforms", ["twitter", "linkedin"]),
                project_id=job.get("project_id"),
            )
            print(f"✅ Social job {job['id']} completed")

        except ImportError:
            print("⚠ Social crew not available for scheduled generation")
        except Exception as e:
            raise RuntimeError(f"Social generation failed: {e}") from e

    async def _run_ingest_newsletters(self, job: dict) -> None:
        """Ingest newsletter emails into the Idea Pool with LLM extraction."""
        config = job.get("configuration", {})
        user_id = job.get("user_id")
        project_id = job.get("project_id")

        # Pre-fetch persona/niche context (async) for LLM scoring
        persona_context = ""
        if user_id and user_id != "system":
            try:
                from api.services.user_data_store import user_data_store
                from agents.sources.newsletter_extractor import format_persona_context

                personas = await user_data_store.list_personas(user_id, project_id)
                creator = await user_data_store.get_creator_profile(user_id, project_id)
                persona_context = format_persona_context(personas, creator)
            except Exception as e:
                print(f"⚠ Could not load persona context: {e}")

        try:
            from agents.sources.ingest import ingest_newsletter_inbox

            count = await asyncio.to_thread(
                ingest_newsletter_inbox,
                days_back=config.get("days_back", 7),
                folder=config.get("folder", "Newsletters"),
                max_results=config.get("max_results", 20),
                project_id=project_id,
                persona_context=persona_context,
                archive_folder=config.get("archive_folder", "CONTENTFLOW_DONE"),
            )
            print(f"✅ Newsletter ingestion: {count} ideas")

        except Exception as e:
            raise RuntimeError(f"Newsletter ingestion failed: {e}") from e

    async def _run_ingest_seo(self, job: dict) -> None:
        """Generate SEO keywords and ingest into the Idea Pool."""
        config = job.get("configuration", {})
        seed_keywords = config.get("seed_keywords", [])

        if not seed_keywords:
            print("ℹ️  No seed keywords configured for SEO ingestion, skipping")
            return

        try:
            from agents.sources.ingest import (
                DFS_STANDARD_KEYWORD_SEED_THRESHOLD,
                ingest_seo_keywords,
            )

            # Scheduler jobs always use Standard queue ($0.05 vs $0.075/task)
            force_standard = config.get("force_standard", True)
            logger.info(
                "ingest_seo job %s force_standard=%s seed_count=%d",
                job.get("id"),
                force_standard,
                len(seed_keywords),
            )
            count = await asyncio.to_thread(
                ingest_seo_keywords,
                seed_keywords=seed_keywords,
                max_keywords=config.get("max_keywords", 30),
                project_id=job.get("project_id"),
                force_standard=force_standard,
            )
            print(f"✅ SEO keyword ingestion: {count} ideas")

        except Exception as e:
            raise RuntimeError(f"SEO ingestion failed: {e}") from e

    async def _run_enrich_ideas(self, job: dict) -> None:
        """Enrich raw ideas in the Idea Pool with DataForSEO metrics."""
        config = job.get("configuration", {})

        try:
            from agents.sources.ingest import (
                DFS_STANDARD_ENRICH_THRESHOLD,
                enrich_ideas,
            )

            batch_size = config.get("batch_size", 50)
            # Scheduler jobs always use Standard queue ($0.05 vs $0.075/task)
            force_standard = config.get("force_standard", True)
            logger.info(
                "enrich_ideas job %s batch_size=%d force_standard=%s",
                job.get("id"),
                batch_size,
                force_standard,
            )
            count = await asyncio.to_thread(
                enrich_ideas,
                batch_size=batch_size,
                location=config.get("location", "us"),
                language=config.get("language", "en"),
                project_id=job.get("project_id"),
                force_standard=force_standard,
            )
            print(f"✅ Idea enrichment: {count} ideas enriched")

        except Exception as e:
            raise RuntimeError(f"Idea enrichment failed: {e}") from e

    async def _run_ingest_competitors(self, job: dict) -> None:
        """Analyze competitors and ingest content gaps into the Idea Pool."""
        config = job.get("configuration", {})
        target_domain = config.get("target_domain")
        competitor_domains = config.get("competitor_domains", [])

        if not competitor_domains:
            print("ℹ️  No competitor domains configured, skipping")
            return

        try:
            from agents.sources.ingest import (
                DFS_STANDARD_COMPETITOR_RANKED_LIMIT,
                ingest_competitor_watch,
            )

            max_gaps = config.get("max_gaps", 50)
            # Scheduler jobs always use Standard queue ($0.05 vs $0.075/task)
            force_standard = config.get("force_standard", True)
            logger.info(
                "ingest_competitors job %s max_gaps=%d force_standard=%s",
                job.get("id"),
                max_gaps,
                force_standard,
            )
            count = await asyncio.to_thread(
                ingest_competitor_watch,
                target_domain=target_domain or "",
                competitor_domains=competitor_domains,
                max_gaps=max_gaps,
                location=config.get("location", "us"),
                language=config.get("language", "en"),
                project_id=job.get("project_id"),
                force_standard=force_standard,
            )
            print(f"✅ Competitor intelligence: {count} gap ideas ingested")

        except Exception as e:
            raise RuntimeError(f"Competitor ingestion failed: {e}") from e

    async def _run_track_serp(self, job: dict) -> None:
        """Track SERP positions for published content."""
        config = job.get("configuration", {})

        try:
            from agents.sources.ingest import track_serp_positions

            count = await asyncio.to_thread(
                track_serp_positions,
                location=config.get("location", "us"),
                language=config.get("language", "en"),
                project_id=job.get("project_id"),
            )
            print(f"✅ SERP tracking: {count} items tracked")

        except Exception as e:
            raise RuntimeError(f"SERP tracking failed: {e}") from e

    async def _run_ingest_social(self, job: dict) -> None:
        """Run social listening across Reddit, X, HN, YouTube into the Idea Pool."""
        config = job.get("configuration", {})
        topics = config.get("topics", [])

        if not topics:
            print("ℹ️  No topics configured for social listening, skipping")
            return

        try:
            from agents.sources.social_listener import ingest_social_listening

            result = await asyncio.to_thread(
                ingest_social_listening,
                topics=topics,
                days_back=config.get("days_back", 30),
                max_ideas=config.get("max_ideas", 50),
                project_id=job.get("project_id"),
            )
            print(f"✅ Social listening: {result['count']} ideas ({result['sources']})")

        except Exception as e:
            raise RuntimeError(f"Social listening failed: {e}") from e

    async def _auto_transition_scheduled(self, svc) -> None:
        """Auto-transition content whose scheduledFor has passed."""
        now = datetime.utcnow().isoformat()

        # Find all content with status=scheduled and scheduledFor <= now
        scheduled_items = svc.list_content(status="scheduled", limit=100)

        for item in scheduled_items:
            if item.scheduled_for and item.scheduled_for.isoformat() <= now:
                try:
                    svc.transition(
                        item.id,
                        "publishing",
                        "scheduler",
                        reason="Scheduled time reached",
                    )
                    print(f"📅 Auto-transitioning {item.id} to publishing")
                except Exception as e:
                    print(f"⚠ Failed to auto-transition {item.id}: {e}")

    async def _reconcile_frequency_jobs(self, svc) -> None:
        """Ensure schedule jobs match user frequency config from settings.

        Reads contentFrequency from user settings and creates/updates/disables
        schedule jobs to match the desired cadence.
        """
        try:
            from api.services.user_data_store import UserDataStore
            store = UserDataStore()
        except Exception:
            return  # DB not configured, skip

        # For now, reconcile for all users with settings
        # In production, this would iterate over active users
        try:
            # Get all users with settings — simplified to single-user for now
            # The system currently operates as single-tenant
            freq = None
            try:
                # Try to read from a known user or system config
                settings = store.get_user_settings_raw()
                if settings:
                    robot_settings = settings.get("robotSettings", {})
                    if isinstance(robot_settings, str):
                        import json
                        robot_settings = json.loads(robot_settings)
                    freq = robot_settings.get("contentFrequency")
            except Exception:
                pass

            if not freq:
                return

            # Map frequency config to job types
            freq_map = {
                "article": {
                    "count": freq.get("blog_posts_per_month", 0),
                    "schedule": "weekly" if freq.get("blog_posts_per_month", 0) >= 4 else "monthly",
                    "schedule_time": "09:00",
                    "schedule_day": 1,
                },
                "newsletter": {
                    "count": freq.get("newsletters_per_week", 0),
                    "schedule": "weekly",
                    "schedule_time": "10:00",
                    "schedule_day": 1,
                },
                "short": {
                    "count": freq.get("shorts_per_day", 0),
                    "schedule": "daily",
                    "schedule_time": "08:00",
                },
                "social": {
                    "count": freq.get("social_posts_per_day", 0),
                    "schedule": "daily",
                    "schedule_time": "09:00",
                },
            }

            existing_jobs = svc.list_schedule_jobs()
            existing_by_type = {}
            for job in existing_jobs:
                jtype = job.get("job_type", "")
                if jtype.startswith("auto_"):
                    existing_by_type[jtype.replace("auto_", "")] = job

            for job_type, config in freq_map.items():
                existing = existing_by_type.get(job_type)
                should_exist = config["count"] > 0

                if should_exist and not existing:
                    # Create new auto-job
                    svc.create_schedule_job(
                        user_id="system",
                        job_type=f"auto_{job_type}",
                        schedule=config["schedule"],
                        schedule_time=config.get("schedule_time", "09:00"),
                        schedule_day=config.get("schedule_day"),
                        configuration={"auto_generated": True, "target_count": config["count"]},
                        enabled=True,
                    )
                    print(f"📅 Created auto_{job_type} job (count={config['count']})")
                elif not should_exist and existing:
                    # Disable existing auto-job
                    svc.update_schedule_job(existing["id"], enabled=False)
                    print(f"📅 Disabled auto_{job_type} job")

        except Exception as e:
            print(f"⚠ Frequency reconciliation failed: {e}")

    def _calculate_next_run(self, job: dict) -> Optional[str]:
        """Calculate the next run time based on schedule configuration."""
        now = datetime.utcnow()
        schedule = job.get("schedule", "daily")
        schedule_time = job.get("schedule_time", "09:00")
        schedule_day = job.get("schedule_day")

        # Parse target time
        try:
            hour, minute = (int(x) for x in schedule_time.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0

        if schedule == "daily":
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.isoformat()

        elif schedule == "weekly":
            day = schedule_day if schedule_day is not None else 0  # Monday
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
            return next_run.isoformat()

        elif schedule == "monthly":
            day = schedule_day if schedule_day is not None else 1
            day = min(day, 28)  # Cap at 28 for safety
            next_run = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                # Next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run.isoformat()

        elif schedule == "custom" and job.get("cron_expression"):
            # For custom cron, set next run to 24h from now as fallback
            return (now + timedelta(hours=24)).isoformat()

        return None


# ─── Singleton ────────────────────────────────────────

_scheduler_instance: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the singleton SchedulerService."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance

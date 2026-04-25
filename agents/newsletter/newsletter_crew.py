"""
Newsletter Crew - Multi-agent workflow for newsletter generation.

Pipeline: Research → Curate → Write → Review → Draft/Send → Archive

Uses:
- IMAP (free) or Composio (managed) for Gmail integration
- Exa AI for content research
- SendGrid for mass delivery
"""

from typing import Any, List, Optional, Dict
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
import os
import re
from datetime import datetime

from agents.newsletter.newsletter_agent import (
    NewsletterAgent,
    NewsletterResearchAgent,
    NewsletterWriterAgent,
)
from agents.newsletter.schemas.newsletter_schemas import (
    NewsletterConfig,
    NewsletterDraft,
    NewsletterSection,
)
from agents.newsletter.config.newsletter_config import (
    get_newsletter_config,
    EMAIL_BACKEND,
    is_imap_backend,
)
from status.audit import actor_from_agent

# Import archiving tools if using IMAP backend
if is_imap_backend():
    from agents.newsletter.tools.imap_tools import IMAPNewsletterReader

# Conditional memory import (graceful degradation)
try:
    from memory import get_memory_service
    from agents.newsletter.tools.memory_tools import (
        clear_memory_tool_scope,
        set_memory_tool_scope,
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    set_memory_tool_scope = None
    clear_memory_tool_scope = None

# Conditional status tracking (graceful degradation)
try:
    from status import get_status_service
    STATUS_AVAILABLE = True
except ImportError:
    STATUS_AVAILABLE = False

load_dotenv()


class NewsletterCrew:
    """
    Multi-agent crew for newsletter generation.

    Coordinates research, writing, and delivery agents to produce
    complete newsletters from email insights and web research.
    """

    def __init__(
        self,
        llm_model: Any | None = None,
        use_gmail: bool = True,
        track_status: bool = True,
    ):
        """
        Initialize Newsletter Crew.

        Args:
            llm_model: LLM model for all agents
            use_gmail: Enable Gmail integration via Composio
        """
        config = get_newsletter_config()
        self.llm_model = llm_model or config["llm_model"]
        self.use_gmail = use_gmail
        self.email_backend = EMAIL_BACKEND
        self.track_status = track_status

        # Initialize agents
        print("Initializing Newsletter Crew...")
        print(f"Email backend: {self.email_backend}")
        self.research_agent = NewsletterResearchAgent(self.llm_model)
        self.writer_agent = NewsletterWriterAgent(self.llm_model)
        print("✅ Newsletter agents initialized")

    def generate_newsletter(
        self,
        config: NewsletterConfig,
        competitor_emails: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete newsletter through multi-agent workflow.

        Args:
            config: Newsletter configuration
            competitor_emails: Override competitor email addresses

        Returns:
            Dictionary with newsletter draft and metadata
        """
        print("\n" + "=" * 60)
        print("NEWSLETTER GENERATION PIPELINE")
        print("=" * 60)
        print(f"Newsletter: {config.name}")
        print(f"Topics: {', '.join(config.topics)}")
        print(f"Tone: {config.tone.value}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

        # Status tracking: create content record
        status_record_id = None
        if self.track_status and STATUS_AVAILABLE:
            try:
                status_svc = get_status_service()
                record = status_svc.create_content(
                    title=config.name,
                    content_type="newsletter",
                    source_robot="newsletter",
                    status="in_progress",
                    tags=config.topics,
                    metadata={
                        "tone": config.tone.value,
                        "target_audience": config.target_audience,
                        "max_sections": config.max_sections,
                    },
                )
                status_record_id = record.id
                print(f"📊 Status tracking: record {record.id} created (in_progress)")
            except Exception as e:
                print(f"⚠ Status tracking init failed (non-critical): {e}")

        results = {
            "config": config.model_dump(),
            "stages": {},
            "draft": None,
        }

        # Merge competitor emails
        all_competitors = list(config.competitor_emails)
        if competitor_emails:
            all_competitors.extend(competitor_emails)

        # STAGE 0: Memory Context Loading
        memory_context = ""
        if MEMORY_AVAILABLE:
            try:
                print("\n🧠 STAGE 0: Loading Project Memory")
                print("-" * 40)
                memory = get_memory_service()

                sections = []

                # Load brand voice
                if user_id:
                    brand_ctx = memory.load_project_context(
                        "brand voice writing style tone guidelines",
                        user_id=user_id,
                        project_id=project_id,
                        limit=10,
                    )
                else:
                    brand_ctx = memory.load_context("brand voice writing style tone guidelines")
                if brand_ctx:
                    sections.append(brand_ctx)
                    print("  ✓ Brand voice loaded")

                # Load past newsletters for deduplication
                if user_id:
                    past_ctx = memory.load_project_context(
                        "past newsletter generation topics covered",
                        user_id=user_id,
                        project_id=project_id,
                        limit=10,
                    )
                else:
                    past_ctx = memory.load_context(
                        "past newsletter generation topics covered",
                        agent_id="newsletter",
                        limit=10,
                    )
                if past_ctx:
                    sections.append(past_ctx)
                    print("  ✓ Past newsletters loaded")

                # Load content inventory
                if user_id:
                    inventory_ctx = memory.load_project_context(
                        "published content articles inventory",
                        user_id=user_id,
                        project_id=project_id,
                        limit=15,
                    )
                else:
                    inventory_ctx = memory.load_context(
                        "published content articles inventory",
                        limit=15,
                    )
                if inventory_ctx:
                    sections.append(inventory_ctx)
                    print("  ✓ Content inventory loaded")

                if sections:
                    memory_context = (
                        "\n\n--- PROJECT MEMORY CONTEXT ---\n"
                        + "\n\n".join(sections)
                        + "\n--- END MEMORY CONTEXT ---\n"
                    )
                    print(f"  Total memory sections loaded: {len(sections)}")
                else:
                    print("  No memories found (brain may need seeding)")
            except Exception as e:
                print(f"  ⚠ Memory loading failed (non-critical): {e}")
                memory_context = ""

        # STAGE 1: Research
        print("\n📧 STAGE 1: Email & Content Research")
        print("-" * 40)

        research_task = Task(
            description=f"""
            Research content for a newsletter about: {', '.join(config.topics)}

            Your tasks:
            1. Read recent newsletter emails from Gmail (last 7 days)
            2. Analyze competitor newsletters from: {', '.join(all_competitors) or 'N/A'}
            3. Research trending content on the topics
            4. Identify 3-5 key themes or stories to cover

            Target audience: {config.target_audience}
            Tone: {config.tone.value}

            Output a structured research brief with:
            - Key insights from emails
            - Trending topics and angles
            - Recommended content themes
            - Source URLs for reference
            {memory_context}
            """,
            expected_output="Structured research brief with themes, insights, and sources",
            agent=self.research_agent.get_agent(),
        )

        # STAGE 2: Write Content
        print("\n✍️ STAGE 2: Content Writing")
        print("-" * 40)

        writing_task = Task(
            description=f"""
            Write newsletter content based on the research brief.

            Newsletter: {config.name}
            Topics: {', '.join(config.topics)}
            Tone: {config.tone.value}
            Target audience: {config.target_audience}

            Create:
            1. Compelling subject line (under 50 characters)
            2. Preview text (under 100 characters)
            3. Engaging intro paragraph
            4. {config.max_sections} content sections with:
               - Clear headings
               - Valuable insights
               - Source links where relevant
            5. Call-to-action: {config.cta_text or 'Encourage engagement'}
            6. Brief outro

            Format in clean markdown.
            {memory_context}
            """,
            expected_output="Complete newsletter in markdown format",
            agent=self.writer_agent.get_agent(),
            context=[research_task],
        )

        # Create and run crew
        crew = Crew(
            agents=[
                self.research_agent.get_agent(),
                self.writer_agent.get_agent(),
            ],
            tasks=[research_task, writing_task],
            process=Process.sequential,
            verbose=True,
        )

        print("\n🚀 Running newsletter generation pipeline...")
        newsletter_actor = actor_from_agent("newsletter")
        if set_memory_tool_scope is not None:
            set_memory_tool_scope(user_id=user_id, project_id=project_id)
        try:
            crew_output = crew.kickoff()
        except Exception as e:
            # Status tracking: mark as failed
            if self.track_status and STATUS_AVAILABLE and status_record_id:
                try:
                    status_svc = get_status_service()
                    status_svc.transition(status_record_id, "failed", newsletter_actor, reason=str(e))
                    print(f"📊 Status tracking: marked as failed")
                except Exception as se:
                    print(f"⚠ Status tracking failed transition error: {se}")
            raise
        finally:
            if clear_memory_tool_scope is not None:
                clear_memory_tool_scope()

        # Parse results
        results["stages"]["research"] = research_task.output.raw if research_task.output else None
        results["stages"]["writing"] = writing_task.output.raw if writing_task.output else None
        results["raw_output"] = str(crew_output)

        # Extract email UIDs from research output for archiving
        email_uids = self._extract_email_uids(
            results["stages"]["research"] or ""
        )
        results["email_uids"] = email_uids

        # Create draft object
        draft = NewsletterDraft(
            config=config,
            subject_line=self._extract_subject(str(crew_output)),
            preview_text=self._extract_preview(str(crew_output)),
            sections=self._parse_sections(str(crew_output)),
            plain_text=str(crew_output),
            email_sources=email_uids,
        )
        draft.word_count = len(str(crew_output).split())
        draft.estimated_read_time = draft.calculate_read_time()

        results["draft"] = draft.model_dump()

        # Store generation record in memory
        if MEMORY_AVAILABLE:
            try:
                memory = get_memory_service()
                topics_covered = config.topics
                if user_id:
                    memory.store_generation_scoped(
                        content_type="newsletter",
                        title=draft.subject_line,
                        user_id=user_id,
                        project_id=project_id,
                        topics=topics_covered,
                        summary=(
                            f"Newsletter '{config.name}' with {draft.word_count} words, "
                            f"{len(draft.sections)} sections. "
                            f"Topics: {', '.join(topics_covered)}."
                        ),
                    )
                else:
                    memory.store_generation(
                        content_type="newsletter",
                        title=draft.subject_line,
                        topics=topics_covered,
                        summary=f"Newsletter '{config.name}' with {draft.word_count} words, "
                                f"{len(draft.sections)} sections. "
                                f"Topics: {', '.join(topics_covered)}.",
                    )
                print("🧠 Generation record stored in memory")
            except Exception as e:
                print(f"⚠ Failed to store generation record (non-critical): {e}")

        # STAGE 3: Archive processed emails (IMAP only)
        if is_imap_backend() and email_uids:
            print("\n📁 STAGE 3: Archiving Processed Emails")
            print("-" * 40)
            archived_count = self._archive_processed_emails(email_uids)
            results["archived_count"] = archived_count
            print(f"Archived {archived_count} emails")

        # Status tracking: mark as generated → pending_review
        if self.track_status and STATUS_AVAILABLE and status_record_id:
            try:
                status_svc = get_status_service()
                preview = str(crew_output)[:500] if crew_output else None
                status_svc.update_content(
                    status_record_id,
                    content_preview=preview,
                    metadata={
                        "word_count": draft.word_count,
                        "read_time_minutes": draft.estimated_read_time,
                        "sections_count": len(draft.sections),
                        "subject_line": draft.subject_line,
                    },
                )
                status_svc.transition(status_record_id, "generated", newsletter_actor)
                status_svc.transition(status_record_id, "pending_review", newsletter_actor)
                results["status_record_id"] = status_record_id
                print(f"📊 Status tracking: marked as pending_review")
            except Exception as e:
                print(f"⚠ Status tracking completion failed (non-critical): {e}")

        print("\n" + "=" * 60)
        print("✅ NEWSLETTER GENERATION COMPLETE")
        print(f"Word count: {draft.word_count}")
        print(f"Read time: ~{draft.estimated_read_time} min")
        if is_imap_backend() and email_uids:
            print(f"Emails archived: {results.get('archived_count', 0)}")
        print("=" * 60)

        return results

    def _extract_subject(self, content: str) -> str:
        """Extract subject line from generated content."""
        lines = content.split("\n")
        for line in lines:
            if "subject" in line.lower() and ":" in line:
                return line.split(":", 1)[1].strip()[:50]
        return f"Newsletter - {datetime.now().strftime('%B %d, %Y')}"

    def _extract_preview(self, content: str) -> str:
        """Extract preview text from generated content."""
        lines = content.split("\n")
        for line in lines:
            if "preview" in line.lower() and ":" in line:
                return line.split(":", 1)[1].strip()[:100]
        return "This week's insights and updates"

    def _parse_sections(self, content: str) -> List[NewsletterSection]:
        """Parse content into newsletter sections."""
        sections = []
        current_section = None
        current_content = []
        order = 0

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections.append(NewsletterSection(
                        title=current_section,
                        content="\n".join(current_content).strip(),
                        order=order,
                    ))
                    order += 1
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections.append(NewsletterSection(
                title=current_section,
                content="\n".join(current_content).strip(),
                order=order,
            ))

        return sections

    def _extract_email_uids(self, research_output: str) -> List[str]:
        """
        Extract email UIDs from research agent output.

        The IMAP tools include UID in their output format:
        - UID: 12345

        Args:
            research_output: Raw output from research stage

        Returns:
            List of email UID strings
        """
        uids = []
        # Pattern to match "UID: <value>" in the research output
        uid_pattern = r"UID:\s*(\S+)"
        matches = re.findall(uid_pattern, research_output)
        uids.extend(matches)
        return uids

    def _archive_processed_emails(self, email_uids: List[str]) -> int:
        """
        Archive emails that were processed during newsletter generation.

        Only called when using IMAP backend.

        Args:
            email_uids: List of email UIDs to archive

        Returns:
            Number of emails successfully archived
        """
        if not email_uids:
            return 0

        try:
            reader = IMAPNewsletterReader()
            return reader.archive_multiple(email_uids)
        except Exception as e:
            print(f"Warning: Failed to archive emails: {e}")
            return 0


# Convenience function for quick generation
def generate_newsletter(
    name: str,
    topics: List[str],
    audience: str,
    competitor_emails: Optional[List[str]] = None,
    tone: str = "professional",
) -> Dict[str, Any]:
    """
    Quick function to generate a newsletter.

    Args:
        name: Newsletter name
        topics: List of topics to cover
        audience: Target audience description
        competitor_emails: Competitor newsletters to analyze
        tone: Writing tone

    Returns:
        Generated newsletter data
    """
    from agents.newsletter.schemas.newsletter_schemas import NewsletterTone

    config = NewsletterConfig(
        name=name,
        topics=topics,
        target_audience=audience,
        tone=NewsletterTone(tone),
        competitor_emails=competitor_emails or [],
    )

    crew = NewsletterCrew()
    return crew.generate_newsletter(config)

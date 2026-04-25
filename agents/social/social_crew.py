"""Social Post Crew — generates platform-adapted social media content.

Pipeline: Two agents work together:
1. PlatformAdapter — adapts content to each platform's format and constraints
2. ThreadBuilder — structures multi-part content (Twitter threads, LinkedIn carousels)
"""

import json
from typing import Any, Optional
from crewai import Agent, Task, Crew, Process
from agents.shared.prompt_loader import load_prompt
from status.audit import actor_from_agent

# Conditional status tracking (graceful degradation)
try:
    from status import get_status_service
    STATUS_AVAILABLE = True
except ImportError:
    STATUS_AVAILABLE = False


PLATFORM_SPECS = {
    "twitter": {"char_limit": 280, "thread_max": 10, "hashtag_max": 5, "supports_thread": True},
    "linkedin": {"char_limit": 3000, "hashtag_max": 5, "supports_thread": False},
    "instagram": {"char_limit": 2200, "hashtag_max": 30, "supports_thread": False},
}


class SocialPostCrew:
    """Crew for generating platform-adapted social media posts."""

    def __init__(self, llm_model: Any = "groq/mixtral-8x7b-32768"):
        self.llm_model = llm_model

    def _build_adapter_agent(self) -> Agent:
        p = load_prompt("social", "platform_adapter")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[],
            llm=self.llm_model,
            verbose=False,
        )

    def _build_thread_agent(self) -> Agent:
        p = load_prompt("social", "thread_builder")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[],
            llm=self.llm_model,
            verbose=False,
        )

    def generate_social_post(
        self,
        angle: dict,
        creator_voice: dict,
        platforms: list[str] | None = None,
        project_id: Optional[str] = None,
        create_content_record: bool = True,
    ) -> dict:
        """Generate platform-adapted social media posts.

        Args:
            angle: Content angle dict
            creator_voice: Creator's voice profile
            platforms: Target platforms (default: twitter, linkedin)
            project_id: Optional project ID

        Returns:
            Dict with posts list, one per platform
        """
        if platforms is None:
            platforms = ["twitter", "linkedin"]

        # Create content record
        record_id = None
        if STATUS_AVAILABLE and create_content_record:
            try:
                svc = get_status_service()
                record = svc.create_content(
                    title=angle.get("title", "Untitled Post"),
                    content_type="social_post",
                    source_robot="social",
                    status="in_progress",
                    project_id=project_id,
                    tags=platforms + ["social"],
                    metadata={
                        "angle": angle,
                        "platforms": platforms,
                    },
                )
                record_id = record.id
            except Exception as e:
                print(f"⚠ Status tracking failed (non-critical): {e}")

        adapter = self._build_adapter_agent()

        # Build platform specs for prompt
        platform_details = "\n".join(
            f"- **{p}**: {PLATFORM_SPECS.get(p, PLATFORM_SPECS['twitter'])}"
            for p in platforms
        )

        task = Task(
            description=(
                f"Create social media posts adapted for each platform.\n\n"
                f"## Content Angle\n"
                f"**Title**: {angle.get('title', 'N/A')}\n"
                f"**Hook**: {angle.get('hook', 'N/A')}\n"
                f"**Angle**: {angle.get('angle', 'N/A')}\n"
                f"**Pain point**: {angle.get('pain_point_addressed', 'N/A')}\n\n"
                f"## Creator Voice\n"
                f"{json.dumps(creator_voice)}\n\n"
                f"## Target Platforms\n"
                f"{platform_details}\n\n"
                f"## Required Output (JSON)\n"
                f'{{\n'
                f'  "posts": [\n'
                f'    {{\n'
                f'      "platform": "twitter",\n'
                f'      "text": "Main post text",\n'
                f'      "format": "single" or "thread",\n'
                f'      "thread_parts": ["Part 1", "Part 2", ...] (if thread),\n'
                f'      "hashtags": ["tag1", "tag2"],\n'
                f'      "media_suggestion": "Description of ideal image/visual",\n'
                f'      "character_count": 280\n'
                f'    }}\n'
                f'  ]\n'
                f'}}\n\n'
                f"Create one post object per platform. Make each post native to its platform.\n"
                f"For Twitter: if the content needs > 280 chars, use thread format.\n"
                f"For LinkedIn: use storytelling format with line breaks.\n"
                f"For Instagram: use emoji and visual language."
            ),
            agent=adapter,
            expected_output="JSON with posts array, one per platform",
        )

        crew = Crew(agents=[adapter], tasks=[task], verbose=False)
        result = crew.kickoff()
        raw = str(result)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: create a basic post for each platform
            parsed = {
                "posts": [
                    {
                        "platform": p,
                        "text": raw[:PLATFORM_SPECS.get(p, PLATFORM_SPECS["twitter"])["char_limit"]],
                        "format": "single",
                        "hashtags": [],
                        "media_suggestion": None,
                    }
                    for p in platforms
                ],
            }

        # Update content record
        if STATUS_AVAILABLE and create_content_record and record_id:
            try:
                svc = get_status_service()
                body = json.dumps(parsed.get("posts", []), indent=2)
                svc.save_content_body(record_id, body, edited_by=actor_from_agent("social_crew"))
                svc.transition(record_id, "pending_review", actor_from_agent("social_crew"))
            except Exception as e:
                print(f"⚠ Status update failed: {e}")

        parsed["content_record_id"] = record_id
        return parsed

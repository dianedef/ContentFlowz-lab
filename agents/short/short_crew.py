"""Short-Form Content Crew — generates scripts for TikTok, Reels, YouTube Shorts.

Pipeline: Single agent (ShortFormWriter) produces a complete short content package
including hook, timed script, hashtags, and visual notes.
"""

import json
from typing import Any, Optional
from crewai import Agent, Task, Crew
from agents.shared.prompt_loader import load_prompt
from status.audit import actor_from_agent

# Conditional status tracking (graceful degradation)
try:
    from status import get_status_service
    STATUS_AVAILABLE = True
except ImportError:
    STATUS_AVAILABLE = False


PLATFORM_CONSTRAINTS = {
    "tiktok": {"max_duration": 180, "max_hashtags": 10, "char_limit": 2200},
    "instagram_reels": {"max_duration": 90, "max_hashtags": 30, "char_limit": 2200},
    "youtube_shorts": {"max_duration": 60, "max_hashtags": 15, "char_limit": 5000},
}


class ShortContentCrew:
    """Crew for generating short-form video content packages."""

    def __init__(self, llm_model: Any = "groq/mixtral-8x7b-32768"):
        self.llm_model = llm_model

    def _build_agent(self) -> Agent:
        p = load_prompt("short", "short_form_writer")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[],
            llm=self.llm_model,
            verbose=False,
        )

    def generate_short(
        self,
        angle: dict,
        creator_voice: dict,
        platform: str = "tiktok",
        max_duration: int = 60,
        project_id: Optional[str] = None,
        create_content_record: bool = True,
    ) -> dict:
        """Generate a complete short-form content package.

        Args:
            angle: Content angle dict (title, hook, angle, pain_point_addressed)
            creator_voice: Creator's voice profile
            platform: Target platform (tiktok, instagram_reels, youtube_shorts)
            max_duration: Maximum duration in seconds
            project_id: Optional project ID

        Returns:
            Dict with hook, script, duration, hashtags, cta, visual_notes
        """
        constraints = PLATFORM_CONSTRAINTS.get(platform, PLATFORM_CONSTRAINTS["tiktok"])
        actual_max = min(max_duration, constraints["max_duration"])

        # Create content record if status service available
        record_id = None
        if STATUS_AVAILABLE and create_content_record:
            try:
                svc = get_status_service()
                record = svc.create_content(
                    title=angle.get("title", "Untitled Short"),
                    content_type="short",
                    source_robot="short",
                    status="in_progress",
                    project_id=project_id,
                    tags=[platform, "short"],
                    metadata={
                        "angle": angle,
                        "platform": platform,
                        "max_duration": actual_max,
                    },
                )
                record_id = record.id
            except Exception as e:
                print(f"⚠ Status tracking failed (non-critical): {e}")

        agent = self._build_agent()

        task = Task(
            description=(
                f"Create a short-form video script for {platform}.\n\n"
                f"## Content Angle\n"
                f"**Title**: {angle.get('title', 'N/A')}\n"
                f"**Hook**: {angle.get('hook', 'N/A')}\n"
                f"**Angle**: {angle.get('angle', 'N/A')}\n"
                f"**Pain point**: {angle.get('pain_point_addressed', 'N/A')}\n\n"
                f"## Creator Voice\n"
                f"{json.dumps(creator_voice)}\n\n"
                f"## Platform Constraints\n"
                f"- Platform: {platform}\n"
                f"- Max duration: {actual_max} seconds\n"
                f"- Max hashtags: {constraints['max_hashtags']}\n\n"
                f"## Required Output (JSON)\n"
                f"{{\n"
                f'  "hook": "Opening line — must grab attention in < 2 seconds (< 10 words)",\n'
                f'  "script": "Full script with [TIMECODES] like [0:00-0:03] Hook. [0:03-0:15] Setup...",\n'
                f'  "duration_seconds": {actual_max},\n'
                f'  "on_screen_text": ["Key phrase 1", "Key phrase 2"],\n'
                f'  "hashtags": ["tag1", "tag2", ...],\n'
                f'  "cta": "Call to action (follow, comment, link in bio, etc.)",\n'
                f'  "visual_notes": "Camera angles, transitions, b-roll suggestions",\n'
                f'  "thumbnail_concept": "What the thumbnail/cover frame should show"\n'
                f"}}"
            ),
            agent=agent,
            expected_output="JSON with hook, script, duration_seconds, hashtags, cta, visual_notes",
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = crew.kickoff()
        raw = str(result)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "hook": angle.get("hook", ""),
                "script": raw,
                "duration_seconds": actual_max,
                "hashtags": [],
                "cta": "",
                "visual_notes": "",
            }

        # Update content record
        if STATUS_AVAILABLE and create_content_record and record_id:
            try:
                svc = get_status_service()
                body = parsed.get("script", raw)
                svc.save_content_body(record_id, body, edited_by=actor_from_agent("short_crew"))
                svc.transition(record_id, "pending_review", actor_from_agent("short_crew"))
            except Exception as e:
                print(f"⚠ Status update failed: {e}")

        parsed["content_record_id"] = record_id
        parsed["platform"] = platform
        return parsed

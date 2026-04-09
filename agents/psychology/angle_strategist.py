"""Angle Strategist — generates content angles by crossing creator narrative with customer pain.

This is The Bridge — the core value proposition of the Psychology Engine.
It takes creator identity (voice, positioning, narrative) and customer
persona (pain points, goals, language) and produces strategic content angles.

This agent uses no tools — it reasons purely over the provided context.
"""

from crewai import Agent, Task, Crew
from agents.shared.prompt_loader import load_prompt


def _build_agent() -> Agent:
    p = load_prompt("psychology", "angle_strategist")
    return Agent(
        role=p["role"],
        goal=p["goal"],
        backstory=p["backstory"],
        tools=[],
        verbose=False,
    )


def run_angle_generation(
    creator_voice: dict,
    creator_positioning: dict,
    narrative_summary: str | None,
    persona_data: dict,
    content_type: str | None = None,
    count: int = 5,
    seo_signals: list[dict] | None = None,
    trending_signals: list[dict] | None = None,
) -> dict:
    """Run the Angle Strategist to generate content angles.

    Args:
        creator_voice: Creator's voice profile dict
        creator_positioning: Creator's positioning dict
        narrative_summary: Current narrative summary text
        persona_data: Customer persona dict
        content_type: Optional content type filter
        count: Number of angles to generate
        seo_signals: Optional SEO keyword data (volume, difficulty, intent)
        trending_signals: Optional trending topics from research

    Returns:
        Dict with angles list and strategy_note
    """
    import json

    agent = _build_agent()

    content_type_instruction = (
        f"Focus on {content_type} format." if content_type else "Suggest the best format for each angle (article, newsletter, short, social_post)."
    )

    # Build SEO/trending context sections
    seo_section = ""
    if seo_signals:
        seo_section = (
            f"\n## SEO Opportunities\n"
            f"The following keywords have search demand. Use them to inform angle selection, "
            f"especially for article and blog content:\n"
            f"{json.dumps(seo_signals, indent=2)}\n"
        )

    trending_section = ""
    if trending_signals:
        trending_section = (
            f"\n## Trending Signals\n"
            f"These topics are currently trending. Prefer timely angles when relevant, "
            f"especially for short and social_post formats:\n"
            f"{json.dumps(trending_signals, indent=2)}\n"
        )

    scoring_instruction = ""
    if seo_signals or trending_signals:
        scoring_instruction = (
            "\nFor each angle, also provide:\n"
            "8. priority_score: 0-100 computed priority (factor in SEO volume, trending velocity, and confidence)\n"
            "9. seo_keyword: the primary SEO keyword this angle targets (if applicable, null otherwise)\n"
        )

    task_cfg = load_prompt("psychology", "angle_strategist")["tasks"]["angle_generation"]
    generation_task = Task(
        description=task_cfg["description"].format(
            count=count,
            creator_voice=json.dumps(creator_voice),
            creator_positioning=json.dumps(creator_positioning),
            narrative_summary=narrative_summary or "Not available",
            persona_name=persona_data.get("name", "Unknown"),
            pain_points=json.dumps(persona_data.get("painPoints", [])),
            goals=json.dumps(persona_data.get("goals", [])),
            language_triggers=json.dumps(persona_data.get("language", {}).get("triggers", [])),
            content_preferences=json.dumps(persona_data.get("contentPreferences", {})),
            seo_section=seo_section,
            trending_section=trending_section,
            content_type_instruction=content_type_instruction,
            scoring_instruction=scoring_instruction,
        ),
        agent=agent,
        expected_output=task_cfg["expected_output"],
    )

    crew = Crew(
        agents=[agent],
        tasks=[generation_task],
        verbose=False,
    )

    result = crew.kickoff()
    raw = str(result)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "angles": [],
            "strategy_note": raw,
        }

    return parsed

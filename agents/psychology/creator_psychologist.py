"""Creator Psychologist — synthesizes creator entries into narrative updates.

This agent reads raw ritual entries, detects patterns and evolution,
and produces narrative updates that the creator reviews before merging.
"""

from typing import Any

from crewai import Agent, Task, Crew
from agents.shared.prompt_loader import load_prompt
from agents.psychology.tools.narrative_tools import (
    read_narrative_context,
    analyze_entry_patterns,
    detect_chapter_transition,
    generate_narrative_update,
)


def _build_agent(llm: Any | None = None) -> Agent:
    p = load_prompt("psychology", "creator_psychologist")
    return Agent(
        role=p["role"],
        goal=p["goal"],
        backstory=p["backstory"],
        tools=[
            read_narrative_context,
            analyze_entry_patterns,
            detect_chapter_transition,
            generate_narrative_update,
        ],
        llm=llm,
        verbose=False,
    )


def run_narrative_synthesis(
    profile_id: str,
    entries: list[dict],
    current_voice: dict | None = None,
    current_positioning: dict | None = None,
    chapter_title: str | None = None,
    llm: Any | None = None,
) -> dict:
    """Run the Creator Psychologist crew to synthesize narrative from entries.

    Args:
        profile_id: Creator profile ID
        entries: List of creator entry dicts
        current_voice: Current voice profile dict
        current_positioning: Current positioning dict
        chapter_title: Current narrative chapter title

    Returns:
        Dict with voice_delta, positioning_delta, narrative_summary, chapter_transition
    """
    import json

    agent = _build_agent(llm=llm)

    entries_json = json.dumps(entries)
    voice_json = json.dumps(current_voice or {})
    positioning_json = json.dumps(current_positioning or {})

    task_cfg = load_prompt("psychology", "creator_psychologist")["tasks"]["narrative_synthesis"]
    synthesis_task = Task(
        description=task_cfg["description"].format(
            voice_json=voice_json,
            positioning_json=positioning_json,
            chapter_title=chapter_title or "None",
            entries_json=entries_json,
        ),
        agent=agent,
        expected_output=task_cfg["expected_output"],
    )

    crew = Crew(
        agents=[agent],
        tasks=[synthesis_task],
        verbose=False,
    )

    result = crew.kickoff()
    raw = str(result)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "voice_delta": {},
            "positioning_delta": {},
            "narrative_summary": raw,
            "chapter_transition": False,
        }

    return parsed

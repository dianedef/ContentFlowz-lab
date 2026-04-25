"""Audience Analyst — refines customer personas using behavioral data and analytics.

This agent takes existing persona definitions and enriches them with
analytics data, content performance correlations, and gap analysis.
"""

from typing import Any

from crewai import Agent, Task, Crew
from agents.shared.prompt_loader import load_prompt
from agents.psychology.tools.persona_tools import (
    read_persona_profile,
    analyze_persona_gaps,
    merge_behavioral_data,
    update_persona_confidence,
)
from agents.psychology.tools.analytics_tools import (
    correlate_content_performance,
)


def _build_agent(llm: Any | None = None) -> Agent:
    p = load_prompt("psychology", "audience_analyst")
    return Agent(
        role=p["role"],
        goal=p["goal"],
        backstory=p["backstory"],
        tools=[
            read_persona_profile,
            analyze_persona_gaps,
            merge_behavioral_data,
            update_persona_confidence,
            correlate_content_performance,
        ],
        llm=llm,
        verbose=False,
        allow_delegation=True,
    )


def run_persona_refinement(
    persona: dict,
    analytics_data: dict | None = None,
    content_performance: list[dict] | None = None,
    llm: Any | None = None,
) -> dict:
    """Run the Audience Analyst crew to refine a persona.

    Args:
        persona: Current persona dict
        analytics_data: Optional analytics data dict
        content_performance: Optional list of content performance records

    Returns:
        Dict with updated persona fields and new confidence score
    """
    import json

    agent = _build_agent(llm=llm)

    persona_json = json.dumps(persona)
    analytics_json = json.dumps(analytics_data or {})
    content_json = json.dumps(content_performance or [])

    task_cfg = load_prompt("psychology", "audience_analyst")["tasks"]["persona_refinement"]
    refinement_task = Task(
        description=task_cfg["description"].format(
            persona_json=persona_json,
            analytics_json=analytics_json,
            content_json=content_json,
        ),
        agent=agent,
        expected_output=task_cfg["expected_output"],
    )

    crew = Crew(
        agents=[agent],
        tasks=[refinement_task],
        verbose=False,
    )

    result = crew.kickoff()
    raw = str(result)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "suggested_updates": {},
            "new_confidence": persona.get("confidence", 50),
            "gaps": [],
            "insights": [raw],
        }

    return parsed

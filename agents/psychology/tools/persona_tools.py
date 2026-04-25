"""Tools for the Audience Analyst agent — persona refinement and behavioral analysis"""

from crewai import tool


def _first(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, list | dict) and not value:
            continue
        return value
    return None


def _trigger_values(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        values: list[str] = []
        for item in raw.values():
            if isinstance(item, list):
                values.extend(str(entry) for entry in item if str(entry).strip())
            elif item is not None and str(item).strip():
                values.append(str(item))
        return values
    if raw is None:
        return []
    value = str(raw).strip()
    return [value] if value else []


@tool("read_persona_profile")
def read_persona_profile(persona_json: str) -> str:
    """Read a customer persona and format it for analysis.

    Args:
        persona_json: JSON string of the customer persona data
    """
    import json

    persona = json.loads(persona_json)

    parts = [
        f"## Persona: {persona.get('name', 'Unknown')}",
        f"**Confidence**: {persona.get('confidence', 50)}%",
    ]

    demographics = persona.get("demographics", {})
    if demographics:
        parts.append(
            f"**Demographics**: {demographics.get('role', 'N/A')} in "
            f"{demographics.get('industry', 'N/A')}, "
            f"{_first(demographics.get('ageRange'), demographics.get('age_range'), 'N/A')}, "
            f"{_first(demographics.get('experience'), demographics.get('experience_level'), 'N/A')} experience"
        )

    pain_points = _first(persona.get("painPoints"), persona.get("pain_points"), []) or []
    if pain_points:
        parts.append(f"**Pain points**: {', '.join(pain_points)}")

    goals = persona.get("goals", [])
    if goals:
        parts.append(f"**Goals**: {', '.join(goals)}")

    lang = persona.get("language", {})
    if lang:
        if lang.get("vocabulary"):
            parts.append(f"**Vocabulary**: {', '.join(lang['vocabulary'][:10])}")
        if lang.get("objections"):
            parts.append(f"**Objections**: {', '.join(lang['objections'])}")
        triggers = _trigger_values(lang.get("triggers"))
        if triggers:
            parts.append(f"**Triggers**: {', '.join(triggers)}")

    prefs = _first(persona.get("contentPreferences"), persona.get("content_preferences"), {}) or {}
    if prefs:
        if prefs.get("formats"):
            parts.append(f"**Preferred formats**: {', '.join(prefs['formats'])}")
        if prefs.get("channels"):
            parts.append(f"**Channels**: {', '.join(prefs['channels'])}")

    return "\n".join(parts)


@tool("analyze_persona_gaps")
def analyze_persona_gaps(persona_json: str) -> str:
    """Identify gaps and weak spots in a persona definition that need more data.

    Args:
        persona_json: JSON string of the customer persona data
    """
    import json

    persona = json.loads(persona_json)
    gaps = []

    if not persona.get("demographics") or not persona["demographics"].get("role"):
        gaps.append("Missing demographics (role, industry, experience)")
    pain_points = _first(persona.get("painPoints"), persona.get("pain_points"), []) or []
    if len(pain_points) < 2:
        gaps.append("Needs more pain points (minimum 2)")
    if not persona.get("goals") or len(persona.get("goals", [])) < 2:
        gaps.append("Needs more goals (minimum 2)")
    triggers = _trigger_values(persona.get("language", {}).get("triggers"))
    if not persona.get("language") or not triggers:
        gaps.append("Missing language triggers")
    if not persona.get("language", {}).get("objections"):
        gaps.append("Missing objections/resistances")
    prefs = _first(persona.get("contentPreferences"), persona.get("content_preferences"), {}) or {}
    if not prefs:
        gaps.append("Missing content preferences")

    confidence = persona.get("confidence", 50)

    return (
        f"## Persona Gap Analysis: {persona.get('name', 'Unknown')}\n"
        f"**Current confidence**: {confidence}%\n"
        f"**Gaps found**: {len(gaps)}\n\n"
        + ("\n".join(f"- {g}" for g in gaps) if gaps else "No major gaps found.")
    )


@tool("merge_behavioral_data")
def merge_behavioral_data(
    persona_json: str,
    analytics_json: str,
) -> str:
    """Merge behavioral data from analytics into persona, suggesting updates.

    Args:
        persona_json: JSON string of the customer persona
        analytics_json: JSON string of analytics/behavioral data
    """
    import json

    persona = json.loads(persona_json)
    analytics = json.loads(analytics_json) if analytics_json else {}

    suggestions = []

    top_content = analytics.get("topContent", [])
    if top_content:
        suggestions.append(f"Top-performing content themes: {', '.join(top_content[:5])}")

    avg_session = analytics.get("avgSessionDuration")
    if avg_session:
        suggestions.append(f"Average session duration: {avg_session}s — suggests {'deep' if avg_session > 180 else 'quick'} content consumption")

    top_channels = analytics.get("topChannels", [])
    if top_channels:
        suggestions.append(f"Top traffic channels: {', '.join(top_channels[:3])}")

    bounce_rate = analytics.get("bounceRate")
    if bounce_rate and bounce_rate > 70:
        suggestions.append(f"High bounce rate ({bounce_rate}%) — content may not match expectations")

    return (
        f"## Behavioral Data Merge for: {persona.get('name', 'Unknown')}\n\n"
        + ("\n".join(f"- {s}" for s in suggestions) if suggestions else "No significant behavioral data available.")
    )


@tool("update_persona_confidence")
def update_persona_confidence(
    persona_json: str,
    data_sources_count: int,
    gaps_count: int,
) -> str:
    """Calculate updated confidence score based on data completeness.

    Args:
        persona_json: JSON string of the customer persona
        data_sources_count: Number of data sources used to build the persona
        gaps_count: Number of identified gaps in the persona
    """
    import json

    persona = json.loads(persona_json)

    base = 30
    field_bonus = 0

    if persona.get("demographics"): field_bonus += 10
    if len(_first(persona.get("painPoints"), persona.get("pain_points"), []) or []) >= 2: field_bonus += 10
    if len(persona.get("goals", [])) >= 2: field_bonus += 10
    if _trigger_values(persona.get("language", {}).get("triggers")): field_bonus += 10
    if persona.get("language", {}).get("objections"): field_bonus += 10
    if _first(persona.get("contentPreferences"), persona.get("content_preferences"), {}): field_bonus += 10

    data_bonus = min(data_sources_count * 5, 20)
    gap_penalty = gaps_count * 5

    new_confidence = min(100, max(10, base + field_bonus + data_bonus - gap_penalty))

    return (
        f"## Confidence Update: {persona.get('name', 'Unknown')}\n"
        f"**Previous**: {persona.get('confidence', 50)}%\n"
        f"**New**: {new_confidence}%\n"
        f"**Breakdown**: base={base} + fields={field_bonus} + data={data_bonus} - gaps={gap_penalty}"
    )

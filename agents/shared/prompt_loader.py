"""Prompt loader — loads agent prompts from YAML files.

Usage:
    from agents.shared.prompt_loader import load_prompt

    p = load_prompt("seo", "research_analyst")
    # p["role"], p["goal"], p["backstory"]
    # p["tasks"]["analysis"]["description"].format_map(vars)
"""

from pathlib import Path
import yaml


_BASE = Path(__file__).parent.parent  # agents/


def load_prompt(robot: str, agent_name: str) -> dict:
    """Load agent prompt config from YAML.

    Args:
        robot: Robot folder name (e.g. "seo", "newsletter", "psychology").
        agent_name: Agent YAML file name without extension (e.g. "research_analyst").

    Returns:
        Dict with keys: role, goal, backstory, tasks (dict of task configs).

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        KeyError: If a required key (role/goal/backstory) is missing.
    """
    path = _BASE / robot / "prompts" / f"{agent_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}. "
            f"Expected agents/{robot}/prompts/{agent_name}.yaml"
        )

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for required in ("role", "goal", "backstory"):
        if required not in data:
            raise KeyError(
                f"Missing required key '{required}' in {path}"
            )

    data.setdefault("tasks", {})
    return data

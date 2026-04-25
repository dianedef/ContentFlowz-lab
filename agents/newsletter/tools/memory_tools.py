"""
Memory Tools - CrewAI @tool functions for accessing the project brain.

Provides newsletter agents with access to persistent memory for:
- Recalling past newsletters (deduplication)
- Loading brand voice guidelines
- Searching project context

All tools use lazy imports with graceful degradation — if Mem0 isn't
installed, they return "Memory unavailable" instead of crashing.
"""

from crewai.tools import tool

# Lazy import flag — checked on first tool call
_memory_checked = False
_memory_service = None
_runtime_user_id: str | None = None
_runtime_project_id: str | None = None


def set_memory_tool_scope(*, user_id: str | None, project_id: str | None) -> None:
    """Bind request scope for newsletter memory tools."""
    global _runtime_user_id, _runtime_project_id
    _runtime_user_id = user_id
    _runtime_project_id = project_id


def clear_memory_tool_scope() -> None:
    """Clear request scope after a newsletter run."""
    set_memory_tool_scope(user_id=None, project_id=None)


def _get_memory():
    """Lazy-load memory service with graceful fallback."""
    global _memory_checked, _memory_service
    if not _memory_checked:
        _memory_checked = True
        try:
            from memory import get_memory_service
            _memory_service = get_memory_service()
        except (ImportError, Exception) as e:
            print(f"Memory tools: Memory unavailable ({e})")
            _memory_service = None
    return _memory_service


@tool
def recall_project_context(query: str) -> str:
    """Search the project brain for relevant context about a topic.

    Use this to recall what you know about a specific topic, past decisions,
    content strategy, or any project knowledge before starting work.

    Args:
        query: Natural language search query (e.g. "AI agent trends",
               "content strategy for newsletters")

    Returns:
        Relevant project memories formatted as context, or a message
        if memory is unavailable.
    """
    memory = _get_memory()
    if memory is None:
        return "Memory unavailable — proceeding without project context."

    try:
        if _runtime_user_id:
            context = memory.load_project_context(
                query,
                user_id=_runtime_user_id,
                project_id=_runtime_project_id,
                limit=10,
            )
        else:
            context = memory.load_context(query, limit=10)
        if not context:
            return f"No memories found for: {query}"
        return context
    except Exception as e:
        return f"Memory search failed: {e}"


@tool
def recall_past_newsletters(limit: int = 10) -> str:
    """Recall past newsletter topics to avoid duplication.

    Use this before planning newsletter content to see what topics
    were already covered in previous newsletters.

    Args:
        limit: Maximum number of past newsletters to recall (default 10)

    Returns:
        Summary of past newsletter topics and dates, or a message
        if memory is unavailable.
    """
    memory = _get_memory()
    if memory is None:
        return "Memory unavailable — no past newsletter history accessible."

    try:
        if _runtime_user_id:
            scoped = memory.load_project_context(
                "past newsletter generation topics covered",
                user_id=_runtime_user_id,
                project_id=_runtime_project_id,
                limit=limit,
            )
            if not scoped:
                return "No past newsletters found in memory — this may be the first run."
            return scoped

        entries = memory.search(
            "past newsletter generation topics covered",
            limit=limit,
            agent_id="newsletter",
        )
        if not entries:
            return "No past newsletters found in memory — this may be the first run."

        lines = [f"=== Past Newsletters ({len(entries)} found) ==="]
        for i, entry in enumerate(entries, 1):
            lines.append(f"\n[{i}] {entry.memory}")
        lines.append("\n=== End Past Newsletters ===")
        return "\n".join(lines)
    except Exception as e:
        return f"Memory search failed: {e}"


@tool
def recall_brand_voice() -> str:
    """Recall brand voice guidelines and writing style from memory.

    Use this before writing content to ensure consistent tone, style,
    and terminology across all newsletters.

    Returns:
        Brand voice guidelines and style notes, or a message
        if memory is unavailable.
    """
    memory = _get_memory()
    if memory is None:
        return "Memory unavailable — using default writing style."

    try:
        if _runtime_user_id:
            context = memory.load_project_context(
                "brand voice writing style tone guidelines",
                user_id=_runtime_user_id,
                project_id=_runtime_project_id,
                limit=10,
            )
        else:
            context = memory.load_context(
                "brand voice writing style tone guidelines",
                limit=10,
            )
        if not context:
            return "No brand voice guidelines found in memory — using default style."
        return context
    except Exception as e:
        return f"Memory search failed: {e}"

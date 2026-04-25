import importlib.util
import sys
import types
from pathlib import Path


_MEMORY_TOOLS_PATH = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "newsletter"
    / "tools"
    / "memory_tools.py"
)


def _identity_tool_decorator(func=None, *args, **kwargs):
    if func is None:
        def _decorator(inner):
            return inner
        return _decorator
    return func


def _load_memory_tools_module():
    fake_crewai = types.ModuleType("crewai")
    fake_tools = types.ModuleType("crewai.tools")
    fake_tools.tool = _identity_tool_decorator
    fake_crewai.tools = fake_tools
    sys.modules["crewai"] = fake_crewai
    sys.modules["crewai.tools"] = fake_tools

    spec = importlib.util.spec_from_file_location(
        "contentflow_newsletter_memory_tools",
        _MEMORY_TOOLS_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_memory_tools_use_project_scope_when_bound():
    module = _load_memory_tools_module()

    calls: list[tuple[str, dict]] = []

    class FakeMemory:
        def load_project_context(self, query, *, user_id, project_id, limit):
            calls.append(
                (
                    "project",
                    {
                        "query": query,
                        "user_id": user_id,
                        "project_id": project_id,
                        "limit": limit,
                    },
                )
            )
            return "scoped-memory"

        def load_context(self, *args, **kwargs):
            calls.append(("global", {}))
            return "global-memory"

    module._memory_checked = True
    module._memory_service = FakeMemory()

    module.set_memory_tool_scope(user_id="user-1", project_id="project-1")
    result = module.recall_brand_voice()

    assert result == "scoped-memory"
    assert calls[0][0] == "project"
    assert calls[0][1]["user_id"] == "user-1"
    assert calls[0][1]["project_id"] == "project-1"


def test_memory_tools_fallback_to_global_context_when_scope_cleared():
    module = _load_memory_tools_module()

    calls: list[str] = []

    class FakeMemory:
        def load_project_context(self, *args, **kwargs):
            calls.append("project")
            return "scoped-memory"

        def load_context(self, *args, **kwargs):
            calls.append("global")
            return "global-memory"

    module._memory_checked = True
    module._memory_service = FakeMemory()
    module.set_memory_tool_scope(user_id="user-1", project_id="project-1")
    module.clear_memory_tool_scope()

    result = module.recall_project_context("newsletter topics")

    assert result == "global-memory"
    assert calls == ["global"]

import sys
import types
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.models.research import CompetitorAnalysisRequest
from api.routers import research as research_router
from api.services.user_llm_service import OpenRouterCredentialMissingError


@pytest.mark.asyncio
async def test_competitor_analysis_requires_user_key_even_with_env(monkeypatch):
    monkeypatch.setattr(
        research_router.user_llm_service,
        "get_crewai_llm",
        AsyncMock(
            side_effect=OpenRouterCredentialMissingError("missing OpenRouter key")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await research_router.competitor_analysis(
            request=CompetitorAnalysisRequest(
                target_url="https://example.com",
                competitors=["https://competitor.com"],
                keywords=["ai workflows"],
            ),
            current_user=SimpleNamespace(user_id="user-1"),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_competitor_analysis_normalizes_request_payload(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResearchAnalystAgent:
        def __init__(self, llm_model, use_consensus_ai=False, include_firecrawl_tools=True):
            captured["llm_model"] = llm_model
            captured["use_consensus_ai"] = use_consensus_ai
            captured["include_firecrawl_tools"] = include_firecrawl_tools
            self.use_consensus_ai = use_consensus_ai

        def run_analysis(self, target_keyword, competitor_domains=None):
            captured["target_keyword"] = target_keyword
            captured["competitor_domains"] = competitor_domains
            return types.SimpleNamespace(
                raw="""
## Competitors
- www.comp-one.com
- comp-two.io
## Common Topics
- AI workflows
## Opportunities
- Better onboarding content
## Recommendations
- Create a migration checklist
""".strip()
            )

    fake_module = types.ModuleType("agents.seo.research_analyst")
    fake_module.ResearchAnalystAgent = FakeResearchAnalystAgent
    monkeypatch.setitem(sys.modules, "agents.seo.research_analyst", fake_module)
    monkeypatch.setattr(
        research_router.ai_runtime_service,
        "preflight_providers",
        AsyncMock(
            return_value=SimpleNamespace(
                mode="byok",
                has_optional_provider=lambda _provider: True,
            )
        ),
    )
    monkeypatch.setattr(
        research_router.ai_runtime_service,
        "bind_provider_env",
        lambda _resolution: nullcontext(),
    )
    monkeypatch.setattr(
        research_router.user_llm_service,
        "get_crewai_llm",
        AsyncMock(return_value="llm-object"),
    )

    response = await research_router.competitor_analysis(
        request=CompetitorAnalysisRequest(
            target_url="https://example.com",
            competitors=[
                "https://www.comp-one.com/path",
                "comp-two.io/blog",
            ],
            keywords=[" ai workflows "],
            use_consensus_ai=True,
        ),
        current_user=SimpleNamespace(user_id="user-1"),
    )

    assert captured["llm_model"] == "llm-object"
    assert captured["use_consensus_ai"] is True
    assert captured["include_firecrawl_tools"] is True
    assert captured["target_keyword"] == "ai workflows"
    assert captured["competitor_domains"] == ["comp-one.com", "comp-two.io"]
    assert response.keywords == ["ai workflows"]
    assert sorted([competitor.domain for competitor in response.competitors]) == [
        "comp-one.com",
        "comp-two.io",
    ]

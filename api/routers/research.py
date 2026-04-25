"""Research & Analysis API endpoints

IMPORTANT: Uses lazy imports for heavy agent dependencies.
"""

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import time
import re
from typing import Any, TYPE_CHECKING

from api.models.research import (
    CompetitorAnalysisRequest,
    CompetitorAnalysisResponse,
    CompetitorInfo,
)
from api.dependencies.auth import CurrentUser, require_current_user
from api.services.ai_runtime_service import AIRuntimeServiceError, ai_runtime_service
from api.services.user_llm_service import (
    DEFAULT_OPENROUTER_MODEL,
    AIRuntimeResolutionError,
    UserLLMCredentialError,
    user_llm_service,
)

# Type hint only - not loaded at runtime
if TYPE_CHECKING:
    from agents.seo.research_analyst import ResearchAnalystAgent

router = APIRouter(
    prefix="/api/research",
    tags=["Research & Analysis"],
    dependencies=[Depends(require_current_user)],
)


def _raise_runtime_http(exc: Exception) -> None:
    if isinstance(exc, AIRuntimeServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if isinstance(exc, AIRuntimeResolutionError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if isinstance(exc, UserLLMCredentialError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/competitor-analysis",
    response_model=CompetitorAnalysisResponse,
    summary="Analyze competitors",
    description="""
    Analyze competitors for given keywords using SERP data and Exa AI.

    **What it does:**
    - Fetches top-ranking competitors
    - Analyzes their content strategy
    - Identifies content gaps
    - Recommends topics to cover

    **Returns:**
    - Competitor profiles with authority scores
    - Common topics across competitors
    - Content opportunities
    - Recommended topics for your site
    """
)
async def competitor_analysis(
    request: CompetitorAnalysisRequest,
    current_user: CurrentUser = Depends(require_current_user),
) -> Any:
    """Analyze competitors for given keywords using the Research Analyst agent."""
    start_time = time.time()
    keywords = request.normalized_keywords()
    if not keywords:
        raise HTTPException(
            status_code=400,
            detail="At least one keyword is required for competitor analysis.",
        )

    competitor_domains = request.normalized_competitor_domains()

    route_id = "research.competitor_analysis"
    try:
        resolution = await ai_runtime_service.preflight_providers(
            user_id=current_user.user_id,
            route=route_id,
            required_providers=["openrouter", "exa"],
            optional_providers=["firecrawl"],
        )
    except Exception as exc:
        _raise_runtime_http(exc)

    primary_keyword = keywords[0]

    try:
        with ai_runtime_service.bind_provider_env(resolution):
            llm = await user_llm_service.get_crewai_llm(
                current_user.user_id,
                model=DEFAULT_OPENROUTER_MODEL,
                route=route_id,
            )
            from agents.seo.research_analyst import ResearchAnalystAgent

            analyst = ResearchAnalystAgent(
                llm_model=llm,
                use_consensus_ai=request.use_consensus_ai,
                include_firecrawl_tools=resolution.has_optional_provider("firecrawl"),
            )
            if hasattr(analyst, "use_consensus_ai"):
                analyst.use_consensus_ai = request.use_consensus_ai
                if hasattr(analyst, "_create_agent"):
                    analyst.agent = analyst._create_agent()

            crew_result = analyst.run_analysis(
                target_keyword=primary_keyword,
                competitor_domains=competitor_domains or (keywords[1:] if len(keywords) > 1 else None),
            )

            raw_text = str(getattr(crew_result, "raw", crew_result))
            competitors, common_topics, content_opportunities, recommended_topics = _parse_analysis_output(
                raw_text, primary_keyword, keywords
            )
    except (AIRuntimeServiceError, AIRuntimeResolutionError, UserLLMCredentialError) as exc:
        _raise_runtime_http(exc)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ai_runtime_operator_provider_unavailable",
                "message": f"Competitor analysis failed before useful output: {exc}",
                "kind": "ai_runtime",
                "route": route_id,
                "retryable": True,
                "mode": resolution.mode,
                "provider": None,
                "settingsPath": None,
                "details": None,
            },
        ) from exc

    return CompetitorAnalysisResponse(
        keywords=keywords,
        competitors=competitors,
        common_topics=common_topics,
        content_opportunities=content_opportunities,
        recommended_topics=recommended_topics,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        processing_time_seconds=round(time.time() - start_time, 2),
    )


def _parse_analysis_output(
    raw: str,
    primary_keyword: str,
    keywords: list[str],
) -> tuple[list[CompetitorInfo], list[str], list[str], list[str]]:
    """
    Parse the markdown report from ResearchAnalystAgent into structured data.

    The agent returns a freeform markdown report. We extract:
    - Competitor domains mentioned (with dummy CompetitorInfo entries)
    - Common topics
    - Content opportunities / gaps
    - Recommended topics
    """
    competitors: list[CompetitorInfo] = []
    common_topics: list[str] = []
    content_opportunities: list[str] = []
    recommended_topics: list[str] = []

    lines = raw.splitlines()

    # --- Section detection ---
    # We track which section we are in to route bullet points correctly
    SECTION_NONE = 0
    SECTION_SERP = 1
    SECTION_TOPICS = 2
    SECTION_OPPORTUNITIES = 3
    SECTION_RECOMMENDATIONS = 4
    SECTION_GAPS = 5

    section = SECTION_NONE

    # Domain pattern — matches things like "competitor.com" in bullet points
    domain_re = re.compile(r'\b((?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b')

    competitor_domains: set[str] = set()

    # Add the first keyword as domain context if it looks like a domain
    for kw in keywords:
        if "." in kw and " " not in kw:
            competitor_domains.add(kw.replace("www.", ""))

    for line in lines:
        stripped = line.strip()

        # --- Detect section headers ---
        lower = stripped.lower()
        if re.match(r'#+\s+serp|#+\s+competitive|#+\s+competitor', lower):
            section = SECTION_SERP
        elif re.match(r'#+\s+common.topic|#+\s+topic.covered|#+\s+topic', lower):
            section = SECTION_TOPICS
        elif re.match(r'#+\s+content.opportunit|#+\s+opportunit|#+\s+content.gap', lower):
            section = SECTION_OPPORTUNITIES
        elif re.match(r'#+\s+gap', lower):
            section = SECTION_GAPS
        elif re.match(r'#+\s+recommend|#+\s+strategic.recommend', lower):
            section = SECTION_RECOMMENDATIONS
        elif stripped.startswith("#"):
            # Other header — reset section
            section = SECTION_NONE

        # --- Extract bullet points ---
        is_bullet = stripped.startswith(("- ", "* ", "• ")) or re.match(r'^\d+\.\s', stripped)
        if not is_bullet:
            continue

        # Remove bullet marker
        text = re.sub(r'^[-*•]\s+|^\d+\.\s+', '', stripped).strip()
        if not text:
            continue

        if section == SECTION_SERP:
            # Look for domain mentions in SERP results
            matches = domain_re.findall(text)
            for m in matches:
                if "." in m and m != primary_keyword:
                    competitor_domains.add(m.replace("www.", ""))

        elif section == SECTION_TOPICS:
            topic = _clean_bullet(text)
            if topic and topic not in common_topics:
                common_topics.append(topic)

        elif section in (SECTION_OPPORTUNITIES, SECTION_GAPS):
            opp = _clean_bullet(text)
            if opp and opp not in content_opportunities:
                content_opportunities.append(opp)

        elif section == SECTION_RECOMMENDATIONS:
            rec = _clean_bullet(text)
            if rec and rec not in recommended_topics:
                recommended_topics.append(rec)

    # Build CompetitorInfo objects from discovered domains
    for domain in list(competitor_domains)[:5]:
        try:
            competitors.append(
                CompetitorInfo(
                    domain=domain,
                    url=f"https://{domain}",  # type: ignore[arg-type]
                    topics_covered=common_topics[:3],
                    content_gaps=content_opportunities[:2],
                    strengths=[],
                    weaknesses=[],
                )
            )
        except Exception:
            pass

    # Fallbacks — if the agent output was too sparse, extract any bullet points globally
    if not common_topics:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                text = stripped[2:].strip()
                if 3 < len(text) < 80 and text not in common_topics:
                    common_topics.append(_clean_bullet(text))
                if len(common_topics) >= 6:
                    break

    if not recommended_topics:
        recommended_topics = common_topics[:3]

    return competitors, common_topics[:8], content_opportunities[:6], recommended_topics[:6]


def _clean_bullet(text: str) -> str:
    """Remove markdown formatting from a bullet point text."""
    # Remove bold/italic markers
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Truncate at colon (often used for "Topic: description" bullets)
    if ":" in text:
        text = text.split(":")[0].strip()
    return text[:120].strip()

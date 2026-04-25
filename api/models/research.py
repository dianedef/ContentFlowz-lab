"""Pydantic models for Research endpoints"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class CompetitorAnalysisRequest(BaseModel):
    """Request for competitor analysis"""
    keywords: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Keywords to analyze (1-10)",
        examples=[["SEO tools", "content marketing"]]
    )
    target_url: Optional[HttpUrl] = Field(
        default=None,
        description="Primary site URL from the Flutter research screen",
    )
    competitors: list[str] = Field(
        default_factory=list,
        description="Competitor URLs or domains from the Flutter research screen",
    )
    num_competitors: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of competitors to analyze"
    )
    include_serp_data: bool = Field(
        default=True,
        description="Include SERP rankings data"
    )
    use_consensus_ai: bool = Field(
        default=False,
        description="Use Consensus AI for scientific/academic research"
    )

    def normalized_keywords(self) -> list[str]:
        return [
            keyword.strip()
            for keyword in self.keywords
            if isinstance(keyword, str) and keyword.strip()
        ]

    def normalized_competitor_domains(self) -> list[str]:
        domains: list[str] = []
        for value in self.competitors:
            if not isinstance(value, str):
                continue
            raw = value.strip()
            if not raw:
                continue
            parsed = urlparse(raw if "://" in raw else f"https://{raw}")
            host = parsed.netloc or parsed.path
            host = host.replace("www.", "").strip().strip("/")
            if host:
                domains.append(host)
        return domains[: self.num_competitors]


class CompetitorInfo(BaseModel):
    """Information about a single competitor"""
    domain: str
    url: HttpUrl
    authority_score: Optional[int] = None
    backlinks: Optional[int] = None
    topics_covered: list[str] = []
    content_gaps: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []


class CompetitorAnalysisResponse(BaseModel):
    """Response from competitor analysis"""
    keywords: list[str]
    competitors: list[CompetitorInfo]
    
    common_topics: list[str]
    content_opportunities: list[str]
    recommended_topics: list[str]
    
    analysis_timestamp: str
    processing_time_seconds: float

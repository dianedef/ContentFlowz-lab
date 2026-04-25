"""Pydantic models for the Psychology Engine"""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Any, Optional
from enum import Enum

from api.models.user_data import PersonaCreateRequest


# ─────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────

class EntryType(str, Enum):
    reflection = "reflection"
    win = "win"
    struggle = "struggle"
    idea = "idea"
    pivot = "pivot"


class ContentType(str, Enum):
    article = "article"
    newsletter = "newsletter"
    video_script = "video_script"
    social_post = "social_post"
    short = "short"


# ─────────────────────────────────────────────────
# Creator Brain Models
# ─────────────────────────────────────────────────

class CreatorEntryInput(BaseModel):
    """Raw input from the creator's weekly ritual"""
    model_config = ConfigDict(populate_by_name=True)

    entry_type: EntryType = Field(
        default=EntryType.reflection,
        validation_alias=AliasChoices("entryType", "entry_type"),
        serialization_alias="entryType",
        description="Type of entry",
    )
    content: str = Field(..., description="Free-form text from the creator")
    tags: list[str] = Field(default_factory=list, description="Optional tags")

    def to_agent_payload(self) -> dict[str, Any]:
        return {
            "entryType": self.entry_type.value,
            "content": self.content,
            "tags": self.tags,
        }


class NarrativeSynthesisRequest(BaseModel):
    """Request to synthesize narrative from recent entries"""
    profile_id: str = Field(default="default", description="Creator profile ID")
    entries: list[CreatorEntryInput] = Field(default_factory=list, description="Raw ritual entries")
    entry_ids: list[str] = Field(default_factory=list, description="Legacy ritual entry payload")
    current_voice: Optional[dict] = Field(None, description="Current voice profile")
    current_positioning: Optional[dict] = Field(None, description="Current positioning")
    chapter_title: Optional[str] = Field(None, description="Current chapter title")

    def to_entry_payloads(self) -> list[dict[str, Any]]:
        if self.entries:
            return [
                entry.to_agent_payload()
                for entry in self.entries
                if entry.content.strip()
            ]

        return [
            {
                "entryType": EntryType.reflection.value,
                "content": str(entry_id),
                "tags": [],
            }
            for entry_id in self.entry_ids
            if str(entry_id).strip()
        ]


class NarrativeSynthesisResult(BaseModel):
    """Result of narrative synthesis by the Creator Psychologist agent"""
    voice_delta: dict = Field(default_factory=dict, description="Proposed changes to voice profile")
    positioning_delta: dict = Field(default_factory=dict, description="Proposed changes to positioning")
    narrative_summary: str = Field(..., description="Human-readable summary of what changed")
    chapter_transition: bool = Field(default=False, description="Whether a chapter transition is detected")
    suggested_chapter_title: Optional[str] = Field(None, description="New chapter title if transition detected")


class NarrativeReviewInput(BaseModel):
    """Creator's review decision on a narrative update"""
    update_id: str = Field(..., description="Narrative update ID")
    approved: bool = Field(..., description="Whether the creator approves the update")


# ─────────────────────────────────────────────────
# Customer Brain Models
# ─────────────────────────────────────────────────

class PersonaInput(BaseModel):
    """Input for creating or updating a customer persona"""
    name: str = Field(..., description="Persona name (e.g., 'Startup Steve')")
    avatar: Optional[str] = Field(None, description="Emoji or image URL")
    demographics: Optional[dict] = Field(None, description="Age range, role, industry, experience")
    pain_points: list[str] = Field(default_factory=list, description="Key pain points")
    goals: list[str] = Field(default_factory=list, description="Goals and aspirations")
    language: Optional[dict] = Field(None, description="Vocabulary, objections, triggers")
    content_preferences: Optional[dict] = Field(None, description="Formats, channels, frequency")
    confidence: int = Field(default=50, ge=0, le=100, description="Confidence score 0-100")


class PersonaRefinementRequest(BaseModel):
    """Request to refine a persona using analytics or behavioral data"""
    persona_id: str | None = Field(default=None, description="Persona ID to refine")
    current_persona: PersonaCreateRequest = Field(
        ...,
        validation_alias=AliasChoices("current_persona", "persona"),
        description="Current persona data",
    )
    analytics_data: Optional[dict] = Field(None, description="GA or similar analytics data")
    content_performance: Optional[list[dict]] = Field(None, description="Performance data for content targeting this persona")


# ─────────────────────────────────────────────────
# The Bridge Models
# ─────────────────────────────────────────────────

class AngleSuggestion(BaseModel):
    """A single content angle suggestion"""
    title: str = Field(..., description="Working title for the content piece")
    hook: str = Field(..., description="Opening hook or headline")
    angle: str = Field(..., description="The strategic angle — how creator narrative meets customer pain")
    content_type: ContentType = Field(default=ContentType.article, description="Suggested content format")
    narrative_thread: str = Field(..., description="Which part of the creator's story this draws from")
    pain_point_addressed: str = Field(..., description="Which customer pain point this addresses")
    confidence: int = Field(default=70, ge=0, le=100, description="Confidence score")
    priority_score: float = Field(default=50.0, ge=0, le=100, description="Computed priority score")
    seo_keyword: Optional[str] = Field(None, description="Primary SEO keyword if applicable")
    source_idea_ids: list[str] = Field(default_factory=list, description="Idea Pool IDs that contributed")


class AngleGenerationRequest(BaseModel):
    """Request to generate content angles by crossing creator + customer data"""
    profile_id: str | None = Field(default=None, description="Creator profile ID")
    persona_id: str | None = Field(default=None, description="Target customer persona ID")
    creator_voice: dict = Field(default_factory=dict, description="Creator's voice profile")
    creator_positioning: dict = Field(default_factory=dict, description="Creator's positioning")
    narrative_summary: Optional[str] = Field(None, description="Current narrative summary")
    persona_data: PersonaCreateRequest = Field(..., description="Customer persona data")
    content_type: Optional[ContentType] = Field(None, description="Limit to specific content type")
    count: int = Field(default=5, ge=1, le=10, description="Number of angles to generate")
    seo_signals: Optional[list[dict]] = Field(None, description="SEO keyword data (volume, difficulty, intent)")
    trending_signals: Optional[list[dict]] = Field(None, description="Trending topics from research or competitor watch")
    source_ideas: Optional[list[str]] = Field(None, description="Idea pool IDs that seeded this generation")


class ContentAngleResult(BaseModel):
    """Result from the Angle Strategist agent"""
    angles: list[AngleSuggestion] = Field(..., description="Generated content angles")
    strategy_note: str = Field(..., description="High-level strategy rationale")


class AngleSelectionInput(BaseModel):
    """Creator selects an angle for production"""
    angle_id: str = Field(..., description="Content angle ID")
    status: str = Field(..., description="New status: selected, used, or dismissed")


class MultiFormatExtract(BaseModel):
    """A selected angle rendered into multiple content formats (deprecated — use dispatch-pipeline)"""
    angle_id: str = Field(..., description="Source angle ID")
    article_outline: Optional[str] = Field(None, description="Full article outline")
    newsletter_hook: Optional[str] = Field(None, description="Newsletter intro paragraph")
    social_post: Optional[str] = Field(None, description="Social media post text")
    video_script_opener: Optional[str] = Field(None, description="Video script opening")


# ─────────────────────────────────────────────────
# Pipeline Dispatch Models
# ─────────────────────────────────────────────────

class PipelineDispatchRequest(BaseModel):
    """Request to dispatch an angle to a content generation pipeline"""
    angle_data: dict = Field(..., description="The full angle object from generation")
    target_format: str = Field(..., description="Target format: article, newsletter, short, social_post")
    creator_voice: Optional[dict] = Field(None, description="Creator's voice profile")
    seo_keyword: Optional[str] = Field(None, description="Primary SEO keyword for blog articles")
    project_id: Optional[str] = Field(None, description="Associated project ID")


class PipelineDispatchResult(BaseModel):
    """Result of pipeline dispatch (async — poll for completion)"""
    task_id: str = Field(..., description="Background task ID for polling")
    content_record_id: str = Field(..., description="Created ContentRecord ID")
    format: str = Field(..., description="Target format")
    status: str = Field(..., description="running, completed, or failed")

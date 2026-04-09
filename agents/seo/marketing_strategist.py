"""
Marketing Strategist Agent - Business Prioritization & ROI Analysis
Part of the SEO multi-agent system (Agent 5/6 - inserted before Editor)

Responsibilities:
- Create prioritization matrix aligned with business objectives
- Analyze potential ROI of SEO actions
- Provide strategic recommendations for competitive markets
- Validate marketing relevance of content
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.shared.prompt_loader import load_prompt
from agents.seo.tools.marketing_tools import (
    PrioritizationMatrix,
    ROIAnalyzer,
    CompetitivePositioning,
    MarketingValidator
)

load_dotenv()


class MarketingStrategistAgent:
    """
    Marketing Strategist Agent for business alignment and ROI optimization.
    Works between Technical SEO and Editor to ensure business value.
    Reviews content strategy and technical implementation for business impact.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Marketing Strategist with marketing tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.prioritization_matrix = PrioritizationMatrix()
        self.roi_analyzer = ROIAnalyzer()
        self.competitive_positioning = CompetitivePositioning()
        self.marketing_validator = MarketingValidator()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Marketing Strategist CrewAI agent with tools."""
        p = load_prompt("seo", "marketing_strategist")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[
                self.prioritization_matrix.create_priority_matrix,
                self.roi_analyzer.analyze_roi,
                self.competitive_positioning.assess_positioning,
                self.marketing_validator.validate_marketing_fit
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_strategy_task(
        self,
        content_strategy: str,
        article_content: str,
        technical_seo: str,
        business_goals: Optional[List[str]] = None,
        target_audience: Optional[str] = None,
        competitive_landscape: Optional[Dict[str, Any]] = None,
        budget_constraints: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Create a marketing strategy validation task.
        
        Args:
            content_strategy: Output from Content Strategist
            article_content: Output from Copywriter
            technical_seo: Output from Technical SEO Specialist
            business_goals: List of business objectives
            target_audience: Target audience description
            competitive_landscape: Competitive analysis data
            budget_constraints: Budget and resource constraints
            
        Returns:
            CrewAI Task configured for marketing strategy
        """
        description = f"""
        Review the content strategy, article, and technical SEO implementation from a 
        business and marketing perspective. Ensure alignment with business goals and 
        validate the potential ROI of this content investment.
        
        CONTENT STRATEGY OVERVIEW:
        {content_strategy[:1000]}...
        
        ARTICLE SUMMARY:
        {article_content[:800]}...
        
        TECHNICAL SEO ELEMENTS:
        {technical_seo[:600]}...
        
        YOUR STRATEGIC ANALYSIS DELIVERABLES:
        
        1. BUSINESS ALIGNMENT ASSESSMENT:
           - Evaluate how this content supports business objectives
           - Identify which stage of the buyer's journey it serves
           - Assess target audience fit and messaging alignment
           - Validate content positioning against brand strategy
           - Rate business relevance: High/Medium/Low
        """
        
        if business_goals:
            description += f"""
        2. GOAL ALIGNMENT ANALYSIS:
           Business Goals: {', '.join(business_goals)}
           
           For each goal, assess:
           - How this content contributes to achieving the goal
           - Expected impact (direct/indirect/minimal)
           - Timeline to see results (immediate/short-term/long-term)
           - Key metrics to track success
           - Potential bottlenecks or challenges
        """
        
        description += """
        3. ROI PROJECTION:
           - Estimate potential organic traffic (monthly)
           - Project conversion potential based on search intent
           - Calculate content creation cost vs. potential value
           - Assess payback period (when content becomes profitable)
           - Compare ROI to alternative marketing investments
           - Risk assessment: What could prevent ROI realization?
        
        4. PRIORITIZATION RECOMMENDATION:
           Create a priority score (0-100) based on:
           - Business impact potential (40%)
           - Resource efficiency (20%)
           - Competitive advantage (20%)
           - Time to results (10%)
           - Strategic fit (10%)
           
           Recommendation: High Priority / Medium Priority / Low Priority / Reconsider
        """
        
        if competitive_landscape:
            description += """
        5. COMPETITIVE POSITIONING:
           - How does this content differentiate us from competitors?
           - What unique value does it provide?
           - Will it help us gain competitive advantage?
           - Are we late to the topic or leading the conversation?
           - Recommended positioning strategy
        """
        
        if target_audience:
            description += f"""
        6. AUDIENCE ALIGNMENT:
           Target Audience: {target_audience}
           
           Validate:
           - Content speaks to audience pain points
           - Tone and complexity match audience sophistication
           - Examples and use cases resonate with audience
           - Call-to-action is appropriate for audience stage
           - Distribution channels align with where audience is
        """
        
        description += """
        7. STRATEGIC RECOMMENDATIONS:
           - Content optimization opportunities for higher business impact
           - Distribution and promotion strategy suggestions
           - Conversion optimization recommendations
           - Internal linking to high-value pages
           - Repurposing opportunities (webinar, email series, social)
           - Quick wins vs. long-term plays
        
        8. RISK ANALYSIS:
           - What could prevent this content from achieving goals?
           - Are we targeting the right keywords for business outcomes?
           - Is search volume sufficient for business impact?
           - Competitive risk: Can we realistically rank?
           - Brand risk: Any messaging concerns?
        
        9. SUCCESS METRICS & KPIs:
           Define specific, measurable KPIs:
           - Traffic metrics (sessions, users, pages/session)
           - Engagement metrics (time on page, scroll depth, CTR)
           - Conversion metrics (leads, signups, sales)
           - SEO metrics (rankings, impressions, featured snippets)
           - Business metrics (pipeline, revenue, customer acquisition cost)
           - Timeline: 30/60/90-day benchmarks
        
        DELIVERABLE FORMAT:
        Provide a comprehensive marketing strategy report with:
        - Executive Summary (business alignment score, priority level)
        - ROI Projection with assumptions and calculations
        - Prioritization Matrix (visual or structured format)
        - Strategic Recommendations (prioritized by impact)
        - Success Metrics Dashboard
        - Go/No-Go Recommendation with rationale
        
        DECISION FRAMEWORK:
        - HIGH PRIORITY: Strong business alignment, clear ROI path, competitive advantage
        - MEDIUM PRIORITY: Good potential but needs optimization or has moderate risk
        - LOW PRIORITY: Weak business case, better alternatives exist
        - RECONSIDER: Doesn't align with business goals, poor ROI potential, high risk
        
        Remember: You're the business conscience of this system. Traffic without conversions 
        is vanity. Rankings without revenue is meaningless. Every content piece must justify 
        its existence with clear business value. Be honest about weak business cases - it's 
        better to kill a weak idea than waste resources on content that won't move the needle.
        """
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                "A comprehensive marketing strategy report with business alignment assessment, "
                "ROI projection, priority scoring, competitive positioning analysis, success metrics, "
                "and clear Go/No-Go recommendation with strategic justification."
            )
        )
    
    def evaluate_strategy(
        self,
        content_strategy: str,
        article_content: str,
        technical_seo: str,
        business_goals: Optional[List[str]] = None,
        target_audience: Optional[str] = None,
        competitive_landscape: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute marketing strategy evaluation.
        
        Args:
            content_strategy: Content strategy from strategist
            article_content: Article from copywriter
            technical_seo: Technical SEO report
            business_goals: Business objectives
            target_audience: Target audience
            competitive_landscape: Competitive data
            
        Returns:
            Marketing strategy report with recommendations
        """
        task = self.create_strategy_task(
            content_strategy=content_strategy,
            article_content=article_content,
            technical_seo=technical_seo,
            business_goals=business_goals,
            target_audience=target_audience,
            competitive_landscape=competitive_landscape
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function
def validate_business_case(
    strategy: str,
    article: str,
    technical: str,
    business_goals: Optional[List[str]] = None
) -> str:
    """
    Quick function to validate business case for content.
    
    Args:
        strategy: Content strategy
        article: Article content
        technical: Technical SEO report
        business_goals: Business objectives
        
    Returns:
        Marketing strategy report
    """
    strategist = MarketingStrategistAgent()
    return strategist.evaluate_strategy(
        content_strategy=strategy,
        article_content=article,
        technical_seo=technical,
        business_goals=business_goals
    )


if __name__ == "__main__":
    print("=== Marketing Strategist Agent - Test Run ===\n")
    
    # Mock inputs for testing
    test_strategy = """
    Content Strategy: Build pillar content on "content marketing strategy"
    with 5 supporting cluster articles targeting SMB marketing managers.
    """
    
    test_article = """
    # Content Marketing Strategy Guide
    
    A comprehensive 2,500-word guide covering strategy frameworks,
    implementation tactics, and measurement approaches...
    """
    
    test_technical = """
    Technical SEO: Schema markup added, metadata optimized,
    internal linking strategy defined.
    """
    
    result = validate_business_case(
        strategy=test_strategy,
        article=test_article,
        technical=test_technical,
        business_goals=["Increase organic leads", "Establish thought leadership"]
    )
    
    print("\n=== MARKETING STRATEGY COMPLETE ===")
    print(result[:500] + "...")

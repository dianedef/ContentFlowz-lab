"""
Editor Agent - Quality Control & Final Harmonization
Part of the SEO multi-agent system (Agent 6/6)

Responsibilities:
- Validate content quality and grammar
- Ensure tone of voice and brand consistency
- Final harmonization before publication
- Format markdown and prepare for deployment
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.shared.prompt_loader import load_prompt
from agents.seo.tools.editing_tools import (
    QualityChecker,
    ConsistencyValidator,
    MarkdownFormatter,
    PublicationPreparer
)

load_dotenv()


class EditorAgent:
    """
    Editor Agent for final quality control and content harmonization.
    Final agent in the SEO content generation pipeline.
    Reviews all previous work and prepares content for publication.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Editor with editing tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.quality_checker = QualityChecker()
        self.consistency_validator = ConsistencyValidator()
        self.markdown_formatter = MarkdownFormatter()
        self.publication_preparer = PublicationPreparer()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Editor CrewAI agent with tools."""
        p = load_prompt("seo", "editor")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[
                self.quality_checker.check_quality,
                self.consistency_validator.validate_consistency,
                self.markdown_formatter.format_markdown,
                self.publication_preparer.prepare_for_publication
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_editing_task(
        self,
        article_content: str,
        technical_seo_report: str,
        brand_guidelines: Optional[Dict[str, Any]] = None,
        quality_standards: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Create a comprehensive editing and QA task.
        
        Args:
            article_content: Complete article from Copywriter
            technical_seo_report: Technical SEO recommendations
            brand_guidelines: Brand voice and style guidelines
            quality_standards: Quality criteria and thresholds
            
        Returns:
            CrewAI Task configured for final editing
        """
        description = f"""
        Perform final editorial review and prepare content for publication.
        
        ARTICLE TO REVIEW:
        {article_content[:1500]}...
        
        TECHNICAL SEO REPORT:
        {technical_seo_report[:800]}...
        
        YOUR EDITORIAL RESPONSIBILITIES:
        
        1. CONTENT QUALITY REVIEW:
           - Grammar and spelling (zero tolerance for errors)
           - Sentence structure and clarity
           - Paragraph flow and transitions
           - Logical argument progression
           - Factual accuracy and claims verification
           - Reading level appropriateness (target: 8th-9th grade)
           - Word choice precision and effectiveness
        
        2. CONSISTENCY VALIDATION:
           - Tone of voice consistency throughout
           - Terminology usage (consistent terms for same concepts)
           - Formatting consistency (lists, emphasis, capitalization)
           - Brand voice alignment
           - Style guide compliance
           - Heading hierarchy and structure
        
        3. SEO QUALITY ASSURANCE:
           - Keyword integration feels natural (not forced)
           - Metadata is compelling and accurate
           - Internal links are contextual and valuable
           - Heading structure supports SEO and readability
           - Content satisfies search intent
           - Schema markup is implemented correctly
        
        4. ENGAGEMENT OPTIMIZATION:
           - Hook strength (first 100 words)
           - Section-by-section engagement
           - Example quality and relevance
           - Call-to-action clarity and placement
           - Visual element suggestions
           - Scanability (headings, lists, formatting)
        """
        
        if brand_guidelines:
            description += f"""
        5. BRAND ALIGNMENT:
           - Voice: {brand_guidelines.get('voice', 'Not specified')}
           - Values: {', '.join(brand_guidelines.get('values', []))}
           - Tone: {brand_guidelines.get('tone', 'Not specified')}
           - Style notes: {brand_guidelines.get('style_notes', 'Not specified')}
           - Ensure content reflects brand personality
        """
        
        if quality_standards:
            description += f"""
        6. QUALITY STANDARDS VALIDATION:
           - Minimum word count: {quality_standards.get('min_words', 1500)}
           - Uniqueness target: {quality_standards.get('uniqueness', 90)}%
           - Readability score: {quality_standards.get('readability_target', 'Flesch 60-70')}
           - Error tolerance: {quality_standards.get('error_tolerance', 'Zero')}
        """
        
        description += """
        
        7. MARKDOWN FORMATTING:
           - Proper heading hierarchy (single H1, nested H2-H6)
           - Consistent list formatting
           - Proper link markdown syntax
           - Image placeholder formatting
           - Code block formatting if applicable
           - Frontmatter metadata (YAML)
           - Clean, valid markdown syntax
        
        8. PUBLICATION PREPARATION:
           - Finalize title and meta description
           - Verify all schema markup is included
           - Check all internal link placeholders are filled
           - Ensure image placeholders have descriptions
           - Add publication checklist
           - Flag any remaining TODOs or reviews needed
        
        DELIVERABLE FORMAT:
        Provide three outputs:
        
        A) EDITORIAL REPORT:
           - Issues found (categorized by severity: critical/major/minor)
           - Changes made and rationale
           - Quality scores (grammar, SEO, engagement, brand fit)
           - Overall content grade (A-F)
           - Publication readiness assessment
        
        B) FINAL ARTICLE (CLEAN):
           - Fully edited, publication-ready markdown
           - All metadata and frontmatter
           - Schema markup included
           - All links and images specified
           - Properly formatted and validated
        
        C) PUBLICATION CHECKLIST:
           - Pre-publication verification steps
           - Post-publication monitoring tasks
           - Success metrics to track
        
        EDITORIAL STANDARDS:
        - Every sentence must serve the reader
        - Zero grammatical or spelling errors
        - Consistent tone and voice throughout
        - Engaging from first word to last
        - SEO-optimized without feeling optimized
        - Ready to represent the brand publicly
        
        You are the last line of defense before publication. If you're not 100% confident
        the content meets our standards, flag it for revision. Excellence is non-negotiable.
        """
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                "Three documents: (1) Detailed editorial report with quality assessment, "
                "(2) Final, publication-ready article in markdown format, and "
                "(3) Publication checklist with verification steps."
            )
        )
    
    def edit_and_finalize(
        self,
        article_content: str,
        technical_seo_report: str,
        brand_guidelines: Optional[Dict[str, Any]] = None,
        quality_standards: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute final editing and prepare for publication.
        
        Args:
            article_content: Article to edit
            technical_seo_report: Technical SEO recommendations
            brand_guidelines: Brand guidelines
            quality_standards: Quality standards
            
        Returns:
            Editorial report, final article, and publication checklist
        """
        task = self.create_editing_task(
            article_content=article_content,
            technical_seo_report=technical_seo_report,
            brand_guidelines=brand_guidelines,
            quality_standards=quality_standards
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function
def finalize_article(
    article: str,
    technical_report: str,
    brand_voice: Optional[str] = None
) -> str:
    """
    Quick function to finalize article for publication.
    
    Args:
        article: Article content
        technical_report: Technical SEO report
        brand_voice: Brand voice description
        
    Returns:
        Final edited article with editorial report
    """
    editor = EditorAgent()
    
    brand_guidelines = {"voice": brand_voice} if brand_voice else None
    
    return editor.edit_and_finalize(
        article_content=article,
        technical_seo_report=technical_report,
        brand_guidelines=brand_guidelines
    )


if __name__ == "__main__":
    print("=== Editor Agent - Test Run ===\n")
    
    # Mock inputs for testing
    test_article = """
    # Content Marketing Strategy Guide
    
    Content marketing has become essential for businesses in 2024...
    
    ## What is Content Marketing
    Content marketing is the strategic approach...
    """
    
    test_technical = """
    Technical SEO Report:
    - Schema markup: Article schema generated
    - Metadata: All validated
    - Internal links: 3 opportunities identified
    """
    
    result = finalize_article(
        article=test_article,
        technical_report=test_technical,
        brand_voice="Professional but approachable"
    )
    
    print("\n=== EDITORIAL REVIEW COMPLETE ===")
    print(result[:500] + "...")

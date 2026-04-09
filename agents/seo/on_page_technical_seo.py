"""
On-Page Technical SEO Agent - Individual Page Optimization & Schema Markup
Part of the SEO multi-agent system (Agent 4/6)

Responsibilities:
- Generate schema.org structured data for NEW content
- Validate and optimize metadata for individual pages
- Recommend internal linking for new articles
- Optimize on-page technical factors during content creation

Note: For site-wide health monitoring, see scheduler/site_health_monitor.py
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.shared.prompt_loader import load_prompt
from agents.seo.tools.technical_tools import (
    SchemaGenerator,
    MetadataValidator,
    InternalLinkingAnalyzer,
    OnPageOptimizer
)

load_dotenv()


class OnPageTechnicalSEOAgent:
    """
    Technical SEO Specialist for on-page optimization and structured data.
    Fourth agent in the SEO content generation pipeline.
    Works with Copywriter output to add technical SEO elements.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Technical SEO Specialist with technical tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.schema_generator = SchemaGenerator()
        self.metadata_validator = MetadataValidator()
        self.linking_analyzer = InternalLinkingAnalyzer()
        self.onpage_optimizer = OnPageOptimizer()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Technical SEO Specialist CrewAI agent with tools."""
        p = load_prompt("seo", "technical_seo")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[
                self.schema_generator.generate_schema,
                self.metadata_validator.validate_metadata,
                self.linking_analyzer.analyze_internal_links,
                self.onpage_optimizer.optimize_onpage
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_technical_task(
        self,
        article_content: str,
        article_metadata: Dict[str, Any],
        site_structure: Optional[Dict[str, Any]] = None,
        existing_pages: Optional[List[str]] = None
    ) -> Task:
        """
        Create a technical SEO optimization task.
        
        Args:
            article_content: Written article content
            article_metadata: Metadata (title, description, keywords)
            site_structure: Site structure information
            existing_pages: List of existing pages for internal linking
            
        Returns:
            CrewAI Task configured for technical SEO
        """
        description = f"""
        Perform comprehensive technical SEO optimization for the provided article.
        
        ARTICLE METADATA:
        Title: {article_metadata.get('title', 'N/A')}
        Description: {article_metadata.get('description', 'N/A')}
        Keywords: {', '.join(article_metadata.get('keywords', []))}
        
        ARTICLE CONTENT:
        {article_content[:1000]}...
        
        YOUR TECHNICAL SEO DELIVERABLES:
        
        1. SCHEMA.ORG STRUCTURED DATA:
           - Generate Article schema with all required properties:
             * headline, description, author
             * datePublished, dateModified
             * image (suggest requirements)
             * publisher information
           - Add BreadcrumbList schema if applicable
           - Include FAQPage schema if article has Q&A sections
           - Validate JSON-LD syntax
           - Ensure compliance with Google's structured data guidelines
        
        2. METADATA VALIDATION:
           - Verify title tag length (50-60 characters optimal)
           - Check meta description length (150-160 characters)
           - Validate Open Graph tags for social sharing
           - Verify Twitter Card tags
           - Check for missing or duplicate metadata
           - Ensure keyword appears in metadata naturally
        
        3. ON-PAGE OPTIMIZATION:
           - Validate heading hierarchy (single H1, proper H2-H6 structure)
           - Check image alt text recommendations
           - Verify internal linking opportunities
           - Analyze keyword placement and density
           - Check URL structure recommendations
           - Validate semantic HTML usage
        """
        
        if existing_pages:
            description += f"""
        4. INTERNAL LINKING ANALYSIS:
           - Identify relevant pages to link to from: {', '.join(existing_pages[:5])}
           - Recommend optimal anchor text for internal links
           - Suggest contextual linking locations
           - Analyze link depth and crawl path
           - Ensure proper link equity distribution
        """
        
        if site_structure:
            description += """
        5. SITE ARCHITECTURE:
           - Validate article placement in site structure
           - Check breadcrumb implementation
           - Verify category and tag assignments
           - Ensure proper pagination if applicable
        """
        
        description += """
        
        6. TECHNICAL CHECKLIST:
           - Canonical URL specification
           - Mobile-friendliness considerations
           - Page speed optimization notes
           - Core Web Vitals impact assessment
           - Robots meta tag recommendations
           - XML sitemap inclusion verification
        
        DELIVERABLE FORMAT:
        Provide a comprehensive technical SEO report with:
        - Complete schema.org JSON-LD markup (ready to implement)
        - Validated metadata elements
        - On-page optimization checklist with issues and fixes
        - Internal linking recommendations with specific anchor text
        - Technical implementation notes
        - Priority list of fixes (high/medium/low)
        
        QUALITY STANDARDS:
        - All structured data must validate against schema.org standards
        - Metadata must follow Google's best practices
        - Recommendations must be specific and actionable
        - Include code snippets where applicable
        - Prioritize changes by SEO impact
        
        Remember: Technical SEO is the foundation that allows great content to rank.
        Your optimizations directly impact crawlability, indexation, and rankings.
        """
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                "A complete technical SEO optimization report with schema.org markup, "
                "validated metadata, on-page optimization recommendations, internal linking "
                "strategy, and prioritized action items with implementation code."
            )
        )
    
    def optimize_technical_seo(
        self,
        article_content: str,
        article_metadata: Dict[str, Any],
        site_structure: Optional[Dict[str, Any]] = None,
        existing_pages: Optional[List[str]] = None
    ) -> str:
        """
        Execute technical SEO optimization.
        
        Args:
            article_content: Article content to optimize
            article_metadata: Article metadata
            site_structure: Site structure info
            existing_pages: Existing pages for linking
            
        Returns:
            Technical SEO report with implementation code
        """
        task = self.create_technical_task(
            article_content=article_content,
            article_metadata=article_metadata,
            site_structure=site_structure,
            existing_pages=existing_pages
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function
def add_technical_seo(
    article: str,
    metadata: Dict[str, Any],
    existing_pages: Optional[List[str]] = None
) -> str:
    """
    Quick function to add technical SEO to article.
    
    Args:
        article: Article content
        metadata: Article metadata
        existing_pages: Pages for internal linking
        
    Returns:
        Technical SEO report
    """
    specialist = OnPageTechnicalSEOAgent()
    return specialist.optimize_technical_seo(
        article_content=article,
        article_metadata=metadata,
        existing_pages=existing_pages
    )


if __name__ == "__main__":
    print("=== Technical SEO Specialist - Test Run ===\n")
    
    # Mock article for testing
    test_article = """
    # Content Marketing Strategy Guide
    
    Content marketing is essential for modern businesses...
    
    ## What is Content Marketing
    Content marketing involves creating valuable content...
    """
    
    test_metadata = {
        "title": "Content Marketing Strategy Guide",
        "description": "Learn content marketing strategies...",
        "keywords": ["content marketing", "marketing strategy"]
    }
    
    result = add_technical_seo(
        article=test_article,
        metadata=test_metadata,
        existing_pages=["blog/seo-guide", "blog/social-media"]
    )
    
    print("\n=== TECHNICAL OPTIMIZATION COMPLETE ===")
    print(result[:500] + "...")

"""
Copywriter Agent - SEO-Optimized Content Generation
Part of the SEO multi-agent system (Agent 3/6)

Responsibilities:
- Write natural, engaging, SEO-optimized content
- Strategic keyword insertion without over-optimization
- Create compelling metadata (titles, descriptions)
- Adapt tone of voice to target audience
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.seo.tools.writing_tools import KeywordIntegrator
from agents.shared.tools.firecrawl_tools import scrape_url
from agents.shared.prompt_loader import load_prompt

load_dotenv()


class CopywriterAgent:
    """
    Copywriter Agent for SEO-optimized content creation.
    Third agent in the SEO content generation pipeline.
    Works with Content Strategist output to create final content.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Copywriter with writing tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.keyword_integrator = KeywordIntegrator()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Copywriter CrewAI agent with tools."""
        p = load_prompt("seo", "copywriter")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[
                self.keyword_integrator.integrate_keywords,
                scrape_url,
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_writing_task(
        self,
        content_outline: str,
        target_keywords: List[str],
        tone: str = "professional",
        brand_voice: Optional[str] = None,
        target_audience: Optional[str] = None,
        word_count: int = 2000
    ) -> Task:
        """
        Create a content writing task.
        
        Args:
            content_outline: Detailed outline from Content Strategist
            target_keywords: List of keywords to target
            tone: Desired tone (professional, casual, technical, friendly)
            brand_voice: Brand voice guidelines
            target_audience: Target audience description
            word_count: Target word count
            
        Returns:
            CrewAI Task configured for content writing
        """
        primary_keyword = target_keywords[0] if target_keywords else "topic"
        
        description = f"""
        Write a comprehensive, SEO-optimized article based on the following outline.
        
        PRIMARY KEYWORD: {primary_keyword}
        TARGET WORD COUNT: {word_count} words
        TONE: {tone}
        
        CONTENT OUTLINE:
        {content_outline[:2000]}...
        
        YOUR WRITING REQUIREMENTS:
        
        1. CONTENT QUALITY:
           - Write engaging, valuable content that serves the reader first
           - Use storytelling techniques to maintain interest
           - Include specific examples and actionable advice
           - Break up text with subheadings every 300-400 words
           - Use short paragraphs (3-4 sentences max) for readability
           - Add bullet points and numbered lists where appropriate
        
        2. SEO OPTIMIZATION:
           - Integrate primary keyword "{primary_keyword}" naturally (1-2% density)
           - Include target keywords: {', '.join(target_keywords[1:5])}
           - Place primary keyword in:
             * First 100 words
             * At least one H2 heading
             * Conclusion paragraph
           - Use semantic variations and related terms naturally
           - Never keyword stuff - prioritize natural language
        
        3. STRUCTURE:
           - Follow the provided outline structure
           - Create compelling H2 and H3 headings (include keywords where natural)
           - Write a strong introduction that hooks readers immediately
           - Add transitional phrases between sections for flow
           - End with clear conclusion and call-to-action
        """
        
        if brand_voice:
            description += f"""
        4. BRAND VOICE:
           - Maintain brand voice: {brand_voice}
           - Ensure consistency with brand values and messaging
           - Use appropriate industry terminology
        """
        
        if target_audience:
            description += f"""
        5. AUDIENCE ADAPTATION:
           - Target audience: {target_audience}
           - Write at appropriate knowledge level
           - Address audience pain points and questions
           - Use language and examples they relate to
        """
        
        description += """
        
        6. ENGAGEMENT ELEMENTS:
           - Include relevant statistics and data (cite sources)
           - Add 2-3 expert quotes or industry insights where fitting
           - Suggest 3-5 image placeholders [IMAGE: description]
           - Create 1-2 sections with FAQ-style Q&A if appropriate
           - Add internal linking suggestions [LINK: anchor text → target page]
        
        7. METADATA:
           - Generate compelling title tag (55-60 characters)
           - Write engaging meta description (155-160 characters)
           - Suggest 3-5 relevant tags/categories
        
        DELIVERABLE FORMAT:
        Return complete article in markdown format with:
        - Metadata section (title, description, keywords, tags)
        - Full article content with proper heading hierarchy
        - Image placeholders with descriptions
        - Internal linking suggestions
        - Call-to-action at the end
        
        WRITING STANDARDS:
        - Write for 8th-9th grade reading level (Flesch-Kincaid)
        - Use active voice (80%+ of sentences)
        - Vary sentence length for rhythm
        - Proof for grammar, spelling, clarity
        - Make every word count - no fluff
        
        Remember: Write for humans first, search engines second. Your goal is to create
        content so valuable that readers share it and link to it naturally.
        """
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                f"A complete, SEO-optimized article of approximately {word_count} words in markdown format "
                "with metadata, proper structure, keyword integration, image placeholders, internal links, "
                "and compelling copy that engages readers and satisfies search intent."
            )
        )
    
    def write_article(
        self,
        content_outline: str,
        target_keywords: List[str],
        tone: str = "professional",
        brand_voice: Optional[str] = None,
        target_audience: Optional[str] = None,
        word_count: int = 2000
    ) -> str:
        """
        Execute article writing based on outline.
        
        Args:
            content_outline: Content outline from strategist
            target_keywords: Target keywords list
            tone: Writing tone
            brand_voice: Brand voice guidelines
            target_audience: Target audience
            word_count: Target word count
            
        Returns:
            Complete article in markdown format
        """
        task = self.create_writing_task(
            content_outline=content_outline,
            target_keywords=target_keywords,
            tone=tone,
            brand_voice=brand_voice,
            target_audience=target_audience,
            word_count=word_count
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function for direct usage
def write_seo_article(
    outline: str,
    keywords: List[str],
    tone: str = "professional",
    word_count: int = 2000
) -> str:
    """
    Quick function to write SEO article from outline.
    
    Args:
        outline: Content outline
        keywords: Target keywords
        tone: Writing tone
        word_count: Target word count
        
    Returns:
        Complete article in markdown
    """
    copywriter = CopywriterAgent()
    return copywriter.write_article(
        content_outline=outline,
        target_keywords=keywords,
        tone=tone,
        word_count=word_count
    )


if __name__ == "__main__":
    # Example usage
    print("=== Copywriter Agent - Test Run ===\n")
    
    # Mock outline for testing
    outline = """
    # Content Marketing Strategy Guide
    
    ## Introduction (200 words)
    - Hook: Content marketing statistics
    - What is content marketing strategy
    - Why it matters for businesses
    
    ## What is Content Marketing Strategy (400 words)
    - Definition
    - Core components
    - Difference from tactics
    
    ## Building a Content Strategy (500 words)
    - Audience research
    - Goal setting
    - Content planning
    - Distribution channels
    
    ## Best Practices (400 words)
    - Consistency
    - Quality over quantity
    - Data-driven decisions
    - Continuous optimization
    
    ## Conclusion (200 words)
    - Recap key points
    - Call to action
    """
    
    result = write_seo_article(
        outline=outline,
        keywords=["content marketing strategy", "content strategy", "marketing plan"],
        tone="professional",
        word_count=2000
    )
    
    print("\n=== ARTICLE COMPLETE ===")
    print(result[:500] + "...")

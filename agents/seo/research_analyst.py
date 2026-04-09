"""
Research Analyst Agent - Competitive Intelligence & SEO Opportunity Identification
Part of the SEO multi-agent system (Agent 1/6)

Responsibilities:
- SERP analysis and competitive positioning
- Sector trend monitoring and seasonality
- Content gap identification and keyword opportunities
- Ranking pattern extraction and success factors
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.seo.tools.research_tools import (
    SERPAnalyzer,
    TrendMonitor,
    KeywordGapFinder,
    RankingPatternExtractor,
    ConsensusResearcher,
    analyze_serp_tool,
    monitor_trends_tool,
    identify_keyword_gaps_tool,
    extract_ranking_patterns_tool,
    consensus_deep_search_tool
)
from agents.seo.config.research_config import AI_TOOL_SETTINGS
from agents.shared.tools.exa_tools import exa_search, exa_find_similar
from agents.shared.tools.firecrawl_tools import scrape_url, crawl_site
from agents.shared.prompt_loader import load_prompt

load_dotenv()


class ResearchAnalystAgent:
    """
    Research Analyst Agent for competitive intelligence and SEO analysis.
    First agent in the SEO content generation pipeline.
    """
    
    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768", use_consensus_ai: Optional[bool] = None):
        """
        Initialize Research Analyst with research tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
            use_consensus_ai: Whether to use Consensus AI tool (default: from config)
        """
        self.llm_model = llm_model
        self.use_consensus_ai = use_consensus_ai if use_consensus_ai is not None else AI_TOOL_SETTINGS.get("use_consensus_ai", False)

        # Initialize tools
        self.serp_analyzer = SERPAnalyzer()
        self.trend_monitor = TrendMonitor()
        self.gap_finder = KeywordGapFinder()
        self.pattern_extractor = RankingPatternExtractor()
        self.consensus_researcher = ConsensusResearcher()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Research Analyst CrewAI agent with tools."""
        tools = [
            analyze_serp_tool,
            monitor_trends_tool,
            identify_keyword_gaps_tool,
            extract_ranking_patterns_tool,
            exa_search,
            exa_find_similar,
            scrape_url,
            crawl_site,
        ]

        if self.use_consensus_ai:
            tools.append(consensus_deep_search_tool)
            
        p = load_prompt("seo", "research_analyst")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=tools,
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_analysis_task(
        self,
        target_keyword: str,
        competitor_domains: Optional[List[str]] = None,
        sector: Optional[str] = None,
        target_domain: Optional[str] = None
    ) -> Task:
        """
        Create a comprehensive SEO analysis task.
        
        Args:
            target_keyword: Primary keyword to analyze
            competitor_domains: List of competitor domains (optional)
            sector: Industry sector for trend analysis (optional)
            target_domain: Your domain for gap analysis (optional)
            
        Returns:
            CrewAI Task configured for research analysis
        """
        competitor_section = ""
        if competitor_domains:
            competitor_section = (
                f"\n      3. KEYWORD GAP ANALYSIS:\n"
                f"         - Compare against competitors: {', '.join(competitor_domains)}\n"
                f"         - Identify keyword opportunities where competitors rank but target domain doesn't\n"
                f"         - Prioritize gaps by opportunity score\n"
                f"         - Suggest content types for each gap\n"
            )

        sector_section = ""
        if sector:
            sector_section = (
                f"\n      4. TREND MONITORING:\n"
                f"         - Monitor trends in {sector} sector\n"
                f"         - Identify emerging keywords and topics\n"
                f"         - Detect seasonal patterns\n"
                f"         - Provide strategic recommendations\n"
            )

        p = load_prompt("seo", "research_analyst")
        task_cfg = p["tasks"]["analysis"]
        description = task_cfg["description"].format(
            target_keyword=target_keyword,
            competitor_section=competitor_section,
            sector_section=sector_section,
        )

        return Task(
            description=description,
            agent=self.agent,
            expected_output=task_cfg["expected_output"],
        )
    
    def run_analysis(
        self,
        target_keyword: str,
        competitor_domains: Optional[List[str]] = None,
        sector: Optional[str] = None,
        target_domain: Optional[str] = None
    ) -> str:
        """
        Execute a complete competitive analysis.
        
        Args:
            target_keyword: Primary keyword to analyze
            competitor_domains: List of competitor domains (optional)
            sector: Industry sector for trend analysis (optional)
            target_domain: Your domain for gap analysis (optional)
            
        Returns:
            Markdown report with analysis results
        """
        task = self.create_analysis_task(
            target_keyword=target_keyword,
            competitor_domains=competitor_domains,
            sector=sector,
            target_domain=target_domain
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function for direct usage
def analyze_keyword(
    keyword: str,
    competitors: Optional[List[str]] = None,
    sector: Optional[str] = None,
    your_domain: Optional[str] = None
) -> str:
    """
    Quick function to analyze a keyword with Research Analyst.
    
    Args:
        keyword: Target keyword to analyze
        competitors: Competitor domains (optional)
        sector: Industry sector (optional)
        your_domain: Your domain (optional)
        
    Returns:
        Analysis report in markdown
    """
    analyst = ResearchAnalystAgent()
    return analyst.run_analysis(
        target_keyword=keyword,
        competitor_domains=competitors,
        sector=sector,
        target_domain=your_domain
    )


if __name__ == "__main__":
    # Example usage
    print("=== Research Analyst Agent - Test Run ===\n")
    
    result = analyze_keyword(
        keyword="content marketing strategy",
        competitors=["hubspot.com", "contentmarketinginstitute.com", "semrush.com"],
        sector="Digital Marketing"
    )
    
    print("\n=== ANALYSIS COMPLETE ===")
    print(result)

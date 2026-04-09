"""
Internal Linking Specialist Agent - SEO & Conversion Optimization
Part of SEO multi-agent system (Agent 6/7 - positioned after Marketing Strategist)

Responsibilities:
- Optimize internal linking for both SEO authority and conversion paths
- Balance 50% new link opportunities with 50% existing link optimization
- Prioritize conversion optimization (70% conversion, 30% SEO focus)
- Implement full personalization with progressive profiling
- Create hybrid business objective links (leads, demos, sales)
"""
from typing import List, Optional, Dict, Any, Literal
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os

from agents.seo.tools.internal_linking import (
    LinkingAnalyzer,
    ConversionOptimizer,
    PersonalizationEngine,
    AutomatedInserter,
    FunnelIntegrator,
    MaintenanceTracker
)

from agents.seo.tools.local_link_checker import LocalLinkChecker
from agents.shared.prompt_loader import load_prompt

from agents.seo.config.internal_linking_config import (
    InternalLinkingConfiguration,
    ConfigurationManager
)

load_dotenv()


class InternalLinkingSpecialistAgent:
    """
    Internal Linking Specialist Agent for SEO and conversion optimization.

    Mission: Optimize internal linking strategy to maximize both SEO authority
    and conversion rates through intelligent, personalized linking strategies.

    Position in workflow: After Marketing Strategist, before Technical SEO
    Balance: 50% new links + 50% existing optimization
    Focus: 70% conversion optimization, 30% SEO authority
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Internal Linking Specialist with linking tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Core Tool Suites (following existing pattern)
        self.link_analyzer = LinkingAnalyzer()  # SEO-focused analysis
        self.conversion_optimizer = ConversionOptimizer()  # Conversion-focused optimization
        self.personalization_engine = PersonalizationEngine()  # User profiling
        self.automated_inserter = AutomatedInserter()  # Automatic link insertion
        self.funnel_integrator = FunnelIntegrator()  # Marketing funnel integration
        self.maintenance_tracker = MaintenanceTracker()  # Link health monitoring
        self.local_link_checker = LocalLinkChecker()  # Local-first pre-deploy link validation

        # Configuration management
        self.config_manager = ConfigurationManager()
        self.default_config = InternalLinkingConfiguration()

        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Internal Linking Specialist CrewAI agent with tools."""
        p = load_prompt("seo", "internal_linking_specialist")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=[
                self.link_analyzer.analyze_linking_opportunities,
                self.conversion_optimizer.optimize_conversion_paths,
                self.personalization_engine.generate_personalized_links,
                self.automated_inserter.insert_links_automatically,
                self.funnel_integrator.map_funnel_touchpoints,
                self.maintenance_tracker.audit_existing_links,
                self.local_link_checker.check_local_links,
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )
    
    def create_linking_strategy_task(
        self,
        marketing_strategy: str,  # From Marketing Strategist
        content_inventory: List[Dict[str, Any]],  # From Content Strategist  
        technical_seo: str,  # From Technical SEO Specialist
        business_goals: List[str],  # From Marketing Strategist
        conversion_objectives: List[str],  # From Marketing Strategist
        target_audience: str,
        scope: Literal["new_content_only", "include_existing", "full_site"] = "include_existing",
        personalization_level: Literal["basic", "intermediate", "advanced", "full"] = "intermediate",
        conversion_focus: float = 0.7  # 70% conversion focus by default
    ) -> Task:
        """
        Create comprehensive internal linking strategy task that incorporates marketing insights.
        
        Args:
            marketing_strategy: Output from Marketing Strategist agent
            content_inventory: List of content pages with metadata
            technical_seo: Technical SEO constraints and requirements
            business_goals: Primary business objectives
            conversion_objectives: Specific conversion goals
            target_audience: Target audience description
            scope: Analysis scope for linking optimization
            personalization_level: Level of personalization to implement
            conversion_focus: Balance between conversion vs SEO (0.3-0.9)
            
        Returns:
            CrewAI Task configured for internal linking strategy
        """
        description = f"""
        Develop a comprehensive internal linking strategy that balances SEO authority 
        with conversion optimization, using marketing insights for funnel integration.
        
        MARKETING STRATEGY INPUTS:
        {marketing_strategy[:1000]}...
        
        CONTENT INVENTORY:
        {len(content_inventory)} pages available for linking
        
        TECHNICAL SEO CONSTRAINTS:
        {technical_seo[:600]}...
        
        BUSINESS GOALS:
        {', '.join(business_goals)}
        
        CONVERSION OBJECTIVES:
        {', '.join(conversion_objectives)}
        
        TARGET AUDIENCE:
        {target_audience}
        
        SCOPE AND CONFIGURATION:
        - Analysis Scope: {scope}
        - Personalization Level: {personalization_level}
        - Conversion Focus: {conversion_focus * 100}% (vs {(1-conversion_focus) * 100}% SEO)
        
        YOUR STRATEGIC DELIVERABLES:
        
        1. DUAL-OBJECTIVE ANALYSIS (50/50 SEO vs Conversion):
           - SEO Authority Distribution: 50% focus
           - Conversion Path Optimization: 50% focus  
           - Balance Score: Target {conversion_focus * 100}% conversion focus, {(1-conversion_focus) * 100}% SEO focus
           - Integration Opportunities: Where both objectives align
        
        2. NEW LINK OPPORTUNITIES (50% of effort):
           - Pillar-to-cluster links for authority flow
           - Conversion-focused links for business objectives
           - Funnel progression links for user journey
           - Personalization opportunities for segments
           - Each opportunity rated for SEO vs conversion impact
        
        3. EXISTING LINK OPTIMIZATION (50% of effort):
           - Audit current internal linking structure
           - Identify underperforming links
           - Optimize anchor text for conversion
           - Update link placement for better visibility
           - Remove or fix broken/irrelevant links
        
        4. CONVERSION OPTIMIZATION ({conversion_focus * 100:.0f}% weight):
           - Map links to conversion funnel stages
           - Identify high-intent linking opportunities
           - Optimize CTAs within link context
           - Create conversion-focused link clusters
           - Track conversion attribution per link
        
        5. PERSONALIZATION ENGINE ({personalization_level} level):
           - Progressive profile building strategy
           - Behavioral data integration points
           - Dynamic link insertion rules
           - Segment-specific linking approaches
           - Real-time personalization triggers
        
        6. BUSINESS OBJECTIVE INTEGRATION (Hybrid Approach):
           - Lead Generation: Contact form, webinar links
           - Demo/Trial: Product tour, free trial links  
           - Sales: Pricing, consultation, case study links
           - Thought Leadership: Research, whitepaper links
           - Customer Success: Support, training links
        
        7. MARKETING FUNNEL INTEGRATION:
           - Awareness stage: Educational linking
           - Consideration stage: Comparison and demo links
           - Decision stage: Trial and purchase links
           - Retention stage: Support and upsell links
           - Advocacy stage: Referral and community links
        
        SCOPE-SPECIFIC REQUIREMENTS:
        {"Only analyze new content opportunities" if scope == "new_content_only" else 
         "Analyze both new opportunities and existing optimization" if scope == "include_existing" else
         "Comprehensive site-wide analysis including all content"}
        
        DELIVERABLE FORMAT:
        Provide a complete internal linking strategy with:
        - Executive Summary (balance score, opportunity overview)
        - Detailed Linking Matrix (pages, links, objectives, priority)
        - Conversion Path Maps (user journey with link touchpoints)
        - Personalization Rules (segmentation, triggers, content)
        - Implementation Roadmap (phases, timeline, resources)
        - Performance Dashboard (metrics, targets, monitoring)
        
        Remember: You're bridging SEO expertise with conversion optimization. 
        Every link should serve both search engines and business objectives. 
        Personalization should enhance, not complicate, the user experience.
        """
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                "A comprehensive internal linking strategy with SEO/conversion balance, "
                "personalization engine, automation plan, funnel integration, and "
                "clear implementation roadmap with success metrics."
            )
        )
    
    def generate_linking_strategy(
        self,
        content_inventory: List[Dict[str, Any]],
        business_goals: List[str],
        conversion_objectives: List[str],
        target_audience: str,
        scope: Literal["new_content_only", "include_existing", "full_site"] = "include_existing",
        personalization_level: Literal["basic", "intermediate", "advanced", "full"] = "intermediate",
        conversion_focus: float = 0.7,
        existing_links_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Execute comprehensive internal linking strategy generation.
        
        Args:
            content_inventory: Content inventory with metadata
            business_goals: Business objectives from marketing strategy
            conversion_objectives: Specific conversion goals
            target_audience: Target audience description
            scope: Analysis scope configuration
            personalization_level: Personalization maturity level
            conversion_focus: Balance between conversion vs SEO
            existing_links_data: Current internal links data
            
        Returns:
            Comprehensive internal linking strategy dictionary
        """
        
        # Get configuration
        config = self.config_manager.get_config(
            custom_settings={
                "analysis_scope": scope,
                "personalization_level": personalization_level,
                "conversion_focus": conversion_focus
            }
        )
        
        # 1. Linking Analysis (SEO-focused)
        linking_analysis = self.link_analyzer.analyze_linking_opportunities(
            content_inventory=content_inventory,
            business_goals=business_goals,
            target_audience=target_audience,
            scope=scope,
            existing_links_data=existing_links_data
        )
        
        # 2. Conversion Optimization (Conversion-focused)
        conversion_optimization = self.conversion_optimizer.optimize_conversion_paths(
            linking_analysis=linking_analysis,
            conversion_goals=conversion_objectives,
            business_goals=business_goals,
            conversion_focus=conversion_focus
        )
        
        # 3. Personalization Engine
        personalization_strategy = self.personalization_engine.create_progressive_profiling_system(
            linking_strategy=linking_analysis,
            conversion_optimization=conversion_optimization,
            personalization_level=personalization_level,
            target_audience=target_audience
        )
        
        # 4. Automated Insertion Plan
        insertion_plan = self.automated_inserter.create_insertion_strategy(
            optimized_strategy=conversion_optimization,
            content_files=[content.get("file_path") for content in content_inventory if content.get("file_path")],
            insertion_mode="preview"  # Preview by default
        )
        
        # 5. Funnel Integration
        funnel_integration = self.funnel_integrator.integrate_funnel_strategy(
            linking_strategy=linking_analysis,
            business_objectives=business_goals,
            conversion_objectives=conversion_objectives,
            target_audience=target_audience
        )
        
        # 6. Maintenance Strategy
        maintenance_plan = self.maintenance_tracker.create_maintenance_strategy(
            linking_strategy=linking_analysis,
            existing_links_data=existing_links_data
        )
        
        # Combine into comprehensive strategy
        comprehensive_strategy = {
            "strategy_id": f"linking_strategy_{os.urandom(4).hex()}",
            "generated_at": str(os.times()),
            "configuration": {
                "scope": scope,
                "personalization_level": personalization_level,
                "conversion_focus": conversion_focus,
                "new_vs_existing_split": config.new_vs_existing_split
            },
            "linking_analysis": linking_analysis,
            "conversion_optimization": conversion_optimization,
            "personalization_strategy": personalization_strategy,
            "insertion_plan": insertion_plan,
            "funnel_integration": funnel_integration,
            "maintenance_plan": maintenance_plan,
            "business_goals": business_goals,
            "conversion_objectives": conversion_objectives,
            "target_audience": target_audience,
            "metrics": {
                "total_content_pages": len(content_inventory),
                "new_opportunities": len(linking_analysis.get("new_opportunities", [])),
                "existing_optimizations": len(linking_analysis.get("existing_optimizations", [])),
                "conversion_focus_score": conversion_focus,
                "personalization_maturity": personalization_strategy.get("maturity_score", 0.0)
            }
        }
        
        return comprehensive_strategy
    
    def run_linking_analysis(
        self,
        marketing_strategy: str,
        content_inventory: List[Dict[str, Any]], 
        technical_seo: str,
        business_goals: List[str],
        conversion_objectives: List[str],
        target_audience: str,
        **kwargs
    ) -> str:
        """
        Execute internal linking strategy planning.
        
        Args:
            marketing_strategy: Output from Marketing Strategist agent
            content_inventory: Content pages with metadata
            technical_seo: Technical SEO requirements
            business_goals: Business objectives
            conversion_objectives: Conversion goals
            target_audience: Target audience
            **kwargs: Additional configuration options
            
        Returns:
            Comprehensive internal linking strategy document
        """
        task = self.create_linking_strategy_task(
            marketing_strategy=marketing_strategy,
            content_inventory=content_inventory,
            technical_seo=technical_seo,
            business_goals=business_goals,
            conversion_objectives=conversion_objectives,
            target_audience=target_audience,
            **kwargs
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return result


# Convenience function for direct usage
def create_internal_linking_strategy(
    content_inventory: List[Dict[str, Any]],
    business_goals: List[str],
    conversion_objectives: List[str],
    target_audience: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Quick function to create internal linking strategy.
    
    Args:
        content_inventory: Content inventory with metadata
        business_goals: Business objectives
        conversion_objectives: Conversion goals
        target_audience: Target audience description
        **kwargs: Additional configuration options
        
    Returns:
        Internal linking strategy dictionary
    """
    specialist = InternalLinkingSpecialistAgent()
    return specialist.generate_linking_strategy(
        content_inventory=content_inventory,
        business_goals=business_goals,
        conversion_objectives=conversion_objectives,
        target_audience=target_audience,
        **kwargs
    )


if __name__ == "__main__":
    # Example usage
    print("=== Internal Linking Specialist Agent - Test Run ===\n")
    
    # Mock content inventory for testing
    content_inventory = [
        {
            "url": "https://example.com/content-marketing-guide",
            "title": "Complete Content Marketing Guide",
            "type": "pillar_page",
            "word_count": 3500,
            "current_internal_links": 12,
            "business_goal": "educate"
        },
        {
            "url": "https://example.com/content-strategy-tips",
            "title": "10 Content Strategy Tips", 
            "type": "cluster_page",
            "word_count": 1200,
            "current_internal_links": 5,
            "business_goal": "lead_generation"
        }
    ]
    
    result = create_internal_linking_strategy(
        content_inventory=content_inventory,
        business_goals=["Increase organic traffic", "Generate qualified leads"],
        conversion_objectives=["lead_generation", "demo_request"],
        target_audience="Marketing professionals at mid-size companies",
        scope="include_existing",
        personalization_level="intermediate",
        conversion_focus=0.7
    )
    
    print("\n=== STRATEGY COMPLETE ===")
    print(f"Strategy ID: {result.get('strategy_id')}")
    print(f"New Opportunities: {result.get('metrics', {}).get('new_opportunities', 0)}")
    print(f"Existing Optimizations: {result.get('metrics', {}).get('existing_optimizations', 0)}")
    print(f"Conversion Focus: {result.get('configuration', {}).get('conversion_focus', 0.7) * 100}%")
"""
SEO Content Generation Crew - Hierarchical Multi-Agent Workflow
Orchestrates all 6 SEO agents in a sequential pipeline.

Pipeline: Research → Strategy → Writing → Technical → Marketing → Editing
"""
from typing import Any, Dict, List, Optional
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
import os
from datetime import datetime

# Import all agents
from agents.seo.research_analyst import ResearchAnalystAgent
from agents.seo.content_strategist import ContentStrategistAgent
from agents.seo.copywriter import CopywriterAgent
from agents.seo.on_page_technical_seo import OnPageTechnicalSEOAgent
from agents.seo.marketing_strategist import MarketingStrategistAgent
from agents.seo.editor import EditorAgent

# Pydantic output schemas for structured inter-agent context
from agents.seo.schemas.pipeline_outputs import (
    ResearchOutput,
    StrategyOutput,
    WritingOutput,
    TechnicalOutput,
    MarketingOutput,
    EditingOutput,
)
from status.audit import actor_from_agent

load_dotenv()

# Conditional status tracking (graceful degradation)
try:
    from status import get_status_service
    STATUS_AVAILABLE = True
except ImportError:
    STATUS_AVAILABLE = False


class SEOContentCrew:
    """
    Hierarchical multi-agent system for SEO content generation.
    Coordinates 6 specialized agents to produce publication-ready content.
    """
    
    def __init__(
        self,
        llm_model: Any = "mixtral-8x7b-32768",
        use_consensus_ai: bool = False,
        track_status: bool = True,
        include_firecrawl_tools: bool = True,
    ):
        """
        Initialize SEO Content Crew with all agents.
        
        Args:
            llm_model: Groq model to use for all agents
            use_consensus_ai: Whether to use Consensus AI for research
        """
        self.llm_model = llm_model
        self.track_status = track_status
        
        # Initialize all agents
        print("Initializing SEO Content Crew...")
        self.research_agent = ResearchAnalystAgent(
            llm_model,
            use_consensus_ai=use_consensus_ai,
            include_firecrawl_tools=include_firecrawl_tools,
        )
        self.strategy_agent = ContentStrategistAgent(llm_model)
        self.copywriter_agent = CopywriterAgent(llm_model)
        self.technical_agent = OnPageTechnicalSEOAgent(llm_model)
        self.marketing_agent = MarketingStrategistAgent(llm_model)
        self.editor_agent = EditorAgent(llm_model)
        
        print("✅ All 6 agents initialized")
    
    def generate_content(
        self,
        target_keyword: str,
        competitor_domains: Optional[List[str]] = None,
        sector: Optional[str] = None,
        business_goals: Optional[List[str]] = None,
        brand_voice: Optional[str] = None,
        target_audience: Optional[str] = None,
        word_count: int = 2500,
        tone: str = "professional",
        existing_content: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate complete SEO-optimized content through multi-agent workflow.
        
        Args:
            target_keyword: Primary keyword to target
            competitor_domains: Competitor domains for analysis
            sector: Industry sector
            business_goals: Business objectives
            brand_voice: Brand voice description
            target_audience: Target audience description
            word_count: Target word count
            tone: Writing tone
            existing_content: Existing content for internal linking
            
        Returns:
            Dictionary with all outputs from each agent
        """
        print("\n" + "="*60)
        print("SEO CONTENT GENERATION PIPELINE")
        print("="*60)
        print(f"Target Keyword: {target_keyword}")
        print(f"Word Count: {word_count}")
        print(f"Tone: {tone}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")

        # Status tracking: create content record
        status_record_id = None
        if self.track_status and STATUS_AVAILABLE:
            try:
                status_svc = get_status_service()
                record = status_svc.create_content(
                    title=f"SEO: {target_keyword}",
                    content_type="seo-content",
                    source_robot="seo",
                    status="in_progress",
                    tags=[target_keyword] + (business_goals or []),
                    metadata={
                        "target_keyword": target_keyword,
                        "word_count": word_count,
                        "tone": tone,
                        "sector": sector,
                        "competitor_domains": competitor_domains or [],
                    },
                )
                status_record_id = record.id
                print(f"📊 Status tracking: record {record.id} created (in_progress)")
            except Exception as e:
                print(f"⚠ Status tracking init failed (non-critical): {e}")

        results = {
            "input": {
                "target_keyword": target_keyword,
                "competitor_domains": competitor_domains,
                "sector": sector,
                "business_goals": business_goals,
                "word_count": word_count
            },
            "outputs": {}
        }

        # Build shared keyword list
        keywords = [target_keyword]
        if sector:
            keywords.append(f"{target_keyword} {sector}")

        # --- Create all tasks (no kickoff between them) ---

        research_task = self.research_agent.create_analysis_task(
            target_keyword=target_keyword,
            competitor_domains=competitor_domains,
            sector=sector,
            target_domain=existing_content[0] if existing_content else None,
        )
        research_task.output_pydantic = ResearchOutput

        strategy_task = self.strategy_agent.create_strategy_task(
            target_keyword=target_keyword,
            existing_content=existing_content,
            business_goals=business_goals,
            content_count=5,
        )
        strategy_task.context = [research_task]
        strategy_task.output_pydantic = StrategyOutput

        writing_task = self.copywriter_agent.create_writing_task(
            target_keywords=keywords,
            tone=tone,
            brand_voice=brand_voice,
            target_audience=target_audience,
            word_count=word_count,
        )
        writing_task.context = [research_task, strategy_task]
        writing_task.output_pydantic = WritingOutput

        metadata = {
            "title": f"{target_keyword} - Complete Guide",
            "description": f"Learn everything about {target_keyword}",
            "keywords": keywords,
        }

        technical_task = self.technical_agent.create_technical_task(
            article_metadata=metadata,
            existing_pages=existing_content,
        )
        technical_task.context = [writing_task]
        technical_task.output_pydantic = TechnicalOutput

        marketing_task = self.marketing_agent.create_strategy_task(
            business_goals=business_goals,
            target_audience=target_audience,
        )
        marketing_task.context = [strategy_task, writing_task, technical_task]
        marketing_task.output_pydantic = MarketingOutput

        brand_guidelines = None
        if brand_voice:
            brand_guidelines = {
                "voice": brand_voice,
                "tone": tone,
                "values": business_goals or [],
            }

        quality_standards = {
            "min_words": word_count,
            "uniqueness": 90,
            "readability_target": "Flesch 60-70",
            "error_tolerance": "Zero",
        }

        editing_task = self.editor_agent.create_editing_task(
            brand_guidelines=brand_guidelines,
            quality_standards=quality_standards,
        )
        editing_task.context = [writing_task, technical_task, marketing_task]
        editing_task.output_pydantic = EditingOutput

        # --- Single Crew, Process.sequential ---
        print("\n🚀 Running unified 6-agent SEO Crew (Process.sequential)")
        print("-" * 60)

        crew = Crew(
            agents=[
                self.research_agent.agent,
                self.strategy_agent.agent,
                self.copywriter_agent.agent,
                self.technical_agent.agent,
                self.marketing_agent.agent,
                self.editor_agent.agent,
            ],
            tasks=[
                research_task,
                strategy_task,
                writing_task,
                technical_task,
                marketing_task,
                editing_task,
            ],
            process=Process.sequential,
            verbose=True,
        )

        crew.kickoff()

        # Collect per-stage outputs — prefer structured Pydantic model, fall back to raw text
        def _raw(task) -> str:
            if not task.output:
                return ""
            if task.output.pydantic:
                return task.output.pydantic.model_dump_json(indent=2)
            return task.output.raw

        results["outputs"] = {
            "research": _raw(research_task),
            "strategy": _raw(strategy_task),
            "article": _raw(writing_task),
            "technical_seo": _raw(technical_task),
            "marketing_strategy": _raw(marketing_task),
            "final_article": _raw(editing_task),
        }

        # Expose structured models for callers that want typed access
        results["structured"] = {
            "research": research_task.output and research_task.output.pydantic,
            "strategy": strategy_task.output and strategy_task.output.pydantic,
            "writing": writing_task.output and writing_task.output.pydantic,
            "technical": technical_task.output and technical_task.output.pydantic,
            "marketing": marketing_task.output and marketing_task.output.pydantic,
            "editing": editing_task.output and editing_task.output.pydantic,
        }

        # Final article: prefer structured field, fall back to raw
        editing_model = results["structured"]["editing"]
        final_output = editing_model.final_article if editing_model else results["outputs"]["final_article"]
        print(f"\n✅ Pipeline complete — final article: {len(final_output)} characters\n")
        
        # Status tracking: mark as generated → pending_review
        if self.track_status and STATUS_AVAILABLE and status_record_id:
            try:
                status_svc = get_status_service()
                seo_actor = actor_from_agent("seo")
                status_svc.update_content(
                    status_record_id,
                    content_preview=final_output[:500] if final_output else None,
                    metadata={
                        "target_keyword": target_keyword,
                        "final_article_length": len(final_output),
                        "stages_completed": list(results["outputs"].keys()),
                    },
                )
                status_svc.transition(status_record_id, "generated", seo_actor)
                status_svc.transition(status_record_id, "pending_review", seo_actor)
                results["status_record_id"] = status_record_id
                print(f"📊 Status tracking: marked as pending_review")
            except Exception as e:
                print(f"⚠ Status tracking completion failed (non-critical): {e}")

        # Summary
        print("\n" + "="*60)
        print("CONTENT GENERATION COMPLETE")
        print("="*60)
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nOutputs generated:")
        print(f"  ✅ Research Analysis: {len(results['outputs']['research'])} chars")
        print(f"  ✅ Content Strategy: {len(results['outputs']['strategy'])} chars")
        print(f"  ✅ Article Draft: {len(results['outputs']['article'])} chars")
        print(f"  ✅ Technical SEO: {len(results['outputs']['technical_seo'])} chars")
        print(f"  ✅ Marketing Strategy: {len(results['outputs']['marketing_strategy'])} chars")
        print(f"  ✅ Final Article: {len(results['outputs']['final_article'])} chars")
        print("="*60 + "\n")

        return results
    
    def save_results(self, results: Dict[str, Any], output_dir: str = "output"):
        """
        Save all results to files.
        
        Args:
            results: Results dictionary from generate_content
            output_dir: Output directory path
        """
        import os
        from pathlib import Path
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        keyword_slug = results["input"]["target_keyword"].lower().replace(" ", "-")
        
        # Save each output
        for stage, content in results["outputs"].items():
            filename = f"{timestamp}_{keyword_slug}_{stage}.md"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {stage.upper()}\n\n")
                f.write(f"**Keyword:** {results['input']['target_keyword']}\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("-" * 60 + "\n\n")
                f.write(content)
            
            print(f"  📄 Saved: {filename}")
        
        print(f"\n✅ All results saved to {output_dir}/")


# Convenience function for quick usage
def generate_seo_article(
    keyword: str,
    competitors: Optional[List[str]] = None,
    word_count: int = 2500
) -> Dict[str, Any]:
    """
    Quick function to generate SEO article with all agents.
    
    Args:
        keyword: Target keyword
        competitors: Competitor domains
        word_count: Target word count
        
    Returns:
        Complete results from all agents
    """
    crew = SEOContentCrew()
    return crew.generate_content(
        target_keyword=keyword,
        competitor_domains=competitors,
        word_count=word_count
    )


if __name__ == "__main__":
    # Example: Generate complete SEO article
    print("=== SEO Content Crew - Full Pipeline Test ===\n")
    
    results = generate_seo_article(
        keyword="content marketing strategy",
        competitors=["hubspot.com", "contentmarketinginstitute.com"],
        word_count=2500
    )
    
    # Save results
    crew = SEOContentCrew()
    crew.save_results(results, output_dir="output/seo_content")
    
    print("\n=== PIPELINE TEST COMPLETE ===")

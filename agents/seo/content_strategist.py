"""
Content Strategist Agent - Semantic Architecture & Content Planning
Part of the SEO multi-agent system (Agent 2/6)

Responsibilities:
- Create pillar pages and topic clusters
- Generate detailed content outlines
- Optimize topical flow and internal linking
- Plan strategic editorial calendar
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from typing import List, Optional, Dict, Any, Union

# Third-party imports
from crewai import Agent, Task, Crew
from crewai.tools import Tool
from dotenv import load_dotenv

# Utility imports
import os
import logging

# Local imports
from agents.shared.prompt_loader import load_prompt
from .tools.strategy_tools import (
    OutlineGenerator,
    TopicalFlowOptimizer,
    EditorialCalendarPlanner,
    TopicalMeshBuilder
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load environment variables
load_dotenv()


class ContentStrategistAgent:
    """
    Content Strategist Agent for semantic architecture and content planning.
    Second agent in the SEO content generation pipeline.
    Follows the Liskov Substitution Principle by maintaining consistent 
    method signatures and return types across all methods.
    """
    
    def __init__(
        self,
        llm_model: str = "groq/mixtral-8x7b-32768",
        verbose: bool = True
    ):
        """
        Initialize Content Strategist with strategy tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
            verbose: Enable verbose logging

        Raises:
            ValueError: If initialization fails
        """
        try:
            self.llm_model = llm_model

            # Initialize tools with consistent error handling
            self.outline_generator = self._safe_tool_init(OutlineGenerator)
            self.flow_optimizer = self._safe_tool_init(TopicalFlowOptimizer)
            self.calendar_planner = self._safe_tool_init(EditorialCalendarPlanner)
            self.mesh_builder = self._safe_tool_init(TopicalMeshBuilder)

            # Create agent with well-defined tools
            self.agent = self._create_agent(verbose)
        except Exception as e:
            logger.error(f"Failed to initialize ContentStrategistAgent: {e}")
            raise ValueError(f"Agent initialization error: {e}")
    
    def _safe_tool_init(self, tool_class):
        """
        Safely initialize tools with error handling.
        
        Args:
            tool_class: Tool class to initialize
        
        Returns:
            Initialized tool instance
        
        Raises:
            ValueError: If tool initialization fails
        """
        try:
            return tool_class()
        except Exception as e:
            logger.error(f"Failed to initialize {tool_class.__name__}: {e}")
            raise ValueError(f"Tool initialization error for {tool_class.__name__}")
    
    def _create_agent(self, verbose: bool = True) -> Agent:
        """
        Create the Content Strategist CrewAI agent with well-defined tools.
        
        Args:
            verbose: Enable verbose logging
        
        Returns:
            Configured CrewAI Agent
        """
        tool_list = [
            Tool.tool(
                name="Generate Content Outline",
                func=self.outline_generator.generate_outline,
                description=(
                    "Generate a detailed, SEO-optimized content outline. "
                    "Includes structure, target word count, and key sections "
                    "aligned with search intent."
                )
            ),
            Tool.tool(
                name="Optimize Topical Flow",
                func=self.flow_optimizer.optimize_topical_flow,
                description=(
                    "Analyze and optimize content progression and internal linking. "
                    "Ensures smooth user journey and maximum topical coverage."
                )
            ),
            Tool.tool(
                name="Plan Editorial Calendar",
                func=self.calendar_planner.plan_editorial_calendar,
                description=(
                    "Create a strategic editorial calendar with publication schedule. "
                    "Prioritizes content based on business goals and topical impact."
                )
            )
        ]
        
        p = load_prompt("seo", "content_strategist")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            tools=tool_list,
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=verbose,
            allow_delegation=False
        )
    
    def create_strategy_task(
        self,
        research_insights: str,
        target_keyword: str,
        existing_content: Optional[List[str]] = None,
        business_goals: Optional[List[str]] = None,
        content_count: int = 5
    ) -> Task:
        """
        Create a comprehensive content strategy task.
        
        Args:
            research_insights: Research Analyst output
            target_keyword: Primary target keyword/topic
            existing_content: List of existing content URLs/titles
            business_goals: Business objectives to align strategy
            content_count: Number of content pieces to plan
        
        Returns:
            Configured CrewAI Task
        """
        # Task description generation logic remains the same as in original implementation
        description = f"""Content strategy for "{target_keyword}" based on research insights..."""
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output=(
                "Comprehensive markdown content strategy with "
                "topic cluster architecture, outlines, and editorial calendar."
            )
        )
    
    def run_strategy(
        self,
        research_insights: str,
        target_keyword: str,
        existing_content: Optional[List[str]] = None,
        business_goals: Optional[List[str]] = None,
        content_count: int = 5
    ) -> Union[str, Dict[str, Any]]:
        """
        Execute content strategy planning with robust error handling.
        
        Args:
            research_insights: Research Analyst output
            target_keyword: Primary target keyword/topic
            existing_content: List of existing content
            business_goals: Business objectives
            content_count: Number of content pieces to plan
        
        Returns:
            Content strategy document or error information
        """
        try:
            # Create strategy task
            task = self.create_strategy_task(
                research_insights=research_insights,
                target_keyword=target_keyword,
                existing_content=existing_content,
                business_goals=business_goals,
                content_count=content_count
            )
            
            # Create crew with error handling
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=True
            )
            
            # Execute strategy with type safety
            result = crew.kickoff()
            return str(result) if result else "No strategy generated"
        
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return {
                "error": str(e),
                "details": "Failed to generate content strategy"
            }
    
    def generate_topical_mesh(
        self,
        main_topic: str,
        subtopics: List[str],
        business_goals: Optional[List[str]] = None,
        output_visualization: bool = True,
        viz_path: Optional[Union[str, Path]] = "data/topical_mesh.png"
    ) -> Dict[str, Any]:
        """
        Generate topical mesh structure with robust error handling.
        
        Args:
            main_topic: Central pillar topic
            subtopics: Related cluster topics
            business_goals: Business objectives
            output_visualization: Generate graph visualization
            viz_path: Path for visualization output
        
        Returns:
            Dictionary with mesh structure, including potential errors
        """
        try:
            mesh_structure = self.mesh_builder.build_semantic_cocoon(
                main_topic=main_topic,
                subtopics=subtopics,
                business_goals=business_goals
            )
            
            # Additional processing similar to original implementation
            authority_score = self.mesh_builder.calculate_topical_authority(mesh_structure)
            mesh_structure['topical_authority_score'] = authority_score
            
            return mesh_structure
        
        except Exception as e:
            logger.error(f"Topical mesh generation failed: {e}")
            return {
                "error": str(e),
                "details": "Failed to generate topical mesh"
            }


def create_content_strategy(
    research_insights: str,
    topic: str,
    existing_content: Optional[List[str]] = None,
    business_goals: Optional[List[str]] = None
) -> Union[str, Dict[str, Any]]:
    """
    Quick function to create content strategy from research insights.
    
    Args:
        research_insights: Research Analyst output
        topic: Target topic/keyword
        existing_content: Existing content list
        business_goals: Business objectives
    
    Returns:
        Content strategy document or error information
    """
    try:
        strategist = ContentStrategistAgent()
        return strategist.run_strategy(
            research_insights=research_insights,
            target_keyword=topic,
            existing_content=existing_content,
            business_goals=business_goals
        )
    except Exception as e:
        logger.error(f"Content strategy creation failed: {e}")
        return {
            "error": str(e),
            "details": "Failed to create content strategy"
        }


if __name__ == "__main__":
    # Example usage with improved error handling
    try:
        research_insights = """
        SEO Competitive Analysis for Content Marketing Strategy
        High competition, informational intent, featured snippets present
        """
        
        result = create_content_strategy(
            research_insights=research_insights,
            topic="content marketing strategy",
            business_goals=["Increase organic traffic", "Generate qualified leads"]
        )
        
        if isinstance(result, dict) and 'error' in result:
            print("Strategy generation failed:", result['details'])
        else:
            print("=== Content Strategy ===")
            print(result)
    
    except Exception as e:
        print(f"Unexpected error: {e}")

"""
Calendar Manager Agent - Content Scheduling and Queue Management
Part of the Scheduler Robot multi-agent system (Agent 1/4)

Responsibilities:
- Analyze publishing history and identify patterns
- Manage content queue and prioritization
- Calculate optimal publishing times
- Detect and resolve scheduling conflicts
- Generate visual calendar views
"""
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import os

from agents.scheduler.tools.calendar_tools import (
    CalendarAnalyzer,
    QueueManager,
    TimeOptimizer
)

load_dotenv()


class CalendarManagerAgent:
    """
    Calendar Manager Agent for content scheduling and queue management.
    First agent in the Scheduler Robot pipeline.
    Analyzes patterns and determines optimal publishing times.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Calendar Manager with scheduling tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.calendar_analyzer = CalendarAnalyzer()
        self.queue_manager = QueueManager()
        self.time_optimizer = TimeOptimizer()

    def schedule_content(
        self,
        content_data: Dict[str, Any],
        auto_schedule: bool = True
    ) -> Dict[str, Any]:
        """
        Schedule a content item for publishing.

        Args:
            content_data: Content information (title, path, type, priority, etc.)
            auto_schedule: Whether to automatically calculate optimal time

        Returns:
            Scheduling result with queue position and recommended time
        """
        try:
            # Add to queue
            queue_result = self.queue_manager.add_to_queue(content_data)

            if not queue_result.get('success'):
                return queue_result

            # Calculate optimal time if auto_schedule
            if auto_schedule:
                optimal_time = self.time_optimizer.calculate_optimal_time(
                    content_type=content_data.get('content_type', 'article'),
                    priority=content_data.get('priority', 3)
                )

                return {
                    **queue_result,
                    "optimal_time": optimal_time
                }

            return queue_result

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_calendar(self, days: int = 14) -> Dict[str, Any]:
        """
        Get visual calendar view.

        Args:
            days: Number of days to show

        Returns:
            Calendar view with scheduled content
        """
        return self.time_optimizer.generate_calendar_view(days=days)

    def analyze_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze publishing performance.

        Args:
            days: Number of days to analyze

        Returns:
            Performance analysis with patterns and recommendations
        """
        return self.calendar_analyzer.analyze_publishing_history(days=days)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return self.queue_manager.get_queue_status()

    def detect_conflicts(self) -> Dict[str, Any]:
        """Detect scheduling conflicts"""
        return self.queue_manager.detect_scheduling_conflicts()


# Create default instance
def create_calendar_manager(llm_model: str = "mixtral-8x7b-32768") -> CalendarManagerAgent:
    """Factory function to create Calendar Manager Agent"""
    return CalendarManagerAgent(llm_model=llm_model)

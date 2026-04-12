"""
Calendar Management Tools
Tools for analyzing publishing history, managing content queue, and optimizing publish times
"""
from crewai.tools import tool
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import statistics
from collections import defaultdict, Counter

from agents.scheduler.schemas.publishing_schemas import (
    ContentItem,
    PublishingSchedule,
    SchedulingConflict,
    OptimalTime,
    CalendarEvent,
    CalendarView,
    PublishingStatus
)


class CalendarAnalyzer:
    """Analyzes publishing history and patterns"""

    def __init__(self, data_dir: str = "/root/contentflow_lab/data/scheduler"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "publishing_history.json"

    @tool("Analyze Publishing History")
    def analyze_publishing_history(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze historical publishing patterns to identify trends and optimal times.

        Args:
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with publishing patterns, peak times, and performance metrics
        """
        try:
            if not self.history_file.exists():
                return {
                    "status": "no_data",
                    "message": "No publishing history available yet",
                    "patterns": {}
                }

            with open(self.history_file, 'r') as f:
                history = json.load(f)

            cutoff_date = datetime.now() - timedelta(days=days)
            recent_publishes = [
                p for p in history
                if datetime.fromisoformat(p['published_at']) > cutoff_date
            ]

            if not recent_publishes:
                return {
                    "status": "insufficient_data",
                    "message": f"No publishes in the last {days} days",
                    "patterns": {}
                }

            # Analyze patterns
            patterns = self._extract_patterns(recent_publishes)

            return {
                "status": "success",
                "total_publishes": len(recent_publishes),
                "date_range": {
                    "start": cutoff_date.isoformat(),
                    "end": datetime.now().isoformat()
                },
                "patterns": patterns,
                "recommendations": self._generate_recommendations(patterns)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def _extract_patterns(self, publishes: List[Dict]) -> Dict[str, Any]:
        """Extract publishing patterns from history"""
        by_day_of_week = defaultdict(list)
        by_hour = defaultdict(list)
        by_type = defaultdict(int)
        engagement_scores = []

        for publish in publishes:
            dt = datetime.fromisoformat(publish['published_at'])
            day_name = dt.strftime('%A')
            hour = dt.hour

            by_day_of_week[day_name].append(publish)
            by_hour[hour].append(publish)
            by_type[publish.get('content_type', 'unknown')] += 1

            if 'engagement_score' in publish:
                engagement_scores.append({
                    'day': day_name,
                    'hour': hour,
                    'score': publish['engagement_score']
                })

        # Find peak days and hours
        peak_days = sorted(
            by_day_of_week.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:3]

        peak_hours = sorted(
            by_hour.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:3]

        # Calculate average engagement by time
        engagement_by_hour = defaultdict(list)
        for score in engagement_scores:
            engagement_by_hour[score['hour']].append(score['score'])

        best_hours = sorted(
            [(h, statistics.mean(scores)) for h, scores in engagement_by_hour.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "peak_days": [{"day": day, "count": len(pubs)} for day, pubs in peak_days],
            "peak_hours": [{"hour": hour, "count": len(pubs)} for hour, pubs in peak_hours],
            "best_engagement_hours": [
                {"hour": hour, "avg_engagement": score} for hour, score in best_hours
            ],
            "content_type_distribution": dict(by_type),
            "publish_frequency": len(publishes) / 30,  # per day
        }

    def _generate_recommendations(self, patterns: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on patterns"""
        recommendations = []

        if patterns.get("peak_days"):
            top_day = patterns["peak_days"][0]["day"]
            recommendations.append(
                f"Most content is published on {top_day}. Consider diversifying to other days."
            )

        if patterns.get("best_engagement_hours"):
            best_hour = patterns["best_engagement_hours"][0]["hour"]
            recommendations.append(
                f"Content published at {best_hour}:00 shows highest engagement. "
                f"Prioritize this time slot."
            )

        freq = patterns.get("publish_frequency", 0)
        if freq < 1:
            recommendations.append(
                f"Publishing frequency is {freq:.1f} posts/day. "
                f"Consider increasing to maintain audience engagement."
            )

        return recommendations

    @tool("Get Publishing Statistics")
    def get_publishing_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive publishing statistics for a time period.

        Args:
            days: Number of days to analyze

        Returns:
            Statistics including success rate, timing, indexing speed
        """
        try:
            if not self.history_file.exists():
                return {"status": "no_data", "message": "No history available"}

            with open(self.history_file, 'r') as f:
                history = json.load(f)

            cutoff = datetime.now() - timedelta(days=days)
            recent = [
                p for p in history
                if datetime.fromisoformat(p['published_at']) > cutoff
            ]

            if not recent:
                return {"status": "no_data", "message": f"No publishes in last {days} days"}

            total = len(recent)
            successful = sum(1 for p in recent if p.get('success', False))
            failed = total - successful

            # Calculate timing metrics
            times_to_publish = [
                p.get('time_to_publish_hours', 0) for p in recent
                if 'time_to_publish_hours' in p
            ]

            times_to_index = [
                p.get('time_to_index_hours', 0) for p in recent
                if 'time_to_index_hours' in p
            ]

            return {
                "status": "success",
                "period_days": days,
                "total_publishes": total,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "average_time_to_publish_hours": (
                    statistics.mean(times_to_publish) if times_to_publish else None
                ),
                "average_time_to_index_hours": (
                    statistics.mean(times_to_index) if times_to_index else None
                ),
                "by_content_type": Counter(p.get('content_type') for p in recent)
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


class QueueManager:
    """Manages content publishing queue"""

    def __init__(self, data_dir: str = "/root/contentflow_lab/data/scheduler"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.data_dir / "content_queue.json"
        self._load_queue()

    def _load_queue(self):
        """Load queue from disk"""
        if self.queue_file.exists():
            with open(self.queue_file, 'r') as f:
                self.queue = json.load(f)
        else:
            self.queue = []

    def _save_queue(self):
        """Save queue to disk"""
        with open(self.queue_file, 'w') as f:
            json.dump(self.queue, f, indent=2, default=str)

    @tool("Add Content to Queue")
    def add_to_queue(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new content item to the publishing queue.

        Args:
            content_data: Dictionary with content information (title, path, type, etc.)

        Returns:
            Result with queue position and estimated publish time
        """
        try:
            # Create ContentItem
            item = ContentItem(
                id=content_data.get('id', f"content_{datetime.now().timestamp()}"),
                title=content_data['title'],
                content_path=content_data['content_path'],
                content_type=content_data['content_type'],
                priority=content_data.get('priority', 3),
                source_robot=content_data['source_robot'],
                metadata=content_data.get('metadata', {})
            )

            # Add to queue
            self.queue.append(item.dict())
            self._save_queue()

            # Sort by priority (high to low)
            self.queue.sort(key=lambda x: x['priority'], reverse=True)
            position = next(
                i for i, q in enumerate(self.queue) if q['id'] == item.id
            )

            return {
                "status": "success",
                "content_id": item.id,
                "queue_position": position + 1,
                "total_in_queue": len(self.queue),
                "message": f"Added {item.title} to queue at position {position + 1}"
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    @tool("Get Queue Status")
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and contents.

        Returns:
            Queue contents, statistics, and next items to publish
        """
        try:
            self._load_queue()

            if not self.queue:
                return {
                    "status": "empty",
                    "message": "Queue is empty",
                    "total_items": 0
                }

            # Count by status
            by_status = Counter(item.get('status', 'queued') for item in self.queue)
            by_type = Counter(item.get('content_type') for item in self.queue)

            # Get next items to publish
            next_items = [
                {
                    "id": item['id'],
                    "title": item['title'],
                    "type": item['content_type'],
                    "priority": item['priority'],
                    "scheduled_for": item.get('scheduled_for')
                }
                for item in self.queue[:5]  # Top 5
            ]

            return {
                "status": "success",
                "total_items": len(self.queue),
                "by_status": dict(by_status),
                "by_type": dict(by_type),
                "next_items": next_items,
                "oldest_item_age_hours": self._get_oldest_item_age()
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_oldest_item_age(self) -> Optional[float]:
        """Get age of oldest queued item in hours"""
        if not self.queue:
            return None

        oldest = min(
            (datetime.fromisoformat(item['created_at']) for item in self.queue),
            default=None
        )

        if oldest:
            age = datetime.now() - oldest
            return age.total_seconds() / 3600

        return None

    @tool("Detect Scheduling Conflicts")
    def detect_scheduling_conflicts(self) -> Dict[str, Any]:
        """
        Detect scheduling conflicts in the queue.

        Returns:
            List of conflicts with severity and suggested resolutions
        """
        try:
            self._load_queue()

            if not self.queue:
                return {"status": "no_conflicts", "conflicts": []}

            conflicts = []

            # Group by scheduled time
            scheduled_items = [
                item for item in self.queue
                if item.get('scheduled_for') is not None
            ]

            time_groups = defaultdict(list)
            for item in scheduled_items:
                sched_time = datetime.fromisoformat(item['scheduled_for'])
                # Round to nearest hour for grouping
                rounded = sched_time.replace(minute=0, second=0, microsecond=0)
                time_groups[rounded].append(item)

            # Detect conflicts (multiple items at same time)
            for time_slot, items in time_groups.items():
                if len(items) > 1:
                    conflicts.append({
                        "conflict_id": f"conflict_{time_slot.timestamp()}",
                        "time_slot": time_slot.isoformat(),
                        "items": [
                            {"id": item['id'], "title": item['title']}
                            for item in items
                        ],
                        "count": len(items),
                        "severity": "high" if len(items) > 2 else "medium",
                        "resolution": f"Stagger publishes across {len(items)} hours"
                    })

            return {
                "status": "success",
                "conflict_count": len(conflicts),
                "conflicts": conflicts
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


class TimeOptimizer:
    """Optimizes publishing times based on historical data and rules"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/root/contentflow_lab/agents/scheduler/config/calendar_rules.yaml"
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Load scheduling rules from config"""
        # Default rules if config doesn't exist
        return {
            "peak_hours": [9, 14, 18],
            "peak_days": ["Monday", "Tuesday", "Wednesday", "Thursday"],
            "minimum_spacing_hours": 4,
            "blackout_dates": [],
            "timezone": "America/New_York"
        }

    @tool("Calculate Optimal Publishing Time")
    def calculate_optimal_time(
        self,
        content_type: str,
        priority: int = 3,
        historical_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calculate optimal publishing time for a content item.

        Args:
            content_type: Type of content (article, newsletter, etc.)
            priority: Priority level (1-5)
            historical_data: Optional historical performance data

        Returns:
            Recommended time with confidence score and reasoning
        """
        try:
            now = datetime.now()
            peak_hours = self.rules.get("peak_hours", [9, 14, 18])

            # Find next available peak hour
            next_slots = []
            for day_offset in range(7):  # Look ahead 7 days
                check_date = now + timedelta(days=day_offset)
                day_name = check_date.strftime('%A')

                # Skip if not a peak day
                if day_name not in self.rules.get("peak_days", []):
                    continue

                for hour in peak_hours:
                    slot = check_date.replace(
                        hour=hour,
                        minute=0,
                        second=0,
                        microsecond=0
                    )

                    # Must be in future
                    if slot > now:
                        next_slots.append(slot)

            if not next_slots:
                # Fallback to next business day at 9 AM
                next_slot = now + timedelta(days=1)
                next_slot = next_slot.replace(hour=9, minute=0, second=0, microsecond=0)
            else:
                # For high priority, use earliest slot
                if priority >= 4:
                    next_slot = min(next_slots)
                else:
                    # For normal priority, use second or third slot
                    next_slot = next_slots[min(1, len(next_slots) - 1)]

            # Generate alternatives
            alternatives = [
                slot for slot in next_slots
                if slot != next_slot
            ][:3]

            confidence = 0.85 if historical_data else 0.70

            return {
                "status": "success",
                "recommended_time": next_slot.isoformat(),
                "confidence": confidence,
                "reasoning": (
                    f"Selected {next_slot.strftime('%A at %I:%M %p')} based on "
                    f"peak engagement hours ({peak_hours}) and content priority ({priority})"
                ),
                "alternative_times": [alt.isoformat() for alt in alternatives]
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    @tool("Generate Calendar View")
    def generate_calendar_view(
        self,
        start_date: Optional[str] = None,
        days: int = 14
    ) -> Dict[str, Any]:
        """
        Generate a visual calendar view of upcoming publishes.

        Args:
            start_date: Start date (ISO format, default: today)
            days: Number of days to show (default: 14)

        Returns:
            Calendar structure with events by date
        """
        try:
            start = datetime.fromisoformat(start_date) if start_date else datetime.now()
            end = start + timedelta(days=days)

            # Load queue
            queue_file = Path("/root/contentflow_lab/data/scheduler/content_queue.json")
            if queue_file.exists():
                with open(queue_file, 'r') as f:
                    queue = json.load(f)
            else:
                queue = []

            # Build calendar
            calendar = defaultdict(list)
            for item in queue:
                if item.get('scheduled_for'):
                    sched_dt = datetime.fromisoformat(item['scheduled_for'])
                    if start <= sched_dt <= end:
                        date_key = sched_dt.strftime('%Y-%m-%d')
                        calendar[date_key].append({
                            "time": sched_dt.strftime('%H:%M'),
                            "title": item['title'],
                            "type": item['content_type'],
                            "priority": item['priority']
                        })

            # Generate statistics
            total_events = sum(len(events) for events in calendar.values())
            busiest_day = max(
                calendar.items(),
                key=lambda x: len(x[1]),
                default=(None, [])
            )

            return {
                "status": "success",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "total_events": total_events,
                "busiest_day": {
                    "date": busiest_day[0],
                    "event_count": len(busiest_day[1])
                } if busiest_day[0] else None,
                "calendar": dict(calendar)
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

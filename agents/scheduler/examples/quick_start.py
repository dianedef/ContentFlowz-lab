"""
Scheduling Robot - Quick Start Examples
Demonstrates basic usage of the Scheduling Robot
"""
from agents.scheduler.scheduler_crew import create_scheduler_crew
import json


def main():
    print("🤖 Scheduling Robot - Quick Start\n")

    # Create scheduler crew
    print("Initializing Scheduling Robot...")
    crew = create_scheduler_crew(
        llm_model="mixtral-8x7b-32768",
        base_url="http://localhost:3000",
        project_path="/root/contentflowz-lab"
    )
    print("✅ Scheduler initialized\n")

    # Example 1: Quick Health Check
    print("=" * 60)
    print("Example 1: Quick Health Check")
    print("=" * 60)

    health = crew.quick_health_check()
    print(f"Overall Status: {health.get('overall_status', 'unknown')}")
    print(f"SEO Health: {health.get('seo_health', {}).get('overall_health', 'unknown')}")
    print(f"Security Status: {health.get('security_health', {}).get('status', 'unknown')}")
    print(f"Queue Items: {health.get('queue_status', {}).get('total_items', 0)}")
    print()

    # Example 2: Schedule Content
    print("=" * 60)
    print("Example 2: Schedule Content")
    print("=" * 60)

    content_data = {
        "id": "example_content_001",
        "title": "Getting Started with AI Agents",
        "content_path": "src/content/blog/ai-agents-intro.md",
        "content_type": "article",
        "priority": 4,
        "source_robot": "manual",
        "metadata": {
            "author": "AI Team",
            "tags": ["ai", "agents", "crewai"]
        }
    }

    schedule_result = crew.calendar_manager.schedule_content(
        content_data=content_data,
        auto_schedule=True
    )

    print(f"Scheduling Status: {schedule_result.get('status', 'unknown')}")
    if schedule_result.get('success'):
        print(f"Queue Position: {schedule_result.get('queue_position')}")
        print(f"Total in Queue: {schedule_result.get('total_in_queue')}")
        if 'optimal_time' in schedule_result:
            optimal = schedule_result['optimal_time']
            print(f"Recommended Time: {optimal.get('recommended_time', 'N/A')}")
            print(f"Confidence: {optimal.get('confidence', 0):.0%}")
    print()

    # Example 3: Get Calendar View
    print("=" * 60)
    print("Example 3: Calendar View (Next 7 Days)")
    print("=" * 60)

    calendar = crew.calendar_manager.get_calendar(days=7)
    if calendar.get('success'):
        print(f"Total Events: {calendar.get('total_events', 0)}")
        for date, events in calendar.get('calendar', {}).items():
            print(f"\n{date}:")
            for event in events:
                print(f"  - {event['time']}: {event['title']} ({event['type']})")
    print()

    # Example 4: Security Check
    print("=" * 60)
    print("Example 4: Security Vulnerability Check")
    print("=" * 60)

    security = crew.tech_stack.quick_security_check()
    if security.get('success'):
        print(f"Security Status: {security.get('status', 'unknown')}")
        print(f"Total Vulnerabilities: {security.get('total_vulnerabilities', 0)}")
        print(f"Critical: {security.get('critical_vulnerabilities', 0)}")
        print(f"High: {security.get('high_vulnerabilities', 0)}")

        if security.get('critical_vulnerabilities', 0) > 0:
            print("\n⚠️  CRITICAL vulnerabilities found! Action required immediately.")
    print()

    # Example 5: Publishing History
    print("=" * 60)
    print("Example 5: Recent Deployment History")
    print("=" * 60)

    history = crew.publishing_agent.get_deployment_history(limit=5)
    if history.get('success'):
        print(f"Total Deployments: {history.get('total_deployments', 0)}")
        print(f"Success Rate: {history.get('success_rate', 0):.1f}%")
        print(f"\nRecent Deployments:")
        for deployment in history.get('recent_deployments', [])[:3]:
            print(f"  - {deployment.get('deployment_id')}: "
                  f"{'✅ Success' if deployment.get('success') else '❌ Failed'}")
    print()

    print("=" * 60)
    print("🎉 Quick start examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the full documentation: agents/scheduler/README.md")
    print("2. Configure environment variables for Google APIs and GitHub")
    print("3. Customize calendar rules in agents/scheduler/config/calendar_rules.yaml")
    print("4. Run a weekly analysis: crew.weekly_analysis_workflow()")


if __name__ == "__main__":
    main()

"""
Publishing Agent - Content Deployment and Google Integration
Part of the Scheduler Robot multi-agent system (Agent 2/4)

Responsibilities:
- Deploy content to production via Git
- Submit URLs to Google Search Console
- Trigger Google Indexing API
- Monitor deployment health
- Handle rollbacks on failure
- Track publishing analytics
"""
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import os

from agents.scheduler.tools.publishing_tools import (
    GitDeployer,
    GoogleIntegration,
    DeploymentMonitor
)
from agents.scheduler.schemas.publishing_schemas import DeploymentResult

load_dotenv()


class PublishingAgent:
    """
    Publishing Agent for content deployment and platform integration.
    Second agent in the Scheduler Robot pipeline.
    Handles all deployment operations and Google integrations.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Publishing Agent with publishing tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
        """
        self.llm_model = llm_model

        # Initialize tools
        self.git_deployer = GitDeployer()
        self.google_integration = GoogleIntegration()
        self.deployment_monitor = DeploymentMonitor()

    def publish_content(
        self,
        content_path: str,
        title: str,
        urls: List[str],
        auto_index: bool = True
    ) -> Dict[str, Any]:
        """
        Publish content to production with full pipeline.

        Args:
            content_path: Path to content file
            title: Content title for commit message
            urls: URLs to submit for indexing
            auto_index: Whether to automatically trigger Google indexing

        Returns:
            Comprehensive deployment result
        """
        try:
            deployment_id = f"deploy_{int(__import__('time').time())}"

            # 1. Deploy to Git
            commit_msg = f"Publish: {title}"
            deploy_result = self.git_deployer.deploy_to_production(
                content_path=content_path,
                commit_message=commit_msg,
                auto_push=True
            )

            if not deploy_result.get('success'):
                return {
                    "success": False,
                    "deployment_id": deployment_id,
                    "stage": "git_deployment",
                    "error": deploy_result.get('error'),
                    "rollback_available": deploy_result.get('rollback_available', False)
                }

            # 2. Monitor deployment
            monitor_result = self.deployment_monitor.monitor_deployment(
                deployment_id=deployment_id,
                urls=urls
            )

            # 4. Submit to Google if auto_index
            indexing_result = None
            if auto_index:
                indexing_result = self.google_integration.trigger_google_indexing(
                    urls=urls,
                    action="URL_UPDATED"
                )

            # 5. Log deployment
            log_data = {
                "deployment_id": deployment_id,
                "content_path": content_path,
                "title": title,
                "urls": urls,
                **deploy_result,
                "monitoring": monitor_result,
                "indexing": indexing_result
            }
            self.deployment_monitor.log_deployment(log_data)

            return {
                "success": True,
                "deployment_id": deployment_id,
                "commit_sha": deploy_result.get('commit_sha'),
                "urls": urls,
                "deployment_time_seconds": deploy_result.get('deployment_time_seconds'),
                "monitoring": monitor_result,
                "indexing": indexing_result
            }

        except Exception as e:
            return {
                "success": False,
                "deployment_id": deployment_id,
                "error": str(e)
            }

    def rollback(self, commit_sha: str) -> Dict[str, Any]:
        """
        Rollback to a previous commit.

        Args:
            commit_sha: Commit SHA to rollback to

        Returns:
            Rollback result
        """
        return self.git_deployer.rollback_deployment(commit_sha)

    def check_deployment_health(self, deployment_id: str, urls: List[str]) -> Dict[str, Any]:
        """
        Check deployment health.

        Args:
            deployment_id: Deployment ID to check
            urls: URLs to monitor

        Returns:
            Health check results
        """
        return self.deployment_monitor.monitor_deployment(deployment_id, urls)

    def get_indexing_status(self, urls: List[str]) -> Dict[str, Any]:
        """
        Check Google indexing status.

        Args:
            urls: URLs to check

        Returns:
            Indexing status for each URL
        """
        return self.google_integration.check_indexing_status(urls)

    def get_deployment_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent deployment history"""
        return self.deployment_monitor.get_deployment_history(limit)


# Create default instance
def create_publishing_agent(llm_model: str = "mixtral-8x7b-32768") -> PublishingAgent:
    """Factory function to create Publishing Agent"""
    return PublishingAgent(llm_model=llm_model)

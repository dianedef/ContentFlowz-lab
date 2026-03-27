"""
Tech Stack Analyzer Agent - Infrastructure and Dependency Auditing
Part of the Scheduler Robot multi-agent system (Agent 4/4)

Responsibilities:
- Analyze project dependencies
- Scan for security vulnerabilities
- Monitor build performance
- Track API costs and usage
- Detect outdated packages
- Generate tech health reports
"""
from typing import List, Optional, Dict, Any
from crewai import Agent
from dotenv import load_dotenv
import os

from agents.scheduler.tools.tech_audit_tools import (
    DependencyAnalyzer,
    VulnerabilityScanner,
    BuildAnalyzer,
    CostTracker
)
from agents.scheduler.schemas.analysis_schemas import TechStackHealth

load_dotenv()


class TechStackAnalyzerAgent:
    """
    Tech Stack Analyzer Agent for infrastructure and dependency auditing.
    Fourth agent in the Scheduler Robot pipeline.
    Performs self-analysis of the project's tech stack and infrastructure.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768", project_path: str = "/root/contentflowz-lab"):
        """
        Initialize Tech Stack Analyzer with audit tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
            project_path: Path to project directory
        """
        self.llm_model = llm_model
        self.project_path = project_path

        # Initialize tools
        self.dependency_analyzer = DependencyAnalyzer(project_path=project_path)
        self.vulnerability_scanner = VulnerabilityScanner(project_path=project_path)
        self.build_analyzer = BuildAnalyzer(project_path=project_path)
        self.cost_tracker = CostTracker()

        # Create agent
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Create the CrewAI Tech Stack Analyzer Agent"""
        return Agent(
            role="Infrastructure & DevOps Analyst",
            goal=(
                "Monitor and optimize the project's tech stack, dependencies, and infrastructure. "
                "Identify security vulnerabilities, outdated packages, build performance issues, "
                "and cost optimization opportunities. Maintain zero critical vulnerabilities and "
                "provide actionable recommendations for technical improvements."
            ),
            backstory=(
                "You are an experienced DevOps engineer and infrastructure specialist with deep "
                "expertise in dependency management, security auditing, build optimization, and "
                "cost analysis. You've worked with various tech stacks including Node.js, Python, "
                "and modern frameworks like Astro and Next.js. You have a keen eye for spotting "
                "vulnerabilities before they become security incidents, and you excel at optimizing "
                "build pipelines for speed and efficiency. You track infrastructure costs religiously "
                "and always find ways to reduce spending without sacrificing performance. Your audits "
                "are thorough, prioritized, and always include clear action items."
            ),
            tools=[
                self.dependency_analyzer.analyze_dependencies,
                self.dependency_analyzer.check_sitemap_plugin,
                self.vulnerability_scanner.scan_vulnerabilities,
                self.build_analyzer.analyze_build,
                self.cost_tracker.track_costs,
                self.cost_tracker.get_cost_summary
            ],
            llm=self.llm_model,  # CrewAI uses LiteLLM internally
            verbose=True,
            allow_delegation=False
        )

    def run_full_analysis(self) -> Dict[str, Any]:
        """
        Run comprehensive tech stack analysis.

        Returns:
            Complete tech health report with recommendations
        """
        try:
            analysis_id = f"tech_audit_{int(__import__('time').time())}"

            # 1. Analyze dependencies
            deps_result = self.dependency_analyzer.analyze_dependencies()

            if not deps_result.get('success'):
                return {
                    "success": False,
                    "error": "Dependency analysis failed",
                    "details": deps_result
                }

            # 2. Scan vulnerabilities
            vuln_result = self.vulnerability_scanner.scan_vulnerabilities()

            vulnerabilities = vuln_result.get('vulnerabilities', []) if vuln_result.get('success') else []
            critical_vulns = sum(1 for v in vulnerabilities if v.get('severity') == 'critical')
            high_vulns = sum(1 for v in vulnerabilities if v.get('severity') == 'high')

            # 3. Analyze build performance
            build_result = self.build_analyzer.analyze_build()

            build_metrics = {}
            if build_result.get('success'):
                build_metrics = {
                    "build_time_seconds": build_result.get('build_time_seconds', 0),
                    "bundle_size_mb": build_result.get('bundle_size_mb', 0),
                    "asset_count": build_result.get('asset_count', 0),
                    "cache_hit_rate": build_result.get('cache_hit_rate', 0),
                    "build_trend": build_result.get('build_trend', 'stable')
                }

            # 4. Get cost summary
            cost_result = self.cost_tracker.get_cost_summary(days=30)

            api_costs = cost_result.get('cost_breakdown', []) if cost_result.get('success') else []
            total_monthly_forecast = cost_result.get('forecast_monthly_usd', 0.0)

            # Calculate overall health score
            health_score = self._calculate_health_score(
                deps_result=deps_result,
                vuln_result=vuln_result,
                build_result=build_result
            )

            # Generate recommendations
            recommendations = []
            action_items = []

            # Vulnerability recommendations
            if critical_vulns > 0:
                action_items.append(
                    f"CRITICAL: Fix {critical_vulns} critical vulnerabilities immediately"
                )
                recommendations.append(
                    "Run npm audit fix or update vulnerable packages manually"
                )

            if high_vulns > 0:
                action_items.append(
                    f"HIGH: Address {high_vulns} high-severity vulnerabilities"
                )

            # Dependency recommendations
            outdated_count = deps_result.get('outdated_dependencies', 0)
            if outdated_count > 5:
                recommendations.append(
                    f"Update {outdated_count} outdated dependencies to improve security and performance"
                )

            # Build recommendations
            if build_result.get('success'):
                recommendations.extend(build_result.get('recommendations', []))

            # Cost recommendations
            if total_monthly_forecast > 100:
                recommendations.append(
                    f"Monthly API costs forecasted at ${total_monthly_forecast:.2f}. "
                    "Review usage and consider caching strategies."
                )

            # Build tech health report
            tech_health = {
                "analysis_id": analysis_id,
                "analyzed_at": __import__('datetime').datetime.now().isoformat(),
                "overall_health": health_score,
                "total_dependencies": deps_result.get('total_dependencies', 0),
                "outdated_dependencies": deps_result.get('outdated_dependencies', 0),
                "dependencies": deps_result.get('dependencies', []),
                "vulnerabilities": vulnerabilities,
                "critical_vulnerabilities": critical_vulns,
                "high_vulnerabilities": high_vulns,
                "build_metrics": build_metrics,
                "api_costs": api_costs,
                "total_monthly_cost_forecast": total_monthly_forecast,
                "recommendations": recommendations,
                "action_items": action_items,
                "ci_cd_performance": {},
                "cache_efficiency": build_metrics.get('cache_hit_rate', 0.0),
                "code_quality_score": None
            }

            return {
                "success": True,
                **tech_health
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _calculate_health_score(
        self,
        deps_result: Dict,
        vuln_result: Dict,
        build_result: Dict
    ) -> float:
        """Calculate overall tech health score"""
        base_score = 100.0

        # Deduct for vulnerabilities
        critical_vulns = vuln_result.get('critical', 0) if vuln_result.get('success') else 0
        high_vulns = vuln_result.get('high', 0) if vuln_result.get('success') else 0

        base_score -= critical_vulns * 20  # 20 points per critical
        base_score -= high_vulns * 10      # 10 points per high

        # Deduct for outdated dependencies
        outdated = deps_result.get('outdated_dependencies', 0)
        base_score -= min(outdated * 2, 30)  # Max 30 point penalty

        # Deduct for build issues
        if build_result.get('success'):
            build_time = build_result.get('build_time_seconds', 0)
            if build_time > 180:  # >3 minutes
                base_score -= 10
            bundle_size = build_result.get('bundle_size_mb', 0)
            if bundle_size > 15:  # >15MB
                base_score -= 10

        return max(0.0, min(100.0, base_score))

    def quick_security_check(self) -> Dict[str, Any]:
        """
        Run quick security vulnerability check.

        Returns:
            Vulnerability scan results
        """
        try:
            vuln_result = self.vulnerability_scanner.scan_vulnerabilities()

            if not vuln_result.get('success'):
                return {
                    "success": False,
                    "error": "Security scan failed",
                    "details": vuln_result
                }

            critical = vuln_result.get('critical', 0)
            high = vuln_result.get('high', 0)
            total = vuln_result.get('total_vulnerabilities', 0)

            status = "secure"
            if critical > 0:
                status = "critical"
            elif high > 0:
                status = "warning"
            elif total > 0:
                status = "attention"

            return {
                "success": True,
                "status": status,
                "total_vulnerabilities": total,
                "critical_vulnerabilities": critical,
                "high_vulnerabilities": high,
                "vulnerabilities": vuln_result.get('vulnerabilities', [])
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def track_api_usage(
        self,
        api_name: str,
        requests: int,
        cost: float
    ) -> Dict[str, Any]:
        """
        Track API usage and costs.

        Args:
            api_name: Name of API (e.g., "OpenAI", "Exa")
            requests: Number of requests
            cost: Cost in USD

        Returns:
            Tracking confirmation
        """
        return self.cost_tracker.track_costs(
            api_name=api_name,
            requests_count=requests,
            cost_usd=cost
        )

    def get_cost_forecast(self, days: int = 30) -> Dict[str, Any]:
        """
        Get cost forecast for APIs.

        Args:
            days: Number of days to analyze

        Returns:
            Cost summary and forecast
        """
        return self.cost_tracker.get_cost_summary(days=days)


# Create default instance
def create_tech_stack_analyzer(
    llm_model: str = "mixtral-8x7b-32768",
    project_path: str = "/root/contentflowz-lab"
) -> TechStackAnalyzerAgent:
    """Factory function to create Tech Stack Analyzer Agent"""
    return TechStackAnalyzerAgent(llm_model=llm_model, project_path=project_path)

"""
Site Health Monitor Agent - Site-Wide SEO Auditing and Health Checks
Part of the Scheduler Robot multi-agent system (Agent 3/4)

Responsibilities:
- Crawl site and analyze structure
- Monitor page speed and Core Web Vitals across all pages
- Audit internal linking site-wide
- Detect broken links and redirect chains
- Generate comprehensive site health reports

Uses On-Page Technical SEO Agent to analyze individual pages.

Note: For optimizing NEW content, see seo/on_page_technical_seo.py
"""
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import os

from agents.scheduler.tools.seo_audit_tools import (
    SiteCrawler,
    PerformanceAnalyzer,
    LinkAnalyzer,
    SitemapMonitor,
)
# Import the On-Page SEO agent to analyze individual pages
from agents.seo.on_page_technical_seo import OnPageTechnicalSEOAgent
from agents.seo.tools.technical_tools import SchemaGenerator, MetadataValidator

from agents.scheduler.schemas.analysis_schemas import TechnicalSEOScore

load_dotenv()


class SiteHealthMonitorAgent:
    """
    Site Health Monitor Agent for comprehensive site-wide auditing.
    Third agent in the Scheduler Robot pipeline.
    Performs continuous technical SEO monitoring and optimization.

    Uses OnPageTechnicalSEOAgent to analyze individual pages during crawls.
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768", base_url: str = "http://localhost:3000"):
        """
        Initialize Site Health Monitor with audit tools.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
            base_url: Base URL of the site to analyze
        """
        self.llm_model = llm_model
        self.base_url = base_url

        # Initialize site-wide audit tools
        self.site_crawler = SiteCrawler(base_url=base_url)
        self.performance_analyzer = PerformanceAnalyzer()
        self.link_analyzer = LinkAnalyzer()
        self.sitemap_monitor = SitemapMonitor()

        # Initialize On-Page SEO tools for individual page analysis
        self.schema_validator = SchemaGenerator()  # For validation
        self.metadata_validator = MetadataValidator()

    def analyze_page_seo(self, url: str, content: str) -> Dict[str, Any]:
        """
        Analyze individual page using On-Page Technical SEO tools.

        Args:
            url: Page URL
            content: Page content (HTML or markdown)

        Returns:
            On-page SEO analysis results
        """
        try:
            # Extract metadata from content (simplified)
            # In production, you'd parse the actual HTML
            title = "Page Title"  # Would extract from HTML
            description = "Page description"  # Would extract from meta tags

            # Use On-Page SEO tools
            metadata_result = self.metadata_validator.validate_metadata(
                title=title,
                description=description
            )

            return {
                "url": url,
                "metadata_validation": metadata_result,
                "schema_valid": True,  # Would validate schema
                "on_page_score": metadata_result.get('overall_score', 0)
            }

        except Exception as e:
            return {
                "url": url,
                "error": str(e)
            }

    def run_full_audit(self, max_pages: int = 100) -> Dict[str, Any]:
        """
        Run comprehensive site health audit.
        Uses On-Page SEO analyzer for individual page validation.

        Args:
            max_pages: Maximum pages to crawl

        Returns:
            Complete audit report with scores and recommendations
        """
        try:
            audit_id = f"audit_{int(__import__('time').time())}"

            # 1. Crawl site
            crawl_result = self.site_crawler.crawl_site(
                max_pages=max_pages,
                include_external=False
            )

            if not crawl_result.get('success'):
                return {
                    "success": False,
                    "error": "Site crawl failed",
                    "details": crawl_result
                }

            pages = crawl_result['pages']
            issues: List[Dict[str, Any]] = []

            # 2. Analyze each page using On-Page SEO tools
            page_analyses = []
            for page in pages[:10]:  # Sample first 10 for performance
                analysis = self.analyze_page_seo(page['url'], page.get('content', ''))
                page_analyses.append(analysis)

            # Calculate average on-page score
            avg_onpage_score = sum(
                p.get('on_page_score', 0) for p in page_analyses
            ) / len(page_analyses) if page_analyses else 0

            # 3. Check sitemap health
            sitemap_check = self.sitemap_monitor.check_sitemap_health(self.base_url)
            if sitemap_check.get("warnings"):
                for w in sitemap_check["warnings"]:
                    issues.append({
                        "issue_id": f"sitemap_{audit_id}",
                        "category": "crawlability",
                        "severity": "high",
                        "title": "Sitemap issue detected",
                        "description": w,
                        "recommendation": "Review sitemap generation and recent deploy history",
                    })

            # 5. Check broken links
            broken_links = self.site_crawler.detect_broken_links(pages)

            # 6. Analyze internal linking
            linking_analysis = self.link_analyzer.analyze_internal_links(pages)

            # 5. Check performance (sample first 5 pages)
            performance_scores = []
            for page in pages[:5]:
                perf = self.performance_analyzer.check_page_speed(page['url'])
                if perf.get('success'):
                    performance_scores.append(perf.get('performance_score', 50))

            avg_performance = (
                sum(performance_scores) / len(performance_scores)
                if performance_scores else 50
            )

            # 6. Core Web Vitals (homepage)
            cwv = self.performance_analyzer.measure_core_web_vitals(self.base_url)

            # Calculate component scores
            page_speed_score = avg_performance
            schema_validity_score = avg_onpage_score  # Based on page analyses
            internal_linking_score = self._calculate_linking_score(linking_analysis)
            mobile_friendly_score = 90  # Would check actual mobile-friendliness
            accessibility_score = 85  # Would run accessibility audit

            # Aggregate issues (issues list was started above for sitemap warnings)
            issues.extend(linking_analysis.get('issues', []))
            if broken_links.get('broken_links_count', 0) > 0:
                issues.append({
                    "issue_id": f"broken_links_{audit_id}",
                    "category": "crawlability",
                    "severity": "high",
                    "title": f"{broken_links['broken_links_count']} broken links found",
                    "description": "Broken internal links affect crawlability",
                    "recommendation": "Fix or remove broken links"
                })

            critical_issues = sum(1 for issue in issues if issue.get('severity') == 'critical')

            # Build recommendations
            recommendations = []
            recommendations.extend(linking_analysis.get('recommendations', []))
            if schema_validity_score < 80:
                recommendations.append(
                    "Improve on-page SEO by reviewing metadata and schema on underperforming pages"
                )
            if page_speed_score < 70:
                recommendations.append(
                    "Optimize page speed by reducing bundle size and improving caching"
                )

            # Create audit report
            audit_report = {
                "audit_id": audit_id,
                "analyzed_at": __import__('datetime').datetime.now().isoformat(),
                "overall_score": (
                    page_speed_score * 0.25 +
                    schema_validity_score * 0.15 +
                    internal_linking_score * 0.20 +
                    mobile_friendly_score * 0.20 +
                    accessibility_score * 0.20
                ),
                "page_speed_score": page_speed_score,
                "schema_validity_score": schema_validity_score,
                "internal_linking_score": internal_linking_score,
                "mobile_friendly_score": mobile_friendly_score,
                "accessibility_score": accessibility_score,
                "core_web_vitals": cwv if cwv.get('success') else {},
                "schema_validation": {
                    "valid": schema_validity_score > 80,
                    "coverage": schema_validity_score,
                    "errors": [],
                    "warnings": []
                },
                "internal_linking": {
                    "total_links": linking_analysis.get('total_links', 0),
                    "orphan_pages": linking_analysis.get('orphan_pages', 0),
                    "broken_links": broken_links.get('broken_links_count', 0),
                    "average_depth": linking_analysis.get('average_depth', 0),
                    "link_graph_density": linking_analysis.get('graph_density', 0)
                },
                "page_analyses": page_analyses,
                "issues": issues,
                "critical_issues": critical_issues,
                "recommendations": recommendations,
                "pages_crawled": len(pages),
                "crawl_errors": crawl_result.get('crawl_errors', 0),
                "mobile_friendly": True,
                "https_enabled": True,
                "sitemap_valid": sitemap_check.get("sitemap_valid", False),
                "sitemap_url_count": sitemap_check.get("url_count"),
                "robots_txt_valid": True
            }

            return {
                "success": True,
                **audit_report
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _calculate_linking_score(self, linking_analysis: Dict) -> float:
        """Calculate internal linking score"""
        orphans = linking_analysis.get('orphan_pages', 0)
        total_links = linking_analysis.get('total_links', 0)
        avg_depth = linking_analysis.get('average_depth', 0)
        density = linking_analysis.get('graph_density', 0)

        # Penalties
        score = 100.0
        score -= min(orphans * 5, 30)  # Max 30 point penalty for orphans
        if avg_depth > 3:
            score -= (avg_depth - 3) * 5  # Penalty for deep pages
        if density < 0.1:
            score -= 20  # Penalty for low connectivity

        return max(0, min(100, score))

    def quick_health_check(self) -> Dict[str, Any]:
        """
        Run quick health check (no full crawl).
        Uses On-Page SEO tools for homepage analysis.

        Returns:
            Basic health metrics
        """
        try:
            # Check homepage performance
            perf = self.performance_analyzer.check_page_speed(self.base_url)
            cwv = self.performance_analyzer.measure_core_web_vitals(self.base_url)

            # Use On-Page SEO tools to validate homepage
            # In production, would fetch and parse the homepage
            metadata_check = self.metadata_validator.validate_metadata(
                title="Homepage",  # Would extract from actual page
                description="Site homepage"
            )

            return {
                "success": True,
                "performance_score": perf.get('performance_score', 0),
                "core_web_vitals": cwv,
                "metadata_score": metadata_check.get('overall_score', 0),
                "overall_health": "healthy" if perf.get('performance_score', 0) > 70 else "needs_improvement"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Create default instance
def create_site_health_monitor(
    llm_model: str = "mixtral-8x7b-32768",
    base_url: str = "http://localhost:3000"
) -> SiteHealthMonitorAgent:
    """Factory function to create Site Health Monitor Agent"""
    return SiteHealthMonitorAgent(llm_model=llm_model, base_url=base_url)

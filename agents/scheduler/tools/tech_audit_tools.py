"""
Tech Stack Audit Tools
Tools for dependency analysis, vulnerability scanning, build performance, and cost tracking
"""
from crewai.tools import tool
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import subprocess
from pathlib import Path
import os
import re

from agents.scheduler.schemas.analysis_schemas import (
    Vulnerability,
    BuildMetrics,
    APICosts,
    DependencyInfo,
    IssueSeverity
)


class DependencyAnalyzer:
    """Analyzes project dependencies"""

    def __init__(self, project_path: str = "/root/contentflowz-lab"):
        self.project_path = Path(project_path)

    @tool("Analyze Dependencies")
    def analyze_dependencies(self, package_manager: str = "auto") -> Dict[str, Any]:
        """
        Analyze project dependencies for outdated packages.

        Args:
            package_manager: Package manager to use (npm, pip, auto)

        Returns:
            List of dependencies with version information
        """
        try:
            if package_manager == "auto":
                if (self.project_path / "package.json").exists():
                    return self._analyze_npm_dependencies()
                elif (self.project_path / "requirements.txt").exists():
                    return self._analyze_pip_dependencies()
                else:
                    return {
                        "success": False,
                        "error": "No package.json or requirements.txt found"
                    }
            elif package_manager == "npm":
                return self._analyze_npm_dependencies()
            elif package_manager == "pip":
                return self._analyze_pip_dependencies()
            else:
                return {
                    "success": False,
                    "error": f"Unsupported package manager: {package_manager}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_npm_dependencies(self) -> Dict[str, Any]:
        """Analyze npm dependencies"""
        try:
            # Read package.json
            package_json_path = self.project_path / "package.json"
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)

            dependencies = {
                **package_data.get('dependencies', {}),
                **package_data.get('devDependencies', {})
            }

            # Check for outdated packages
            cmd = f"cd {self.project_path} && npm outdated --json"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            outdated = {}
            if result.stdout:
                try:
                    outdated = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            # Build dependency list
            dep_list = []
            for name, version in dependencies.items():
                is_outdated = name in outdated
                dep_info = DependencyInfo(
                    name=name,
                    current_version=version,
                    latest_version=outdated.get(name, {}).get('latest', version),
                    is_outdated=is_outdated,
                    has_vulnerabilities=False  # Will be checked separately
                )
                dep_list.append(dep_info.dict())

            outdated_count = sum(1 for d in dep_list if d['is_outdated'])

            return {
                "success": True,
                "package_manager": "npm",
                "total_dependencies": len(dep_list),
                "outdated_dependencies": outdated_count,
                "dependencies": dep_list
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_pip_dependencies(self) -> Dict[str, Any]:
        """Analyze pip dependencies"""
        try:
            req_file = self.project_path / "requirements.txt"
            if not req_file.exists():
                return {
                    "success": False,
                    "error": "requirements.txt not found"
                }

            # Parse requirements.txt
            with open(req_file, 'r') as f:
                requirements = f.readlines()

            dep_list = []
            for req in requirements:
                req = req.strip()
                if not req or req.startswith('#'):
                    continue

                # Parse package name and version
                match = re.match(r'([a-zA-Z0-9_-]+)([=<>]+)?([\d.]+)?', req)
                if match:
                    name = match.group(1)
                    current_version = match.group(3) or "unknown"

                    dep_info = DependencyInfo(
                        name=name,
                        current_version=current_version,
                        latest_version=current_version,  # Would check PyPI
                        is_outdated=False,
                        has_vulnerabilities=False
                    )
                    dep_list.append(dep_info.dict())

            return {
                "success": True,
                "package_manager": "pip",
                "total_dependencies": len(dep_list),
                "outdated_dependencies": 0,  # Would use pip list --outdated
                "dependencies": dep_list
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("Check Sitemap Plugin")
    def check_sitemap_plugin(self, project_path: str) -> Dict[str, Any]:
        """
        Verify that a project has a proper sitemap integration configured.

        Checks both package.json (installed) and the framework config file (active).
        Supports Astro (@astrojs/sitemap) and Next.js (next-sitemap or built-in sitemap.ts).

        Args:
            project_path: Absolute path to the project root

        Returns:
            Dict with framework, installed, configured, warnings fields
        """
        try:
            root = Path(project_path)
            warnings = []

            # Detect framework
            package_json_path = root / "package.json"
            if not package_json_path.exists():
                return {
                    "success": False,
                    "error": f"No package.json found at {project_path}"
                }

            with open(package_json_path) as f:
                pkg = json.load(f)

            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {})
            }

            is_astro = "astro" in all_deps
            is_nextjs = "next" in all_deps
            framework = "astro" if is_astro else ("nextjs" if is_nextjs else "unknown")

            if framework == "unknown":
                return {
                    "success": True,
                    "framework": "unknown",
                    "installed": False,
                    "configured": False,
                    "warnings": ["Could not detect Astro or Next.js in package.json"]
                }

            # Astro check
            if is_astro:
                plugin = "@astrojs/sitemap"
                installed = plugin in all_deps

                # Check config file for active usage
                config_files = list(root.glob("astro.config.*"))
                configured = False
                if config_files:
                    config_text = config_files[0].read_text()
                    configured = "sitemap" in config_text and "sitemap()" in config_text

                if not installed:
                    warnings.append(f"'{plugin}' not found in package.json — run: pnpm add {plugin}")
                if not configured:
                    warnings.append("sitemap() not found in astro.config.* integrations — add it and set site: 'https://...'")

                return {
                    "success": True,
                    "framework": "astro",
                    "plugin": plugin,
                    "installed": installed,
                    "configured": configured,
                    "config_file": str(config_files[0]) if config_files else None,
                    "warnings": warnings,
                    "ok": installed and configured
                }

            # Next.js check
            if is_nextjs:
                # Option 1: built-in App Router sitemap (app/sitemap.ts or app/sitemap.js)
                builtin_sitemap = any(
                    (root / "app" / f"sitemap.{ext}").exists()
                    for ext in ("ts", "tsx", "js", "jsx")
                )
                # Option 2: next-sitemap package
                plugin = "next-sitemap"
                next_sitemap_installed = plugin in all_deps
                next_sitemap_configured = (root / "next-sitemap.config.js").exists() or (root / "next-sitemap.config.ts").exists()

                installed = builtin_sitemap or next_sitemap_installed
                configured = builtin_sitemap or next_sitemap_configured

                if not installed:
                    warnings.append("No sitemap found — add app/sitemap.ts (App Router) or install next-sitemap")
                elif next_sitemap_installed and not next_sitemap_configured:
                    warnings.append("next-sitemap installed but next-sitemap.config.js not found")

                return {
                    "success": True,
                    "framework": "nextjs",
                    "builtin_sitemap": builtin_sitemap,
                    "plugin": plugin if next_sitemap_installed else None,
                    "installed": installed,
                    "configured": configured,
                    "warnings": warnings,
                    "ok": installed and configured
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class VulnerabilityScanner:
    """Scans for security vulnerabilities"""

    def __init__(self, project_path: str = "/root/contentflowz-lab"):
        self.project_path = Path(project_path)

    @tool("Scan for Vulnerabilities")
    def scan_vulnerabilities(self) -> Dict[str, Any]:
        """
        Scan dependencies for security vulnerabilities.

        Returns:
            List of vulnerabilities found
        """
        try:
            # Try npm audit for Node projects
            if (self.project_path / "package.json").exists():
                return self._npm_audit()

            # Try pip-audit for Python projects
            elif (self.project_path / "requirements.txt").exists():
                return self._pip_audit()

            else:
                return {
                    "success": False,
                    "error": "No supported dependency file found"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _npm_audit(self) -> Dict[str, Any]:
        """Run npm audit"""
        try:
            cmd = f"cd {self.project_path} && npm audit --json"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if not result.stdout:
                return {
                    "success": True,
                    "vulnerabilities": [],
                    "critical": 0,
                    "high": 0,
                    "message": "No vulnerabilities found"
                }

            audit_data = json.loads(result.stdout)
            vulnerabilities = []

            for vuln_id, vuln_data in audit_data.get('vulnerabilities', {}).items():
                vuln = Vulnerability(
                    vuln_id=vuln_id,
                    package_name=vuln_data.get('name', 'unknown'),
                    installed_version=vuln_data.get('range', 'unknown'),
                    patched_version=vuln_data.get('fixAvailable', {}).get('version'),
                    severity=vuln_data.get('severity', 'low'),
                    title=vuln_data.get('title', ''),
                    description=vuln_data.get('url', ''),
                    recommendation=f"Update to {vuln_data.get('fixAvailable', {}).get('version', 'latest')}"
                )
                vulnerabilities.append(vuln.dict())

            critical = sum(1 for v in vulnerabilities if v['severity'] == 'critical')
            high = sum(1 for v in vulnerabilities if v['severity'] == 'high')

            return {
                "success": True,
                "total_vulnerabilities": len(vulnerabilities),
                "critical": critical,
                "high": high,
                "vulnerabilities": vulnerabilities
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "npm audit timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _pip_audit(self) -> Dict[str, Any]:
        """Run pip vulnerability check"""
        try:
            # Note: Requires safety or pip-audit installed
            cmd = f"cd {self.project_path} && pip-audit --format json"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and not result.stdout:
                return {
                    "success": True,
                    "vulnerabilities": [],
                    "message": "No vulnerabilities found"
                }

            # Parse results
            vulnerabilities = []
            if result.stdout:
                try:
                    audit_data = json.loads(result.stdout)
                    # Process pip-audit format
                    for vuln in audit_data.get('vulnerabilities', []):
                        vulnerabilities.append(vuln)
                except json.JSONDecodeError:
                    pass

            return {
                "success": True,
                "total_vulnerabilities": len(vulnerabilities),
                "vulnerabilities": vulnerabilities
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "note": "Install pip-audit: pip install pip-audit"
            }


class BuildAnalyzer:
    """Analyzes build performance"""

    def __init__(self, project_path: str = "/root/contentflowz-lab"):
        self.project_path = Path(project_path)

    @tool("Analyze Build Performance")
    def analyze_build(self) -> Dict[str, Any]:
        """
        Analyze build performance metrics.

        Returns:
            Build metrics including time, size, and cache efficiency
        """
        try:
            # Check if it's an Astro project
            if (self.project_path / "astro.config.mjs").exists():
                return self._analyze_astro_build()

            # Check if it's a Next.js project
            elif (self.project_path / "next.config.js").exists():
                return self._analyze_nextjs_build()

            else:
                return {
                    "success": False,
                    "error": "Unsupported project type"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_astro_build(self) -> Dict[str, Any]:
        """Analyze Astro build"""
        try:
            # Run build and time it
            start_time = datetime.now()

            cmd = f"cd {self.project_path} && npm run build"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            build_time = (datetime.now() - start_time).total_seconds()

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": "Build failed",
                    "build_output": result.stderr
                }

            # Analyze output directory
            dist_path = self.project_path / "dist"
            if not dist_path.exists():
                return {
                    "success": False,
                    "error": "dist directory not found"
                }

            # Calculate total size
            total_size = sum(
                f.stat().st_size
                for f in dist_path.rglob('*') if f.is_file()
            )
            total_size_mb = total_size / (1024 * 1024)

            # Count assets
            asset_count = sum(1 for _ in dist_path.rglob('*') if _.is_file())

            # Determine trend (would compare with historical data)
            trend = "stable"

            build_metrics = BuildMetrics(
                build_time_seconds=build_time,
                bundle_size_mb=total_size_mb,
                asset_count=asset_count,
                cache_hit_rate=0.0,  # Would track cache usage
                build_trend=trend
            )

            return {
                "success": True,
                **build_metrics.dict(),
                "recommendations": self._get_build_recommendations(build_metrics)
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Build timeout (>5 minutes)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_nextjs_build(self) -> Dict[str, Any]:
        """Analyze Next.js build"""
        # Similar implementation for Next.js
        return {
            "success": True,
            "message": "Next.js build analysis not yet implemented"
        }

    def _get_build_recommendations(self, metrics: BuildMetrics) -> List[str]:
        """Generate build recommendations"""
        recommendations = []

        if metrics.build_time_seconds > 120:
            recommendations.append(
                "Build time is high (>2min). Consider optimizing dependencies or build config."
            )

        if metrics.bundle_size_mb > 10:
            recommendations.append(
                "Bundle size is large (>10MB). Consider code splitting and tree-shaking."
            )

        if metrics.cache_hit_rate < 0.5:
            recommendations.append(
                "Low cache hit rate. Review caching strategy for build tools."
            )

        return recommendations


class CostTracker:
    """Tracks API costs and usage"""

    def __init__(self, data_dir: str = "/root/contentflowz-lab/data/scheduler"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.costs_file = self.data_dir / "api_costs.json"

    @tool("Track API Costs")
    def track_costs(
        self,
        api_name: str,
        requests_count: int,
        cost_usd: float
    ) -> Dict[str, Any]:
        """
        Track API usage and costs.

        Args:
            api_name: Name of the API (e.g., "OpenAI", "Exa", "Firecrawl")
            requests_count: Number of requests made
            cost_usd: Cost in USD

        Returns:
            Updated cost tracking data
        """
        try:
            # Load existing data
            if self.costs_file.exists():
                with open(self.costs_file, 'r') as f:
                    costs_data = json.load(f)
            else:
                costs_data = []

            # Add new entry
            entry = {
                "api_name": api_name,
                "requests_count": requests_count,
                "cost_usd": cost_usd,
                "timestamp": datetime.now().isoformat()
            }
            costs_data.append(entry)

            # Save
            with open(self.costs_file, 'w') as f:
                json.dump(costs_data, f, indent=2)

            return {
                "success": True,
                "message": f"Logged {requests_count} requests costing ${cost_usd:.4f}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("Get Cost Summary")
    def get_cost_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get cost summary for a time period.

        Args:
            days: Number of days to analyze

        Returns:
            Cost summary by API and forecast
        """
        try:
            if not self.costs_file.exists():
                return {
                    "success": True,
                    "message": "No cost data available",
                    "total_cost": 0
                }

            with open(self.costs_file, 'r') as f:
                costs_data = json.load(f)

            cutoff = datetime.now() - timedelta(days=days)
            recent_costs = [
                entry for entry in costs_data
                if datetime.fromisoformat(entry['timestamp']) > cutoff
            ]

            # Group by API
            by_api = {}
            for entry in recent_costs:
                api = entry['api_name']
                if api not in by_api:
                    by_api[api] = {
                        "requests": 0,
                        "cost": 0.0
                    }
                by_api[api]['requests'] += entry['requests_count']
                by_api[api]['cost'] += entry['cost_usd']

            total_cost = sum(api_data['cost'] for api_data in by_api.values())

            # Forecast monthly cost (simple linear extrapolation)
            daily_cost = total_cost / days
            forecast_monthly = daily_cost * 30

            return {
                "success": True,
                "period_days": days,
                "total_cost_usd": total_cost,
                "forecast_monthly_usd": forecast_monthly,
                "by_api": by_api,
                "cost_breakdown": [
                    APICosts(
                        api_name=api,
                        requests_count=data['requests'],
                        cost_usd=data['cost'],
                        quota_used_percent=0.0,  # Would need quota data
                        forecast_monthly_cost=(data['cost'] / days) * 30,
                        period_start=cutoff,
                        period_end=datetime.now()
                    ).dict()
                    for api, data in by_api.items()
                ]
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

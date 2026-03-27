"""
Publishing Tools
Tools for Git deployment, Google integration, and deployment monitoring
"""
from crewai.tools import tool
from typing import List, Dict, Any, Optional
from datetime import datetime
import subprocess
import json
import os
from pathlib import Path
import time
import requests

from agents.scheduler.schemas.publishing_schemas import (
    DeploymentResult,
    GoogleIndexingStatus
)


class GitDeployer:
    """Handles Git operations and deployment"""

    def __init__(self, repo_path: str = "/root/contentflowz-lab", project_id: Optional[str] = None):
        self._project_id = project_id
        self._repo_path_override = repo_path
        self.github_token = os.getenv("GITHUB_TOKEN")
        self._resolved = False

    async def _resolve_repo_path(self) -> Path:
        """Resolve repo path: use project DB lookup if project_id provided, else fallback."""
        if self._resolved:
            return self.repo_path

        if self._project_id:
            try:
                from agents.seo.config.project_store import ProjectStore
                store = ProjectStore()
                project = await store.get_by_id(self._project_id)
                if project and project.settings and project.settings.local_repo_path:
                    self.repo_path = Path(project.settings.local_repo_path)
                    self._resolved = True
                    return self.repo_path
            except Exception:
                pass

        self.repo_path = Path(self._repo_path_override)
        self._resolved = True
        return self.repo_path

    @tool("Deploy Content to Production")
    def deploy_to_production(
        self,
        content_path: str,
        commit_message: str,
        auto_push: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy content to production via Git commit and push.

        Args:
            content_path: Path to content file
            commit_message: Git commit message
            auto_push: Whether to automatically push to remote (default: True)

        Returns:
            Deployment result with commit SHA and status
        """
        start_time = time.time()

        try:
            # Verify file exists
            full_path = self.repo_path / content_path
            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"Content file not found: {content_path}"
                }

            # Git add
            add_cmd = f"git -C {self.repo_path} add {content_path}"
            result = subprocess.run(
                add_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Git add failed: {result.stderr}"
                }

            # Git commit
            commit_cmd = f'git -C {self.repo_path} commit -m "{commit_message}"'
            result = subprocess.run(
                commit_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                # Check if it's "nothing to commit"
                if "nothing to commit" in result.stdout:
                    return {
                        "success": True,
                        "message": "No changes to commit",
                        "deployment_time_seconds": time.time() - start_time
                    }
                return {
                    "success": False,
                    "error": f"Git commit failed: {result.stderr}"
                }

            # Get commit SHA
            sha_cmd = f"git -C {self.repo_path} rev-parse HEAD"
            result = subprocess.run(
                sha_cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            commit_sha = result.stdout.strip()

            # Git push if auto_push
            if auto_push:
                push_cmd = f"git -C {self.repo_path} push origin main"
                result = subprocess.run(
                    push_cmd,
                    shell=True,
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "commit_sha": commit_sha,
                        "error": f"Git push failed: {result.stderr}",
                        "rollback_available": True
                    }

            deployment_time = time.time() - start_time

            return {
                "success": True,
                "commit_sha": commit_sha,
                "message": f"Deployed successfully in {deployment_time:.2f}s",
                "deployment_time_seconds": deployment_time,
                "pushed": auto_push
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "deployment_time_seconds": time.time() - start_time
            }

    @tool("Rollback Deployment")
    def rollback_deployment(self, commit_sha: str) -> Dict[str, Any]:
        """
        Rollback to a previous commit.

        Args:
            commit_sha: Commit SHA to rollback to

        Returns:
            Rollback result
        """
        try:
            # Git reset
            reset_cmd = f"git -C {self.repo_path} reset --hard {commit_sha}"
            result = subprocess.run(
                reset_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Rollback failed: {result.stderr}"
                }

            # Force push
            push_cmd = f"git -C {self.repo_path} push --force origin main"
            result = subprocess.run(
                push_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Force push failed: {result.stderr}"
                }

            return {
                "success": True,
                "message": f"Rolled back to {commit_sha}",
                "commit_sha": commit_sha
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class GoogleIntegration:
    """Integrates with Google Search Console and Indexing API.

    Auth: Service account JSON credentials file.
    Setup:
      1. Google Cloud Console → Create service account → Download JSON key
      2. Google Search Console → Add service account email as owner
      3. Set GOOGLE_CREDENTIALS_FILE=/path/to/service_account.json
      4. Set GOOGLE_SITE_URL=https://your-site.com (or sc-domain:your-site.com)
    """

    INDEXING_SCOPES = ["https://www.googleapis.com/auth/indexing"]
    SEARCH_CONSOLE_SCOPES = ["https://www.googleapis.com/auth/webmasters"]
    INDEXING_DAILY_LIMIT = 200

    def __init__(self):
        self.credentials_file = (
            os.getenv("GOOGLE_CREDENTIALS_FILE")
            or os.getenv("GOOGLE_SEARCH_CONSOLE_CREDENTIALS")  # backward compat
        )
        self.site_url = os.getenv("GOOGLE_SITE_URL", "")
        self._indexing_service = None
        self._search_console_service = None

    def _get_credentials(self, scopes: List[str]):
        try:
            from google.oauth2 import service_account
        except ImportError:
            raise RuntimeError(
                "google-auth not installed. Run: pip install google-auth google-api-python-client"
            )

        if not self.credentials_file:
            raise ValueError(
                "GOOGLE_CREDENTIALS_FILE not set. "
                "Download service account JSON from Google Cloud Console."
            )

        creds_path = Path(self.credentials_file)
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Service account credentials not found: {self.credentials_file}"
            )

        return service_account.Credentials.from_service_account_file(
            str(creds_path), scopes=scopes
        )

    def _get_indexing_service(self):
        if self._indexing_service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError:
                raise RuntimeError(
                    "google-api-python-client not installed. Run: pip install google-api-python-client"
                )
            creds = self._get_credentials(self.INDEXING_SCOPES)
            self._indexing_service = build("indexing", "v3", credentials=creds, cache_discovery=False)
        return self._indexing_service

    def _get_search_console_service(self):
        if self._search_console_service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError:
                raise RuntimeError(
                    "google-api-python-client not installed. Run: pip install google-api-python-client"
                )
            creds = self._get_credentials(self.SEARCH_CONSOLE_SCOPES)
            self._search_console_service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return self._search_console_service

    @tool("Submit Sitemap to Google Search Console")
    def submit_to_google_search_console(self, urls: List[str]) -> Dict[str, Any]:
        """
        Submit sitemaps to Google Search Console.

        Args:
            urls: List of sitemap URLs to submit (e.g. ["https://site.com/sitemap.xml"])

        Returns:
            Submission results for each sitemap URL
        """
        try:
            if not self.site_url:
                return {
                    "success": False,
                    "error": "GOOGLE_SITE_URL not set (e.g. https://your-site.com)"
                }

            service = self._get_search_console_service()
            results = []
            errors = []

            for sitemap_url in urls:
                try:
                    service.sitemaps().submit(
                        siteUrl=self.site_url,
                        feedpath=sitemap_url
                    ).execute()
                    results.append({
                        "url": sitemap_url,
                        "status": "submitted",
                        "submitted_at": datetime.now().isoformat()
                    })
                except Exception as e:
                    error_msg = str(e)
                    results.append({
                        "url": sitemap_url,
                        "status": "error",
                        "error": error_msg
                    })
                    errors.append(f"{sitemap_url}: {error_msg}")

            return {
                "success": len(errors) == 0,
                "site_url": self.site_url,
                "urls_submitted": len(urls) - len(errors),
                "errors": errors,
                "results": results,
                "message": f"Submitted {len(urls) - len(errors)}/{len(urls)} sitemaps to Google Search Console"
            }

        except (RuntimeError, ValueError, FileNotFoundError) as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @tool("Trigger Google Indexing API")
    def trigger_google_indexing(
        self,
        urls: List[str],
        action: str = "URL_UPDATED"
    ) -> Dict[str, Any]:
        """
        Notify Google Indexing API of new or updated URLs for fast crawling.
        Rate limit: 200 URLs/day. Best for job postings, live events, and fresh content.

        Args:
            urls: List of URLs to notify (max 200/day)
            action: URL_UPDATED (publish/update) or URL_DELETED (remove from index)

        Returns:
            Indexing API results per URL
        """
        if action not in ("URL_UPDATED", "URL_DELETED"):
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Use URL_UPDATED or URL_DELETED."
            }

        if len(urls) > self.INDEXING_DAILY_LIMIT:
            return {
                "success": False,
                "error": f"Too many URLs ({len(urls)}): daily quota is {self.INDEXING_DAILY_LIMIT}. Split into batches."
            }

        try:
            service = self._get_indexing_service()
        except (RuntimeError, ValueError, FileNotFoundError) as e:
            return {"success": False, "error": str(e)}

        results = []
        errors = []

        for url in urls:
            try:
                service.urlNotifications().publish(
                    body={"url": url, "type": action}
                ).execute()
                results.append(GoogleIndexingStatus(
                    url=url,
                    status="submitted",
                    submitted_at=datetime.now(),
                ).model_dump())
            except Exception as e:
                error_msg = str(e)
                results.append(GoogleIndexingStatus(
                    url=url,
                    status="error",
                    submitted_at=datetime.now(),
                    error_message=error_msg,
                ).model_dump())
                errors.append(f"{url}: {error_msg}")

            # Avoid hammering the API when submitting many URLs
            if len(urls) > 1:
                time.sleep(0.1)

        successful = len(urls) - len(errors)
        return {
            "success": len(errors) == 0,
            "urls_submitted": successful,
            "urls_failed": len(errors),
            "daily_quota_used": len(urls),
            "daily_quota_remaining": self.INDEXING_DAILY_LIMIT - len(urls),
            "indexing_requests": results,
            "errors": errors,
            "message": f"Submitted {successful}/{len(urls)} URLs to Google Indexing API"
        }

    @tool("Check Indexing Status")
    def check_indexing_status(self, urls: List[str]) -> Dict[str, Any]:
        """
        Check indexing status of URLs via Google Search Console URL Inspection API.

        Args:
            urls: List of URLs to inspect

        Returns:
            Indexing status for each URL (indexed, coverage state, last crawl date)
        """
        if not self.site_url:
            return {
                "success": False,
                "error": "GOOGLE_SITE_URL not set (e.g. https://your-site.com)"
            }

        try:
            service = self._get_search_console_service()
        except (RuntimeError, ValueError, FileNotFoundError) as e:
            return {"success": False, "error": str(e)}

        results = []
        errors = []

        for url in urls:
            try:
                response = service.urlInspection().index().inspect(
                    body={
                        "inspectionUrl": url,
                        "siteUrl": self.site_url,
                    }
                ).execute()

                inspection = response.get("inspectionResult", {})
                index_status = inspection.get("indexStatusResult", {})
                coverage = index_status.get("coverageState", "unknown")

                results.append({
                    "url": url,
                    "is_indexed": coverage in ("Submitted and indexed", "Indexed, not submitted in sitemap"),
                    "coverage_state": coverage,
                    "last_crawled": index_status.get("lastCrawlTime"),
                    "verdict": index_status.get("verdict", "VERDICT_UNSPECIFIED"),
                    "robots_txt_state": index_status.get("robotsTxtState", "UNKNOWN"),
                    "indexing_state": index_status.get("indexingState", "UNKNOWN"),
                })
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "url": url,
                    "is_indexed": False,
                    "coverage_state": "error",
                    "error": error_msg,
                })
                errors.append(f"{url}: {error_msg}")

            # Rate limit: 2000 req/day; space them slightly
            if len(urls) > 1:
                time.sleep(0.1)

        return {
            "success": len(errors) == 0,
            "total_urls": len(urls),
            "indexed": sum(1 for r in results if r.get("is_indexed")),
            "not_indexed": sum(1 for r in results if not r.get("is_indexed")),
            "errors": errors,
            "results": results
        }


class DeploymentMonitor:
    """Monitors deployment health and status"""

    def __init__(self, data_dir: str = "/root/contentflowz-lab/data/scheduler"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.deployments_file = self.data_dir / "deployments.json"

    @tool("Monitor Deployment Status")
    def monitor_deployment(
        self,
        deployment_id: str,
        urls: List[str]
    ) -> Dict[str, Any]:
        """
        Monitor deployment status and health.

        Args:
            deployment_id: Unique deployment identifier
            urls: URLs to monitor

        Returns:
            Health status for each URL
        """
        try:
            health_checks = []

            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    health_checks.append({
                        "url": url,
                        "status_code": response.status_code,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "healthy": response.status_code == 200
                    })
                except requests.RequestException as e:
                    health_checks.append({
                        "url": url,
                        "status_code": None,
                        "error": str(e),
                        "healthy": False
                    })

            total_urls = len(health_checks)
            healthy_urls = sum(1 for hc in health_checks if hc['healthy'])

            return {
                "success": True,
                "deployment_id": deployment_id,
                "total_urls": total_urls,
                "healthy_urls": healthy_urls,
                "success_rate": (healthy_urls / total_urls * 100) if total_urls > 0 else 0,
                "health_checks": health_checks,
                "overall_status": "healthy" if healthy_urls == total_urls else "degraded"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("Log Deployment")
    def log_deployment(self, deployment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Log deployment to history.

        Args:
            deployment_data: Deployment information to log

        Returns:
            Log result
        """
        try:
            # Load existing deployments
            if self.deployments_file.exists():
                with open(self.deployments_file, 'r') as f:
                    deployments = json.load(f)
            else:
                deployments = []

            # Add timestamp
            deployment_data['logged_at'] = datetime.now().isoformat()

            # Append
            deployments.append(deployment_data)

            # Save
            with open(self.deployments_file, 'w') as f:
                json.dump(deployments, f, indent=2, default=str)

            return {
                "success": True,
                "deployment_id": deployment_data.get('deployment_id'),
                "message": "Deployment logged successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @tool("Get Deployment History")
    def get_deployment_history(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent deployment history.

        Args:
            limit: Number of recent deployments to return

        Returns:
            List of recent deployments
        """
        try:
            if not self.deployments_file.exists():
                return {
                    "success": True,
                    "deployments": [],
                    "message": "No deployment history available"
                }

            with open(self.deployments_file, 'r') as f:
                deployments = json.load(f)

            # Get most recent
            recent = sorted(
                deployments,
                key=lambda x: x.get('logged_at', ''),
                reverse=True
            )[:limit]

            # Calculate stats
            total = len(deployments)
            successful = sum(1 for d in deployments if d.get('success', False))

            return {
                "success": True,
                "total_deployments": total,
                "successful_deployments": successful,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "recent_deployments": recent
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

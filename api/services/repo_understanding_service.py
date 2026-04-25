"""Repo and site understanding service for persona draft generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from agents.seo.config.project_store import project_store
from api.models.persona_draft import (
    EvidenceItem,
    ExistingCreatorProfile,
    PersonaDraftRequest,
    RepoUnderstandingResult,
)
from api.services.user_data_store import user_data_store
from api.services.user_llm_service import user_llm_service


def _snippet(text: str, limit: int = 300) -> str:
    cleaned = " ".join(text.replace("\n", " ").split())
    return cleaned[:limit]


def _truncate(text: str, limit: int = 4000) -> str:
    return text[:limit]


def _parse_github_repo(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _extract_json_block(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        raise RuntimeError("LLM response is not JSON serializable.")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM response is not valid JSON.") from exc


class RepoUnderstandingService:
    """Collect project signals and synthesize a persona-ready understanding."""

    def _local_repo_candidates(self, root: Path) -> list[str]:
        candidates: list[str] = []
        explicit = [
            "README.md",
            "readme.md",
            "README.mdx",
            "docs/README.md",
            "docs/index.md",
            "docs/getting-started.md",
            "package.json",
            "pyproject.toml",
            "src/pages/index.astro",
            "src/pages/index.tsx",
            "src/pages/index.jsx",
            "src/app/page.tsx",
            "src/app/page.jsx",
            "pages/index.tsx",
            "pages/index.jsx",
            "content/index.md",
            "blog/index.md",
        ]
        for rel in explicit:
            if (root / rel).is_file():
                candidates.append(rel)

        glob_patterns = [
            "src/pages/about*",
            "src/pages/pricing*",
            "src/pages/docs*",
            "src/pages/blog*",
            "src/app/about*/page.*",
            "src/app/pricing*/page.*",
            "src/app/docs*/page.*",
            "src/app/blog*/page.*",
            "pages/about*",
            "pages/pricing*",
            "pages/docs*",
            "pages/blog*",
            "docs/**/*.md",
            "blog/**/*.md",
            "src/content/**/*.md",
            "src/content/**/*.mdx",
        ]
        for pattern in glob_patterns:
            for path in sorted(root.glob(pattern)):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                if rel not in candidates:
                    candidates.append(rel)
                if len(candidates) >= 10:
                    return candidates
        return candidates[:10]

    async def _collect_local_repo(
        self,
        repo_path: str,
    ) -> tuple[str, list[EvidenceItem]]:
        root = Path(repo_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise RuntimeError("Local repository path does not exist.")

        evidence: list[EvidenceItem] = []
        chunks: list[str] = []
        for rel in self._local_repo_candidates(root):
            full = root / rel
            try:
                content = full.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not content.strip():
                continue
            evidence.append(
                EvidenceItem(
                    source="local_repo",
                    location=rel,
                    snippet=_snippet(content, limit=300),
                )
            )
            chunks.append(f"## {rel}\n{_truncate(content)}")
            if len(evidence) >= 10:
                break
        return "\n\n".join(chunks), evidence

    async def _collect_github_repo(
        self,
        repo_url: str,
        *,
        token: str | None = None,
    ) -> tuple[str, list[EvidenceItem]]:
        parsed = _parse_github_repo(repo_url)
        if not parsed:
            raise RuntimeError("Invalid GitHub repository URL.")
        owner, repo = parsed
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        evidence: list[EvidenceItem] = []
        chunks: list[str] = []
        readme_urls = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/readme.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.mdx",
        ]

        async with httpx.AsyncClient(timeout=12.0) as client:
            for url in readme_urls:
                response = await client.get(url, headers=headers)
                if response.status_code < 400 and response.text.strip():
                    evidence.append(
                        EvidenceItem(
                            source="github_repo",
                            location=url,
                            snippet=_snippet(response.text, limit=300),
                        )
                    )
                    chunks.append(f"## README\n{_truncate(response.text)}")
                    break

            repo_api = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            if repo_api.status_code < 400:
                payload = repo_api.json() if isinstance(repo_api.json(), dict) else {}
                summary = {
                    "name": payload.get("full_name"),
                    "description": payload.get("description"),
                    "homepage": payload.get("homepage"),
                    "topics": payload.get("topics") or [],
                }
                summary_json = json.dumps(summary, ensure_ascii=True)
                evidence.append(
                    EvidenceItem(
                        source="github_repo",
                        location=f"{owner}/{repo}",
                        snippet=_snippet(summary_json, limit=300),
                    )
                )
                chunks.append(f"## Repo metadata\n{summary_json}")

                homepage = payload.get("homepage")
                if isinstance(homepage, str) and homepage.strip():
                    evidence.append(
                        EvidenceItem(
                            source="github_repo",
                            location=homepage.strip(),
                            snippet=_snippet(homepage.strip(), limit=300),
                        )
                    )

            contents_api = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents",
                headers=headers,
            )
            if contents_api.status_code < 400:
                items = contents_api.json()
                if isinstance(items, list):
                    priority_names = {
                        "package.json",
                        "pyproject.toml",
                        "about.md",
                        "pricing.md",
                    }
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get("name") or "")
                        if name not in priority_names:
                            continue
                        download_url = item.get("download_url")
                        if not isinstance(download_url, str):
                            continue
                        raw = await client.get(download_url, headers=headers)
                        if raw.status_code >= 400 or not raw.text.strip():
                            continue
                        evidence.append(
                            EvidenceItem(
                                source="github_repo",
                                location=name,
                                snippet=_snippet(raw.text, limit=300),
                            )
                        )
                        chunks.append(f"## {name}\n{_truncate(raw.text)}")
                        if len(evidence) >= 10:
                            break

        if not chunks:
            raise RuntimeError("Could not load GitHub repository content.")
        return "\n\n".join(chunks[:10]), evidence[:10]

    async def _collect_public_site(
        self,
        manual_url: str,
        *,
        firecrawl_api_key: str | None,
    ) -> tuple[str, list[EvidenceItem]]:
        if not firecrawl_api_key:
            raise RuntimeError("Firecrawl credential is required for manual non-GitHub URLs.")

        try:
            from firecrawl import FirecrawlApp  # type: ignore
        except Exception as exc:
            raise RuntimeError("firecrawl-py is not installed.") from exc

        app = FirecrawlApp(api_key=firecrawl_api_key)
        evidence: list[EvidenceItem] = []
        chunks: list[str] = []
        parsed = urlparse(manual_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        preferred: list[str] = [
            manual_url,
            f"{root}/about",
            f"{root}/pricing",
            f"{root}/docs",
            f"{root}/blog",
        ]

        try:
            mapped = app.map_url(manual_url)
            links = mapped.get("links", []) if isinstance(mapped, dict) else []
            scored: list[str] = []
            for url in links:
                if not isinstance(url, str):
                    continue
                lowered = url.lower()
                if any(key in lowered for key in ("/about", "/pricing", "/docs", "/blog")):
                    scored.append(url)
            for url in scored:
                if url not in preferred:
                    preferred.append(url)
                if len(preferred) >= 5:
                    break
        except Exception:
            pass

        for url in preferred[:5]:
            try:
                result = app.scrape_url(url, formats=["markdown"])
            except Exception:
                continue
            markdown = ""
            if isinstance(result, dict):
                markdown = str(result.get("markdown") or result.get("content") or "")
            if not markdown.strip():
                continue
            evidence.append(
                EvidenceItem(
                    source="manual_url",
                    location=url,
                    snippet=_snippet(markdown, limit=300),
                )
            )
            chunks.append(f"## {url}\n{_truncate(markdown)}")

        if not chunks:
            raise RuntimeError("No crawlable content found for manual_url.")
        return "\n\n".join(chunks[:5]), evidence[:5]

    async def _synthesize_understanding(
        self,
        user_id: str,
        *,
        content: str,
        evidence: list[EvidenceItem],
        request: PersonaDraftRequest,
    ) -> RepoUnderstandingResult:
        evidence_json = json.dumps(
            [item.model_dump() for item in evidence],
            ensure_ascii=True,
            indent=2,
        )
        system_prompt = (
            "You analyze product repositories and websites to infer positioning and likely customer personas. "
            "Return only valid JSON. Be evidence-based, concise, and avoid unsupported claims."
        )
        user_prompt = f"""
Analyze the following repository/site content and return JSON with exactly these keys:
- project_summary: string
- target_audiences: string[]
- icp_hypotheses: string[]
- personal_story_signals: string[]
- positioning_hypotheses: string[]
- persona_candidates: array of objects, each with:
  - name: string
  - demographics: object
  - pain_points: string[]
  - goals: string[]

Rules:
- Ground outputs in the provided evidence only.
- Prefer concrete language over generic marketing phrases.
- Provide 1 to 3 persona_candidates.
- If personal story signals are weak, return an empty list.
- Return valid JSON only.

Context:
- repo_source: {request.repo_source}
- mode: {request.mode}

Evidence:
{evidence_json}

Collected content:
{content}
"""
        payload = await user_llm_service.generate_json(
            user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            route="personas.draft",
        )
        data = _extract_json_block(payload)
        data["evidence"] = [item.model_dump() for item in evidence]
        return RepoUnderstandingResult(**data)

    async def understand(
        self,
        user_id: str,
        request: PersonaDraftRequest,
        *,
        firecrawl_api_key: str | None = None,
    ) -> RepoUnderstandingResult:
        if request.mode == "blank_form":
            return RepoUnderstandingResult()

        if request.repo_source == "project_repo":
            if not request.project_id:
                raise RuntimeError("project_id is required for repo_source=project_repo.")
            project = await project_store.get_by_id(request.project_id)
            if not project or project.user_id != user_id:
                raise RuntimeError("Project not found.")
            repo_path = project.settings.local_repo_path if project.settings else None
            if not repo_path:
                raise RuntimeError("Project local_repo_path is missing. Analyze project first.")
            content, evidence = await self._collect_local_repo(repo_path)
            return await self._synthesize_understanding(
                user_id,
                content=content,
                evidence=evidence,
                request=request,
            )

        if request.repo_source == "connected_github":
            if not request.repo_url:
                raise RuntimeError("repo_url is required for repo_source=connected_github.")
            integration = await user_data_store.get_github_integration(user_id)
            if not integration or not integration.get("token"):
                raise RuntimeError("GitHub integration is required for connected_github source.")
            content, evidence = await self._collect_github_repo(
                request.repo_url,
                token=integration.get("token"),
            )
            return await self._synthesize_understanding(
                user_id,
                content=content,
                evidence=evidence,
                request=request,
            )

        if request.repo_source == "manual_url":
            if request.repo_url and _parse_github_repo(request.repo_url):
                content, evidence = await self._collect_github_repo(request.repo_url, token=None)
            else:
                if not request.manual_url:
                    raise RuntimeError(
                        "manual_url is required for manual_url source when repo_url is not public GitHub."
                    )
                content, evidence = await self._collect_public_site(
                    request.manual_url,
                    firecrawl_api_key=firecrawl_api_key,
                )
            return await self._synthesize_understanding(
                user_id,
                content=content,
                evidence=evidence,
                request=request,
            )

        raise RuntimeError("Unsupported repo_source.")

    def build_persona_draft(
        self,
        understanding: RepoUnderstandingResult,
        creator_profile: ExistingCreatorProfile | None = None,
    ) -> dict[str, Any]:
        candidate = understanding.persona_candidates[0] if understanding.persona_candidates else {}
        demographics = candidate.get("demographics") or {}
        role = str(demographics.get("role") or "Founder").strip()
        industry = str(demographics.get("industry") or "Digital business").strip()
        name = str(candidate.get("name") or "Pragmatic Buyer Persona")
        pain_points = list(candidate.get("pain_points") or ["Inconsistent growth"])
        goals = list(candidate.get("goals") or ["Generate steady pipeline"])
        values = list((creator_profile.values if creator_profile else []) or [])

        return {
            "project_id": None,
            "name": name,
            "avatar": "🧭",
            "demographics": {
                "role": role,
                "industry": industry,
            },
            "pain_points": pain_points,
            "goals": goals,
            "language": {
                "vocabulary": values[:5],
                "objections": ["Not enough time", "Unclear ROI"],
                "triggers": {
                    "emotional": ["confidence", "clarity"],
                    "functional": ["repeatable process", "measurable results"],
                },
            },
            "content_preferences": {
                "formats": ["article", "newsletter"],
                "channels": ["blog", "linkedin"],
                "frequency": "weekly",
            },
            "confidence": min(max(len(understanding.evidence) * 12, 40), 85),
        }


repo_understanding_service = RepoUnderstandingService()

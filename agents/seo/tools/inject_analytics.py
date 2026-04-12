"""Inject or remove the ContentFlow tracking script in a project's site layout.

Used by the deployment agent based on the project's analytics_enabled setting.
Both operations are idempotent — safe to call multiple times.

Usage:
    from agents.seo.tools.inject_analytics import inject_tracking_script, remove_tracking_script

    inject_tracking_script("/path/to/repo", "https://api.contentflow.com")
    remove_tracking_script("/path/to/repo")
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# Framework → candidate layout files (tried in order)
_LAYOUT_CANDIDATES: dict[str, list[str]] = {
    "astro": [
        "src/layouts/Layout.astro",
        "src/layouts/BaseLayout.astro",
        "src/layouts/Default.astro",
    ],
    "next": [
        "app/layout.tsx",
        "app/layout.jsx",
        "pages/_app.tsx",
        "pages/_app.jsx",
        "src/app/layout.tsx",
        "src/app/layout.jsx",
    ],
    "nuxt": [
        "app.vue",
        "layouts/default.vue",
        "src/app.vue",
        "src/layouts/default.vue",
    ],
}

_SCRIPT_MARKER = "/a/s.js"


def _detect_framework(repo_path: Path) -> str | None:
    """Detect the site framework from package.json dependencies."""
    pkg_path = repo_path / "package.json"
    if not pkg_path.exists():
        return None

    try:
        pkg = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    all_deps = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
    }

    if "astro" in all_deps:
        return "astro"
    if "next" in all_deps:
        return "next"
    if "nuxt" in all_deps:
        return "nuxt"

    return None


def _find_layout(repo_path: Path, framework: str) -> Path | None:
    """Find the first existing layout file for the framework."""
    for candidate in _LAYOUT_CANDIDATES.get(framework, []):
        layout = repo_path / candidate
        if layout.exists():
            return layout
    return None


def inject_tracking_script(repo_path: str, api_base_url: str) -> bool:
    """Inject the analytics tracking script into a project's layout file.

    Args:
        repo_path: Absolute path to the project's git repo.
        api_base_url: Base URL of the ContentFlow API
                      (e.g. "https://api.contentflow.com").

    Returns:
        True if the script was injected or already present.
        False if no layout file was found.
    """
    root = Path(repo_path)
    framework = _detect_framework(root)
    if not framework:
        return False

    layout = _find_layout(root, framework)
    if not layout:
        return False

    content = layout.read_text()

    # Already present — idempotent
    if _SCRIPT_MARKER in content:
        return True

    # Build the script tag
    url = api_base_url.rstrip("/")
    script_tag = f'<script defer src="{url}/a/s.js"></script>'

    # Insert before </head>
    if "</head>" in content:
        content = content.replace("</head>", f"  {script_tag}\n</head>")
    elif "</Head>" in content:
        # Next.js uses <Head> component sometimes
        content = content.replace("</Head>", f"  {script_tag}\n</Head>")
    else:
        # Fallback: append to end of file with a comment
        content += f"\n<!-- ContentFlow Analytics -->\n{script_tag}\n"

    layout.write_text(content)
    return True


def remove_tracking_script(repo_path: str) -> bool:
    """Remove the analytics tracking script from a project's layout file.

    Args:
        repo_path: Absolute path to the project's git repo.

    Returns:
        True if the script was removed or was already absent.
        False if no layout file was found.
    """
    root = Path(repo_path)
    framework = _detect_framework(root)
    if not framework:
        return False

    layout = _find_layout(root, framework)
    if not layout:
        return False

    content = layout.read_text()

    # Not present — nothing to do
    if _SCRIPT_MARKER not in content:
        return True

    # Remove the script tag line(s)
    lines = content.splitlines(keepends=True)
    cleaned = [line for line in lines if _SCRIPT_MARKER not in line]
    # Also remove standalone comment line if left behind
    cleaned = [line for line in cleaned if line.strip() != "<!-- ContentFlow Analytics -->"]

    layout.write_text("".join(cleaned))
    return True

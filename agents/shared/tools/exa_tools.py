"""
Exa AI CrewAI tools — shared across all agents.

Wrappers around the Exa SDK that expose semantic search, similar-page
finding, and content extraction as @tool functions for CrewAI agents.

Requires: an Exa secret bound in the runtime provider context.

Pattern adapted from agents/newsletter/tools/content_tools.py (ContentCollector),
generalized for use across all agents.
"""
import logging
from typing import Optional
from crewai.tools import tool
from api.services.runtime_provider_context import get_runtime_provider_secret

logger = logging.getLogger(__name__)

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False
    logger.warning("exa-py not installed. Run: pip install exa-py")


def _get_client() -> "Exa":
    if not EXA_AVAILABLE:
        raise ImportError("exa-py required. Run: pip install exa-py")
    api_key = get_runtime_provider_secret("exa")
    if not api_key:
        raise ValueError("Runtime provider secret required for provider 'exa'")
    return Exa(api_key)


@tool("Exa Semantic Search")
def exa_search(query: str, num_results: int = 5, days_back: Optional[int] = None) -> str:
    """
    Search the web using Exa's neural semantic search — finds pages by meaning,
    not just keywords. Use for researching topics, finding authoritative sources,
    or discovering relevant content that keyword search would miss.

    Args:
        query: Search query (can be a natural language question or topic)
        num_results: Number of results (default: 5)
        days_back: Restrict to content published in last N days (optional)

    Returns:
        Formatted list of results with title, URL, and excerpt
    """
    try:
        client = _get_client()
        kwargs = {
            "num_results": num_results,
            "use_autoprompt": True,
            "text": {"max_characters": 800},
        }
        if days_back:
            kwargs["start_published_date"] = f"{days_back}d"

        results = client.search_and_contents(query, **kwargs)
        if not results.results:
            return f"No results found for: {query}"

        output = []
        for r in results.results:
            excerpt = (r.text or "")[:600]
            output.append(
                f"### {r.title}\n"
                f"**URL:** {r.url}\n"
                f"**Published:** {r.published_date or 'unknown'}\n\n"
                f"{excerpt}"
            )
        return "\n\n---\n\n".join(output)
    except Exception as e:
        logger.error(f"Exa search failed for '{query}': {e}")
        return f"Error searching for '{query}': {str(e)}"


@tool("Exa Find Similar Pages")
def exa_find_similar(url: str, num_results: int = 5) -> str:
    """
    Find web pages similar to a given URL using Exa's semantic similarity.
    Use this to discover competitor content, find related articles,
    or identify what content ranks for similar topics.

    Args:
        url: Reference URL to find similar pages for
        num_results: Number of similar pages to find (default: 5)

    Returns:
        List of similar pages with title, URL, and excerpt
    """
    try:
        client = _get_client()
        results = client.find_similar_and_contents(
            url,
            num_results=num_results,
            text={"max_characters": 600}
        )
        if not results.results:
            return f"No similar pages found for: {url}"

        output = []
        for r in results.results:
            excerpt = (r.text or "")[:400]
            output.append(
                f"### {r.title}\n"
                f"**URL:** {r.url}\n\n"
                f"{excerpt}"
            )
        return "\n\n---\n\n".join(output)
    except Exception as e:
        logger.error(f"Exa find_similar failed for '{url}': {e}")
        return f"Error finding similar pages for '{url}': {str(e)}"


@tool("Exa Get Page Contents")
def exa_get_contents(urls: str) -> str:
    """
    Fetch the full text content of specific URLs using Exa.
    Use this when you already have URLs and need their actual content —
    faster and cleaner than scraping directly.

    Args:
        urls: Comma-separated list of URLs to fetch content for

    Returns:
        Full text content of each URL
    """
    try:
        client = _get_client()
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        if not url_list:
            return "No URLs provided"

        results = client.get_contents(url_list, text={"max_characters": 2000})
        if not results.results:
            return "No content returned"

        output = []
        for r in results.results:
            content = (r.text or "No content available")
            output.append(f"### {r.title}\n**URL:** {r.url}\n\n{content}")
        return "\n\n---\n\n".join(output)
    except Exception as e:
        logger.error(f"Exa get_contents failed: {e}")
        return f"Error fetching contents: {str(e)}"

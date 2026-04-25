"""
Firecrawl CrewAI tools — shared across all agents.

Wrappers around the Firecrawl SDK that expose scraping, crawling,
and web search as @tool functions for CrewAI agents.

Requires: a Firecrawl secret bound in the runtime provider context.
"""
import logging
from typing import Optional
from crewai.tools import tool
from api.services.runtime_provider_context import get_runtime_provider_secret

logger = logging.getLogger(__name__)

try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logger.warning("firecrawl-py not installed. Run: pip install firecrawl-py")


def _get_client() -> "FirecrawlApp":
    if not FIRECRAWL_AVAILABLE:
        raise ImportError("firecrawl-py required. Run: pip install firecrawl-py")
    api_key = get_runtime_provider_secret("firecrawl")
    if not api_key:
        raise ValueError("Runtime provider secret required for provider 'firecrawl'")
    return FirecrawlApp(api_key=api_key)


@tool("Scrape URL")
def scrape_url(url: str) -> str:
    """
    Scrape a single URL and return its content as clean markdown.
    Use this to read the full content of any webpage — competitor articles,
    product pages, documentation, or any other web content.

    Args:
        url: The URL to scrape

    Returns:
        Clean markdown content of the page
    """
    try:
        client = _get_client()
        result = client.scrape_url(url, formats=["markdown"])
        return result.get("markdown", result.get("content", "No content returned"))
    except Exception as e:
        logger.error(f"Firecrawl scrape_url failed for {url}: {e}")
        return f"Error scraping {url}: {str(e)}"


@tool("Crawl Site")
def crawl_site(url: str, max_pages: int = 10) -> str:
    """
    Crawl an entire website and return content from all pages as markdown.
    Use this to analyze a competitor's full content strategy or extract
    structured data from multiple pages of the same site.

    Args:
        url: The root URL to start crawling from
        max_pages: Maximum number of pages to crawl (default: 10)

    Returns:
        Combined markdown content from all crawled pages
    """
    try:
        client = _get_client()
        result = client.crawl_url(
            url,
            params={
                "limit": max_pages,
                "scrapeOptions": {"formats": ["markdown"]}
            }
        )
        pages = result.get("data", [])
        if not pages:
            return f"No pages found when crawling {url}"

        combined = []
        for page in pages:
            page_url = page.get("metadata", {}).get("url", "unknown")
            content = page.get("markdown", "")
            if content:
                combined.append(f"## {page_url}\n\n{content}")

        return "\n\n---\n\n".join(combined)
    except Exception as e:
        logger.error(f"Firecrawl crawl_site failed for {url}: {e}")
        return f"Error crawling {url}: {str(e)}"


@tool("Map Site Structure")
def map_site(url: str) -> str:
    """
    Map the URL structure of a website without downloading content.
    Use this to quickly understand a competitor's site architecture,
    identify content categories, or find specific pages.

    Args:
        url: The root URL to map

    Returns:
        List of URLs found on the site
    """
    try:
        client = _get_client()
        result = client.map_url(url)
        urls = result.get("links", [])
        if not urls:
            return f"No URLs found when mapping {url}"
        return "\n".join(urls)
    except Exception as e:
        logger.error(f"Firecrawl map_site failed for {url}: {e}")
        return f"Error mapping {url}: {str(e)}"


@tool("Search Web via Firecrawl")
def search_web(query: str, num_results: int = 5) -> str:
    """
    Search the web and return scraped content from top results.
    Use this to research topics, find competitor content,
    or gather current information about any subject.

    Args:
        query: Search query
        num_results: Number of results to return (default: 5)

    Returns:
        Markdown content from top search results
    """
    try:
        client = _get_client()
        result = client.search(query, params={"limit": num_results})
        items = result.get("data", [])
        if not items:
            return f"No results found for: {query}"

        combined = []
        for item in items:
            title = item.get("title", "No title")
            url = item.get("url", "")
            content = item.get("markdown", item.get("description", ""))
            combined.append(f"### {title}\n**URL:** {url}\n\n{content[:800]}")

        return "\n\n---\n\n".join(combined)
    except Exception as e:
        logger.error(f"Firecrawl search_web failed for '{query}': {e}")
        return f"Error searching for '{query}': {str(e)}"

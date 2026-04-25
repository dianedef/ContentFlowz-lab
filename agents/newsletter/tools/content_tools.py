"""
Content Tools - Content collection and research for newsletters.

Uses Exa AI for web research and content discovery.
"""

from typing import List, Dict, Any, Optional
from crewai.tools import tool
from api.services.runtime_provider_context import get_runtime_provider_secret

# Exa AI integration (already in requirements.txt)
try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False


class ContentCollector:
    """
    Collects and curates content for newsletters using Exa AI.
    """

    def __init__(self):
        api_key = get_runtime_provider_secret("exa")
        if not api_key:
            raise ValueError("Runtime provider secret required for provider 'exa'")

        if not EXA_AVAILABLE:
            raise ImportError("exa-py required. Run: pip install exa-py")

        self.exa = Exa(api_key)

    def find_trending_content(
        self,
        topics: List[str],
        days_back: int = 7,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find trending content on specified topics.

        Args:
            topics: List of topics to search
            days_back: How recent the content should be
            num_results: Number of results per topic

        Returns:
            List of content items with title, url, summary
        """
        all_results = []

        for topic in topics:
            results = self.exa.search_and_contents(
                query=topic,
                num_results=num_results,
                use_autoprompt=True,
                start_published_date=f"{days_back}d",
                text={"max_characters": 1000}
            )

            for result in results.results:
                all_results.append({
                    "topic": topic,
                    "title": result.title,
                    "url": result.url,
                    "summary": result.text[:500] if result.text else "",
                    "published_date": result.published_date
                })

        return all_results

    def find_similar_content(
        self,
        reference_url: str,
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find content similar to a reference article.

        Args:
            reference_url: URL of reference content
            num_results: Number of similar items to find

        Returns:
            List of similar content items
        """
        results = self.exa.find_similar_and_contents(
            url=reference_url,
            num_results=num_results,
            text={"max_characters": 500}
        )

        return [
            {
                "title": r.title,
                "url": r.url,
                "summary": r.text[:500] if r.text else ""
            }
            for r in results.results
        ]


@tool
def research_newsletter_topics(topics: str, days_back: int = 7) -> str:
    """
    Research trending content on topics for newsletter inclusion.

    Args:
        topics: Comma-separated list of topics to research
        days_back: How many days back to search

    Returns:
        Curated list of trending content
    """
    try:
        collector = ContentCollector()
        topic_list = [t.strip() for t in topics.split(",")]
        results = collector.find_trending_content(topic_list, days_back=days_back)

        if not results:
            return f"No recent content found for: {topics}"

        output = []
        current_topic = None

        for item in results:
            if item["topic"] != current_topic:
                current_topic = item["topic"]
                output.append(f"\n## {current_topic.upper()}\n")

            output.append(
                f"### {item['title']}\n"
                f"- URL: {item['url']}\n"
                f"- Published: {item.get('published_date', 'Unknown')}\n"
                f"- Summary: {item['summary'][:200]}...\n"
            )

        return "\n".join(output)

    except Exception as e:
        return f"Error researching topics: {str(e)}"


@tool
def find_related_articles(url: str) -> str:
    """
    Find articles similar to a reference URL for newsletter inspiration.

    Args:
        url: Reference article URL

    Returns:
        List of similar articles
    """
    try:
        collector = ContentCollector()
        results = collector.find_similar_content(url)

        if not results:
            return f"No similar content found for: {url}"

        output = ["## Similar Articles\n"]
        for item in results:
            output.append(
                f"### {item['title']}\n"
                f"- URL: {item['url']}\n"
                f"- Summary: {item['summary'][:200]}...\n"
            )

        return "\n".join(output)

    except Exception as e:
        return f"Error finding related content: {str(e)}"

"""
Seed Brain - CLI to seed initial project knowledge into the Mem0 brain.

Usage:
    python -m memory.scripts.seed_brain           # Seed all knowledge
    python -m memory.scripts.seed_brain --reset    # Clear and re-seed

Seeds:
- Brand voice guidelines
- Target audience definition
- Topic clusters
- Content inventory (existing published articles)
"""

import argparse
import sys


def seed_brand_voice(memory):
    """Seed brand voice and writing style guidelines."""
    print("\n📝 Seeding brand voice...")

    brand_facts = [
        (
            "Brand voice: informal French (tutoiement), technical but accessible. "
            "We explain complex AI and SEO concepts in simple terms. "
            "Tone is enthusiastic and educational, like a knowledgeable friend sharing discoveries."
        ),
        (
            "Writing style: use short paragraphs, concrete examples, and real numbers. "
            "Avoid corporate jargon. Prefer 'tu' over 'vous'. "
            "Mix technical accuracy with conversational warmth."
        ),
        (
            "Newsletter format: start with a hook or surprising fact. "
            "Each section should have a clear takeaway. "
            "End with a call-to-action that feels natural, not pushy. "
            "Use emojis sparingly for section markers."
        ),
        (
            "Content philosophy: build in public. Share real numbers, real failures, "
            "real lessons. Transparency builds trust. Show the journey, not just results."
        ),
    ]

    count = 0
    for fact in brand_facts:
        memory.store_brand_knowledge(fact)
        count += 1
        print(f"  ✓ Stored brand fact {count}/{len(brand_facts)}")
    return count


def seed_audience(memory):
    """Seed target audience definition."""
    print("\n👥 Seeding audience definition...")

    audience_facts = [
        (
            "Target audience: solo developers, indie hackers, and small teams "
            "building with AI. They are technically capable but time-constrained. "
            "They want practical solutions, not theoretical frameworks."
        ),
        (
            "Audience interests: AI agents (CrewAI, PydanticAI), SEO automation, "
            "content generation, build-in-public movement, developer tools, "
            "reducing costs with smart tooling choices."
        ),
        (
            "Audience pain points: too many AI tools to evaluate, expensive API costs, "
            "difficulty maintaining SEO consistency, time spent on repetitive content tasks, "
            "keeping up with rapidly changing AI landscape."
        ),
    ]

    count = 0
    for fact in audience_facts:
        memory.add(
            content=f"[audience] {fact}",
            metadata={"type": "audience"},
        )
        count += 1
        print(f"  ✓ Stored audience fact {count}/{len(audience_facts)}")
    return count


def seed_topic_clusters(memory):
    """Seed topic cluster definitions."""
    print("\n🎯 Seeding topic clusters...")

    clusters = [
        (
            "Topic cluster: AI Agents — CrewAI multi-agent systems, PydanticAI structured agents, "
            "agent memory (Mem0), tool use, orchestration patterns. "
            "Pillar: building production AI agents."
        ),
        (
            "Topic cluster: SEO Automation — topical mesh strategy, keyword research automation, "
            "content gap analysis, SERP monitoring, technical SEO audits. "
            "Pillar: automated SEO with AI agents."
        ),
        (
            "Topic cluster: Newsletter Automation — email curation with AI, IMAP integration, "
            "content research with Exa AI, automated writing and delivery. "
            "Pillar: AI-powered newsletter generation."
        ),
        (
            "Topic cluster: Build in Public — revenue tracking, infrastructure decisions, "
            "dependency optimization, deployment strategies, real cost analysis. "
            "Pillar: transparent journey to $10K MRR."
        ),
        (
            "Topic cluster: Developer Tools — OpenRouter for LLM routing, FastAPI for APIs, "
            "Blacksmith CI/CD, Flox environments, PM2 process management. "
            "Pillar: modern developer infrastructure."
        ),
    ]

    count = 0
    for cluster in clusters:
        memory.add(
            content=f"[topic_cluster] {cluster}",
            metadata={"type": "topic_cluster"},
        )
        count += 1
        print(f"  ✓ Stored cluster {count}/{len(clusters)}")
    return count


def seed_content_inventory(memory):
    """Seed existing published content for cross-referencing."""
    print("\n📚 Seeding content inventory...")

    articles = [
        {
            "title": "STORM Wikipedia-Quality Articles",
            "url": "website/src/content/blog/storm-wikipedia-quality-articles.md",
            "topics": ["AI agents", "STORM", "content generation"],
        },
        {
            "title": "Free SEO Tools vs SEMrush",
            "url": "website/src/content/blog/free-seo-tools-vs-semrush.md",
            "topics": ["SEO", "tools comparison", "cost optimization"],
        },
        {
            "title": "AI SEO Research Analyst",
            "url": "website/src/content/blog/ai-seo-research-analyst.md",
            "topics": ["AI agents", "SEO automation", "CrewAI"],
        },
        {
            "title": "Topical Mesh SEO Strategy",
            "url": "website/src/content/blog/topical-mesh-seo-strategy.md",
            "topics": ["SEO", "topical mesh", "content strategy"],
        },
        {
            "title": "API Key Security Management",
            "url": "website/src/content/blog/secure-api-key-management.md",
            "topics": ["security", "API keys", "developer tools"],
        },
        {
            "title": "Why We Chose Railway Over Heroku",
            "url": "website/src/content/blog/why-we-chose-railway-over-heroku.md",
            "topics": ["deployment", "build in public", "infrastructure"],
        },
        {
            "title": "Building AI Research Analyst Agent",
            "url": "website/src/content/blog/building-ai-research-analyst-agent.md",
            "topics": ["AI agents", "CrewAI", "build in public"],
        },
        {
            "title": "Cut Dependencies by 50%",
            "url": "website/src/content/blog/cut-dependencies-50-percent.md",
            "topics": ["optimization", "build in public", "developer tools"],
        },
        {
            "title": "Building Production FastAPI",
            "url": "website/src/content/blog/building-production-fastapi.md",
            "topics": ["FastAPI", "API architecture", "build in public"],
        },
        {
            "title": "SEO Content Results Tracking",
            "url": "website/src/content/blog/seo-content-results-tracking.md",
            "topics": ["SEO", "metrics", "build in public"],
        },
        {
            "title": "Journey to $10K MRR",
            "url": "website/src/content/blog/journey-to-10k-mrr.md",
            "topics": ["revenue", "build in public", "tracking"],
        },
    ]

    count = 0
    for article in articles:
        memory.store_content_inventory_item(
            title=article["title"],
            url=article["url"],
            topics=article["topics"],
        )
        count += 1
        print(f"  ✓ [{count}/{len(articles)}] {article['title']}")
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Seed the project brain with initial knowledge"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all memories before seeding",
    )
    args = parser.parse_args()

    try:
        from memory import get_memory_service
    except ImportError:
        print("Error: mem0ai is not installed. Run: pip install mem0ai")
        sys.exit(1)

    print("🧠 Content Flows — Brain Seeding")
    print("=" * 40)

    memory = get_memory_service()

    if args.reset:
        print("\n🗑️  Clearing existing memories...")
        memory.delete_all()
        print("  ✓ All memories cleared")

    total = 0
    total += seed_brand_voice(memory)
    total += seed_audience(memory)
    total += seed_topic_clusters(memory)
    total += seed_content_inventory(memory)

    print("\n" + "=" * 40)
    print(f"✅ Brain seeded with {total} memories")
    print("=" * 40)

    # Verify with a quick search
    print("\n🔍 Verification search: 'brand voice'")
    results = memory.search("brand voice", limit=3)
    for r in results:
        print(f"  → {r.memory[:80]}...")


if __name__ == "__main__":
    main()

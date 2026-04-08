"""
Image Robot Quick Start Example
Demonstrates how to use the Image Robot with articles
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from agents.images import ImagePipeline, create_image_pipeline
from agents.images.config.image_config import ImageConfig


def validate_configuration():
    """Validate that all required environment variables are set"""
    print("Validating configuration...")
    status = ImageConfig.validate()

    print(f"  Robolly configured: {status['robolly_configured']}")
    print(f"  Bunny.net configured: {status['bunny_configured']}")
    print(f"  Templates configured: {status['templates_configured']}")

    if status["warnings"]:
        print("\nWarnings:")
        for warning in status["warnings"]:
            print(f"  - {warning}")

    if not status["valid"]:
        print("\nErrors (must fix):")
        for issue in status["issues"]:
            print(f"  - {issue}")
        return False

    print("\nConfiguration valid!")
    return True


def example_single_article():
    """Example: Process a single article"""
    print("\n" + "="*60)
    print("Example: Process Single Article")
    print("="*60)

    # Create crew
    crew = create_image_pipeline()

    # Sample article content
    article = """---
title: "Introduction to Machine Learning"
slug: intro-machine-learning
date: 2026-01-18
---

# Introduction to Machine Learning

Machine learning is revolutionizing how we build intelligent systems.
This guide covers the fundamentals you need to get started.

## What is Machine Learning?

Machine learning is a subset of artificial intelligence that enables
computers to learn from data without being explicitly programmed.

## Types of Machine Learning

There are three main types of machine learning:
- Supervised Learning
- Unsupervised Learning
- Reinforcement Learning

## Getting Started

To start your machine learning journey, you'll need to understand
Python, linear algebra, and statistics fundamentals.

## Conclusion

Machine learning opens up incredible possibilities. Start learning today!
"""

    # Process with standard strategy
    result = crew.process(
        article_content=article,
        article_title="Introduction to Machine Learning",
        article_slug="intro-machine-learning",
        strategy_type="standard",  # hero + OG card
        style_guide="brand_primary"
    )

    print(f"\nResults:")
    print(f"  Strategy: {result.strategy.strategy_type}")
    print(f"  Total images planned: {result.total_images}")
    print(f"  Successful: {result.successful_images}")
    print(f"  Failed: {result.failed_images}")
    print(f"  Processing time: {result.processing_time_ms}ms")

    if result.og_image_url:
        print(f"\n  OG Image URL: {result.og_image_url}")

    if result.cdn_urls:
        print(f"\n  CDN URLs:")
        for url in result.cdn_urls[:5]:
            print(f"    - {url}")

    # Show updated markdown preview
    print(f"\n  Markdown preview (first 500 chars):")
    print("  " + "-"*50)
    print(result.markdown_with_images[:500])
    print("  ...")

    return result


def example_quick_hero_only():
    """Example: Quick processing with hero image only"""
    print("\n" + "="*60)
    print("Example: Quick Hero-Only Processing")
    print("="*60)

    crew = create_image_pipeline()

    article = """# Quick Update: New Feature Released

We just shipped a new feature that improves performance by 50%.
Check out the changelog for details.
"""

    result = crew.quick_process(
        article_content=article,
        article_title="Quick Update: New Feature Released",
        article_slug="quick-update-new-feature",
        hero_only=True
    )

    print(f"\nResults:")
    print(f"  Total images: {result.total_images}")
    print(f"  Processing time: {result.processing_time_ms}ms")

    return result


def example_rich_content():
    """Example: Rich content with many section images"""
    print("\n" + "="*60)
    print("Example: Rich Content with Section Images")
    print("="*60)

    crew = create_image_pipeline()

    # Long article with many sections
    article = """---
title: "Complete Guide to Python Web Development"
slug: python-web-development-guide
---

# Complete Guide to Python Web Development

Learn everything about building web applications with Python.

## Setting Up Your Environment

First, let's set up a proper Python development environment.
This includes installing Python, pip, and virtual environments.

## Choosing a Framework

Python offers several great web frameworks:
- Django for full-featured applications
- Flask for lightweight APIs
- FastAPI for modern async applications

## Database Integration

Most web apps need a database. We'll cover:
- PostgreSQL setup
- SQLAlchemy ORM
- Database migrations

## Authentication and Security

Security is critical. Learn about:
- User authentication
- JWT tokens
- HTTPS and CORS

## Deployment

Finally, deploy your application:
- Docker containers
- Cloud platforms
- CI/CD pipelines

## Conclusion

You now have a complete understanding of Python web development!
"""

    result = crew.process(
        article_content=article,
        article_title="Complete Guide to Python Web Development",
        article_slug="python-web-development-guide",
        strategy_type="hero+sections",  # Will generate section images
        generate_responsive=True
    )

    print(f"\nResults:")
    print(f"  Strategy: {result.strategy.strategy_type}")
    print(f"  Total images: {result.total_images}")
    print(f"  Successful: {result.successful_images}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    print(f"  Total CDN size: {result.total_cdn_size_kb}KB")

    return result


def example_integration_with_article_generator():
    """Example: Integration pattern with Article Generator"""
    print("\n" + "="*60)
    print("Example: Integration with Article Generator")
    print("="*60)

    # This shows the pattern for integrating with your Article Generator

    # Simulated article generator output
    class MockGeneratedArticle:
        def __init__(self):
            self.title = "AI Agents: The Future of Automation"
            self.slug = "ai-agents-future-automation"
            self.content = """# AI Agents: The Future of Automation

AI agents are autonomous systems that can reason and act.

## What Makes AI Agents Different?

Unlike traditional software, AI agents can adapt and learn.

## Building with CrewAI

CrewAI makes it easy to build multi-agent systems.

## Conclusion

The future is autonomous and intelligent.
"""
            self.topics = ["AI", "automation", "agents", "CrewAI"]

    # Article Generator produces content
    generated_article = MockGeneratedArticle()

    # Image Robot processes the article
    crew = create_image_pipeline()

    result = crew.process(
        article_content=generated_article.content,
        article_title=generated_article.title,
        article_slug=generated_article.slug,
        article_topics=generated_article.topics,
        strategy_type="standard"
    )

    # Article Generator uses the enriched content
    final_article = {
        "title": generated_article.title,
        "slug": generated_article.slug,
        "content": result.markdown_with_images,  # <-- Content with images
        "og_image": result.og_image_url,  # <-- For social sharing
        "images": result.cdn_urls,  # <-- All image URLs
        "image_metadata": result.image_metadata  # <-- Schema.org data
    }

    print(f"\nIntegration Result:")
    print(f"  Title: {final_article['title']}")
    print(f"  OG Image: {final_article['og_image']}")
    print(f"  Total images: {len(final_article['images'])}")

    return final_article


if __name__ == "__main__":
    # First validate config
    if not validate_configuration():
        print("\nPlease set the required environment variables:")
        print("  export ROBOLLY_API_KEY=your_api_key")
        print("  export BUNNY_STORAGE_API_KEY=your_storage_key")
        print("  export BUNNY_CDN_HOSTNAME=your-zone.b-cdn.net")
        print("\nSee .env.example for full configuration")
        sys.exit(1)

    # Run examples
    try:
        example_single_article()
        # example_quick_hero_only()
        # example_rich_content()
        # example_integration_with_article_generator()
    except Exception as e:
        print(f"\nError running example: {e}")
        import traceback
        traceback.print_exc()

"""Test fixtures and data for contentflow tests."""

import pytest
from typing import Dict, Any, List

@pytest.fixture
def sample_research_query():
    """Sample research query for testing."""
    return {
        "keyword": "python machine learning",
        "location": "United States",
        "language": "en",
        "depth": "comprehensive"
    }

@pytest.fixture
def sample_keyword_data():
    """Sample keyword analysis data."""
    return [
        {
            "keyword": "python machine learning",
            "volume": 12000,
            "difficulty": 65,
            "intent": "informational",
            "cpc": 2.50,
            "competition": "medium"
        },
        {
            "keyword": "machine learning python tutorial",
            "volume": 8500,
            "difficulty": 45,
            "intent": "informational",
            "cpc": 1.80,
            "competition": "low"
        }
    ]

@pytest.fixture
def sample_competitor_data():
    """Sample competitor analysis data."""
    return [
        {
            "url": "https://example1.com",
            "domain_authority": 75,
            "page_authority": 68,
            "backlinks": 1500,
            "keywords": 2500,
            "traffic": 50000
        },
        {
            "url": "https://example2.com", 
            "domain_authority": 82,
            "page_authority": 72,
            "backlinks": 2300,
            "keywords": 3200,
            "traffic": 75000
        }
    ]

@pytest.fixture
def sample_content_outline():
    """Sample content outline for testing."""
    return {
        "title": "Complete Guide to Python Machine Learning",
        "h1": "Python Machine Learning: From Beginner to Advanced",
        "sections": [
            {
                "h2": "Introduction to Python Machine Learning",
                "subsections": ["What is Machine Learning?", "Why Python for ML?"]
            },
            {
                "h2": "Setting Up Your Environment",
                "subsections": ["Installing Python", "Required Libraries", "IDE Setup"]
            }
        ],
        "word_count_target": 2500,
        "target_keywords": ["python machine learning", "ml python tutorial"],
        "content_type": "guide"
    }

@pytest.fixture
def sample_storm_response():
    """Sample STORM framework response."""
    return {
        "topic": "Python Machine Learning",
        "research_results": [
            {
                "source": "https://example.com/research1",
                "title": "Latest ML Research",
                "summary": "Recent advances in ML using Python",
                "relevance_score": 0.9
            }
        ],
        "insights": [
            "Python is the dominant language for ML",
            "TensorFlow and PyTorch are leading frameworks"
        ],
        "confidence_score": 0.85
    }

@pytest.fixture
def mock_search_results():
    """Mock search engine results."""
    return {
        "results": [
            {
                "position": 1,
                "title": "Python Machine Learning Tutorial",
                "url": "https://example.com/tutorial",
                "snippet": "Learn Python ML step by step",
                "cached": False
            },
            {
                "position": 2,
                "title": "Machine Learning with Python Examples",
                "url": "https://example.com/examples",
                "snippet": "Practical examples and code",
                "cached": False
            }
        ],
        "total_results": 1250000,
        "search_time": 0.45
    }

@pytest.fixture
def sample_mesh_cluster():
    """Sample topical mesh cluster data."""
    return {
        "cluster_id": "ml_basics",
        "name": "Machine Learning Basics",
        "centroid": ["python", "machine learning", "algorithms"],
        "keywords": [
            {"term": "python ml", "weight": 0.9},
            {"term": "machine learning basics", "weight": 0.8},
            {"term": "ml algorithms", "weight": 0.7}
        ],
        "authority_score": 0.75,
        "internal_links": 12,
        "content_gaps": ["neural networks", "deep learning"]
    }
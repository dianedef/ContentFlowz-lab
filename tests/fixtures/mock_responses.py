"""Test utilities and mock responses for contentflow tests."""

from unittest.mock import MagicMock
from typing import Dict, Any, List
import json

class MockSERPResponse:
    """Mock SERP API response."""
    
    @staticmethod
    def search_results(keyword: str = "test keyword") -> Dict[str, Any]:
        return {
            "search_information": {
                "query_displayed": keyword,
                "total_results": 1000000,
                "time_taken_displayed": 0.45
            },
            "organic_results": [
                {
                    "position": 1,
                    "title": f"Best {keyword.title()} Guide",
                    "link": "https://example1.com",
                    "snippet": f"Comprehensive guide to {keyword}",
                    "cached": False
                },
                {
                    "position": 2,
                    "title": f"{keyword.title()} Tutorial",
                    "link": "https://example2.com",
                    "snippet": f"Step-by-step {keyword} tutorial",
                    "cached": False
                }
            ],
            "related_questions": [
                {
                    "question": f"What is {keyword}?",
                    "snippet": f"Understanding {keyword} basics"
                }
            ]
        }

class MockLLMResponse:
    """Mock LLM response for testing."""
    
    @staticmethod
    def text_generation(prompt: str = "test prompt") -> str:
        responses = [
            "This is a comprehensive analysis of the topic.",
            "Based on the research, here are the key insights.",
            "The strategic approach should focus on these areas."
        ]
        return responses[hash(prompt) % len(responses)]

class MockAgentResponse:
    """Mock agent response for CrewAI testing."""
    
    @staticmethod
    def task_result(agent_role: str, task: str) -> Dict[str, Any]:
        return {
            "agent": agent_role,
            "task": task,
            "result": f"Analysis completed by {agent_role}",
            "confidence": 0.85,
            "data": {
                "insights": [f"Key insight from {agent_role}"],
                "recommendations": [f"Recommendation from {agent_role}"],
                "metadata": {"processing_time": 2.3}
            }
        }

class MockDatabase:
    """Mock database responses for testing."""
    
    def __init__(self):
        self.data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
    
    def exists(self, key: str) -> bool:
        return key in self.data

def create_mock_api_client() -> MagicMock:
    """Create a mock API client with common methods."""
    client = MagicMock()
    
    # Common API methods
    client.get.return_value = {"status": "success", "data": {}}
    client.post.return_value = {"status": "success", "data": {}}
    client.put.return_value = {"status": "success", "data": {}}
    client.delete.return_value = {"status": "success", "data": {}}
    
    return client

def create_mock_tool_response() -> Dict[str, Any]:
    """Create a mock tool response for CrewAI tools."""
    return {
        "success": True,
        "data": {
            "result": "Tool executed successfully",
            "metadata": {
                "execution_time": 0.5,
                "tokens_used": 150
            }
        }
    }

def create_error_response(error_type: str = "APIError", message: str = "Test error") -> Dict[str, Any]:
    """Create a standardized error response."""
    return {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "code": 500
        }
    }

# Sample data constants
SAMPLE_KEYWORDS = [
    "python machine learning",
    "machine learning tutorial",
    "python ml basics",
    "deep learning python",
    "tensorflow python"
]

SAMPLE_DOMAINS = [
    "https://example1.com",
    "https://example2.com",
    "https://example3.com"
]

SAMPLE_TOPICS = [
    "Machine Learning",
    "Python Programming", 
    "Data Science",
    "Artificial Intelligence",
    "Deep Learning"
]
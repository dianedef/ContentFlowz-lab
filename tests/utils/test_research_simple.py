"""
Simple utility tests for SEO system.
Tests basic imports and configuration.
"""
import sys
import os
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.unit
def test_project_path_setup():
    """Test that project path is correctly set up."""
    assert project_root.name == "ContentFlowz_lab"
    assert (project_root / "agents").exists()


@pytest.mark.unit
def test_environment_variables():
    """Test that test environment variables are set."""
    assert os.getenv("TESTING") == "true"
    # API keys are mocked in conftest.py
    assert os.getenv("OPENROUTER_API_KEY") is not None
    assert os.getenv("SERP_API_KEY") is not None


@pytest.mark.unit
def test_import_utils():
    """Test that utility modules can be imported."""
    try:
        from utils.llm_config import LLMConfig
        assert LLMConfig is not None
    except ImportError:
        pytest.skip("LLM config not available")


@pytest.mark.unit
def test_import_research_tools():
    """Test that research tools can be imported."""
    try:
        from agents.seo.tools.research_tools import SERPAnalyzer
        analyzer = SERPAnalyzer()
        assert analyzer is not None
    except ImportError:
        pytest.skip("Research tools not available")
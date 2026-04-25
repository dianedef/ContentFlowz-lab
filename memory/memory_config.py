"""
Memory Configuration - Settings for Mem0 backend (local ChromaDB or hosted).

Reads environment variables to determine backend and model configuration.
Local mode uses ChromaDB for vector storage and OpenAI-compatible LLM
for fact extraction. Hosted mode uses Mem0 Platform API.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base data directory for local storage
DATA_DIR = Path(__file__).parent.parent / "data" / "mem0"

# Backend selection: "local" (default) or "hosted"
MEM0_BACKEND = os.getenv("MEM0_BACKEND", "local")

# LLM for fact extraction (used by Mem0 internally)
MEM0_LLM_MODEL = os.getenv("MEM0_LLM_MODEL", "gpt-4o-mini")

# API keys
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "")


def get_mem0_config(*, runtime_openrouter_api_key: str | None = None) -> dict:
    """
    Build Mem0 configuration dict based on environment.

    Returns:
        Config dict suitable for passing to Memory(**config)
    """
    if MEM0_BACKEND == "hosted":
        return _get_hosted_config()
    return _get_local_config(runtime_openrouter_api_key=runtime_openrouter_api_key)


def _get_local_config(*, runtime_openrouter_api_key: str | None = None) -> dict:
    """Local ChromaDB + OpenAI embeddings configuration."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "contentflow_brain",
                "path": str(DATA_DIR),
            },
        },
    }

    # LLM for fact extraction via OpenRouter
    if runtime_openrouter_api_key:
        config["llm"] = {
            "provider": "openai",
            "config": {
                "model": MEM0_LLM_MODEL,
                "api_key": runtime_openrouter_api_key,
                "openai_base_url": "https://openrouter.ai/api/v1",
            },
        }
        # OpenRouter doesn't proxy embeddings — fall back to default
        # Mem0 will use its built-in embedder if no config is provided

    return config


def _get_hosted_config() -> dict:
    """Mem0 Platform hosted configuration."""
    if not MEM0_API_KEY:
        raise ValueError(
            "MEM0_API_KEY is required when MEM0_BACKEND=hosted. "
            "Get your key at https://app.mem0.ai"
        )
    return {
        "api_key": MEM0_API_KEY,
    }

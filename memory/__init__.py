"""
Memory module - Shared project brain powered by Mem0.

Provides persistent semantic memory for all robots (newsletter, SEO,
articles, scheduler). Uses local ChromaDB by default, with optional
Mem0 Platform hosting.

Usage:
    from memory import get_memory_service

    memory = get_memory_service()
    context = memory.load_context("brand voice guidelines")
    memory.store_generation("newsletter", "Weekly AI Digest", ["AI", "agents"])
"""

from memory.memory_service import (
    MemoryService,
    build_runtime_memory_service,
    get_memory_service,
)

__all__ = ["MemoryService", "get_memory_service", "build_runtime_memory_service"]

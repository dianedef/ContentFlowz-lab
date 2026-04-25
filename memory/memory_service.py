"""
Memory Service - Core wrapper around Mem0 for the project brain.

Provides semantic search, storage, and context loading for all robots.
Uses a singleton pattern (like IMAPNewsletterReader) to avoid
re-initializing the vector store on every call.
"""

from typing import List, Optional, Dict, Any

from memory.memory_config import get_mem0_config, MEM0_BACKEND
from memory.schemas.memory_schemas import (
    MemoryType,
    MemoryEntry,
    MemoryContext,
    GenerationRecord,
)

try:
    from mem0 import Memory, MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

# Default user/agent ID for scoping memories
DEFAULT_USER_ID = "contentflow"


def _scope_user_id(user_id: Optional[str] = None, project_id: Optional[str] = None) -> str:
    """Build a scoped user_id for Mem0 isolation.

    Memories are isolated per user+project so different projects
    don't pollute each other's content brain.
    """
    if user_id and project_id:
        return f"{user_id}:{project_id}"
    if user_id:
        return user_id
    return DEFAULT_USER_ID


class MemoryService:
    """
    Shared memory layer wrapping Mem0.

    All robots (newsletter, SEO, articles, scheduler) use this service
    to read/write the project brain.
    """

    def __init__(self, *, runtime_openrouter_api_key: str | None = None):
        if not MEM0_AVAILABLE:
            raise ImportError(
                "mem0ai is not installed. Run: pip install mem0ai"
            )

        config = get_mem0_config(runtime_openrouter_api_key=runtime_openrouter_api_key)
        if MEM0_BACKEND == "hosted":
            self._client = MemoryClient(api_key=config["api_key"])
            self._is_hosted = True
        else:
            self._client = Memory.from_config(config)
            self._is_hosted = False

    def search(
        self,
        query: str,
        limit: int = 10,
        agent_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        Semantic search across memories.

        Args:
            query: Natural language search query
            limit: Maximum results to return
            agent_id: Optional agent scope (e.g. "newsletter")

        Returns:
            List of matching MemoryEntry objects
        """
        kwargs = {"query": query, "limit": limit}
        if agent_id:
            kwargs["agent_id"] = agent_id
        else:
            kwargs["user_id"] = DEFAULT_USER_ID

        results = self._client.search(**kwargs)

        # Normalize response format (differs between local and hosted)
        entries = []
        raw_results = results.get("results", results) if isinstance(results, dict) else results
        for item in raw_results:
            if isinstance(item, dict):
                entries.append(MemoryEntry(
                    id=item.get("id"),
                    memory=item.get("memory", ""),
                    metadata=item.get("metadata", {}),
                    score=item.get("score"),
                    created_at=item.get("created_at"),
                ))
        return entries[:limit]

    def add(
        self,
        content: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a new memory.

        Args:
            content: Text content to memorize
            agent_id: Optional agent scope
            metadata: Optional metadata dict

        Returns:
            Mem0 response dict with memory ID(s)
        """
        kwargs: Dict[str, Any] = {"messages": [{"role": "user", "content": content}]}
        if agent_id:
            kwargs["agent_id"] = agent_id
        else:
            kwargs["user_id"] = DEFAULT_USER_ID
        if metadata:
            kwargs["metadata"] = metadata

        return self._client.add(**kwargs)

    def get_all(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """
        Retrieve all memories, optionally scoped to an agent.

        Args:
            agent_id: Optional agent scope
            limit: Maximum results

        Returns:
            List of MemoryEntry objects
        """
        kwargs = {}
        if agent_id:
            kwargs["agent_id"] = agent_id
        else:
            kwargs["user_id"] = DEFAULT_USER_ID

        results = self._client.get_all(**kwargs)

        entries = []
        raw_results = results.get("results", results) if isinstance(results, dict) else results
        for item in raw_results:
            if isinstance(item, dict):
                entries.append(MemoryEntry(
                    id=item.get("id"),
                    memory=item.get("memory", ""),
                    metadata=item.get("metadata", {}),
                    created_at=item.get("created_at"),
                ))
        return entries[:limit]

    def load_context(
        self,
        query: str,
        agent_id: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """
        Convenience: search and format as prompt-injectable string.

        Args:
            query: Search query
            agent_id: Optional agent scope
            limit: Maximum results

        Returns:
            Formatted string ready for prompt injection, or empty string
        """
        entries = self.search(query, limit=limit, agent_id=agent_id)
        context = MemoryContext(
            memories=entries,
            query=query,
            agent_id=agent_id,
        )
        return context.to_prompt_context()

    def store_generation(
        self,
        content_type: str,
        title: str,
        topics: Optional[List[str]] = None,
        summary: str = "",
    ) -> Dict[str, Any]:
        """
        Record a content generation run for future deduplication.

        Args:
            content_type: Type of content (newsletter, article, etc.)
            title: Title or subject line
            topics: Topics covered
            summary: Brief summary

        Returns:
            Mem0 response dict
        """
        record = GenerationRecord(
            content_type=content_type,
            title=title,
            topics=topics or [],
            summary=summary,
        )
        return self.add(
            content=record.to_memory_content(),
            agent_id=content_type,
            metadata=record.to_metadata(),
        )

    def store_generation_scoped(
        self,
        content_type: str,
        title: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        summary: str = "",
        seo_keyword: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a content generation with user+project scoping.

        This is the preferred method over store_generation() as it
        ensures memories are isolated per user and project.
        """
        record = GenerationRecord(
            content_type=content_type,
            title=title,
            topics=topics or [],
            summary=summary,
        )
        metadata = record.to_metadata()
        if seo_keyword:
            metadata["seo_keyword"] = seo_keyword
        if source:
            metadata["source"] = source

        scoped_uid = _scope_user_id(user_id, project_id)
        kwargs: Dict[str, Any] = {
            "messages": [{"role": "user", "content": record.to_memory_content()}],
            "user_id": scoped_uid,
            "metadata": metadata,
        }
        return self._client.add(**kwargs)

    def load_project_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 15,
    ) -> str:
        """Load project memory context for prompt injection.

        Returns a formatted string describing what content already exists
        in this project, so AI agents can avoid generating duplicates.

        Typical usage in a generation pipeline:
            context = mem.load_project_context("content marketing SEO", user_id, project_id)
            prompt += f"\\n\\nExisting project content:\\n{context}\\nDo NOT repeat these topics."
        """
        scoped_uid = _scope_user_id(user_id, project_id)

        kwargs = {"query": query, "limit": limit, "user_id": scoped_uid}
        results = self._client.search(**kwargs)

        entries = []
        raw_results = results.get("results", results) if isinstance(results, dict) else results
        for item in raw_results:
            if isinstance(item, dict):
                entries.append(MemoryEntry(
                    id=item.get("id"),
                    memory=item.get("memory", ""),
                    metadata=item.get("metadata", {}),
                    score=item.get("score"),
                ))

        if not entries:
            return ""

        lines = [f"=== Project Content History ({len(entries)} items) ==="]
        for i, entry in enumerate(entries[:limit], 1):
            mem_type = entry.metadata.get("type", "general")
            lines.append(f"[{i}] ({mem_type}) {entry.memory}")
        lines.append("=== End History — do NOT regenerate these topics ===")
        return "\n".join(lines)

    def store_brand_knowledge(self, knowledge: str) -> Dict[str, Any]:
        """
        Seed brand facts into the project brain.

        Args:
            knowledge: Brand knowledge text to store

        Returns:
            Mem0 response dict
        """
        return self.add(
            content=f"[{MemoryType.BRAND_VOICE.value}] {knowledge}",
            metadata={"type": MemoryType.BRAND_VOICE.value},
        )

    def store_content_inventory_item(
        self,
        title: str,
        url: str,
        topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Seed an existing content item into the project brain.

        Args:
            title: Content title
            url: Published URL
            topics: Related topics

        Returns:
            Mem0 response dict
        """
        topics_str = ", ".join(topics) if topics else "general"
        content = (
            f"[{MemoryType.CONTENT_INVENTORY.value}] "
            f'Published article: "{title}" at {url}. Topics: {topics_str}'
        )
        return self.add(
            content=content,
            metadata={
                "type": MemoryType.CONTENT_INVENTORY.value,
                "title": title,
                "url": url,
                "topics": topics or [],
            },
        )

    def delete_all(self, agent_id: Optional[str] = None) -> None:
        """
        Delete all memories. Used by seed_brain --reset.

        Args:
            agent_id: If provided, only delete memories for this agent
        """
        memories = self.get_all(agent_id=agent_id, limit=1000)
        for mem in memories:
            if mem.id:
                self._client.delete(mem.id)


# Singleton instance
_service_instance: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get or create the singleton MemoryService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MemoryService()
    return _service_instance


def build_runtime_memory_service(*, openrouter_api_key: str | None) -> MemoryService:
    """Create a non-singleton runtime-scoped memory service."""
    return MemoryService(runtime_openrouter_api_key=openrouter_api_key)

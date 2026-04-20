"""
Project Store - Database layer for project management

Provides CRUD operations for projects using Turso DB.
Follows the pattern established in content_config.py.
"""

import os
import json
import uuid
from typing import Optional, List
from datetime import datetime

from utils.libsql_async import create_client
from typing import Optional, List

from api.models.project import (
    Project,
    ProjectSettings,
    TechStackDetection,
    ContentDirectoryConfig,
    ProjectConfigOverrides,
    OnboardingStatus,
)


class ProjectStore:
    """
    Database store for project management.

    Uses the existing Project table from chatbot migrations.
    Stores tech_stack, content_directory, config_overrides in the 'settings' JSON field.
    """

    def __init__(self):
        """Initialize database client from environment variables."""
        self.db_client = None
        if os.getenv("TURSO_DATABASE_URL") and os.getenv("TURSO_AUTH_TOKEN"):
            self.db_client = create_client(
                url=os.getenv("TURSO_DATABASE_URL"),
                auth_token=os.getenv("TURSO_AUTH_TOKEN")
            )

    def _ensure_connected(self):
        """Ensure database client is available."""
        if not self.db_client:
            raise RuntimeError(
                "Database not configured. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN."
            )

    async def ensure_table(self) -> None:
        """Create the Project table if it does not exist."""
        self._ensure_connected()

        await self.db_client.execute(
            """
            CREATE TABLE IF NOT EXISTS Project (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'github',
                description TEXT,
                isDefault INTEGER NOT NULL DEFAULT 0,
                settings TEXT,
                lastAnalyzedAt INTEGER,
                createdAt INTEGER NOT NULL
            )
            """
        )

        await self.db_client.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_userId
            ON Project(userId)
            """
        )

        await self.db_client.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_userId_isDefault
            ON Project(userId, isDefault)
            """
        )

        await self.db_client.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_project_userId_url
            ON Project(userId, url)
            """
        )

    def _row_to_project(self, row: tuple) -> Project:
        """Convert database row to Project model."""
        # Row columns: id, userId, name, url, type, description, isDefault, settings, lastAnalyzedAt, createdAt
        settings_json = row[7]
        settings = None
        if settings_json:
            try:
                settings_dict = json.loads(settings_json)
                settings = ProjectSettings(**settings_dict)
            except (json.JSONDecodeError, TypeError):
                settings = None

        return Project(
            id=row[0],
            user_id=row[1],
            name=row[2],
            url=row[3],
            type=row[4],
            description=row[5],
            is_default=bool(row[6]),
            settings=settings,
            last_analyzed_at=datetime.fromtimestamp(row[8]) if row[8] else None,
            created_at=datetime.fromtimestamp(row[9])
        )

    async def create(
        self,
        user_id: str,
        name: str,
        url: str,
        description: Optional[str] = None,
        project_type: str = "github"
    ) -> Project:
        """
        Create a new project.

        Args:
            user_id: Owner user ID
            name: Project name
            url: GitHub repository URL
            description: Optional description
            project_type: Repository type (default: github)

        Returns:
            Created Project
        """
        self._ensure_connected()

        project_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())

        # Initial settings with pending status
        initial_settings = ProjectSettings(
            onboarding_status=OnboardingStatus.PENDING
        )
        settings_json = initial_settings.model_dump_json()

        await self.db_client.execute(
            """
            INSERT INTO Project (id, userId, name, url, type, description, isDefault, settings, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [project_id, user_id, name, url, project_type, description, False, settings_json, now]
        )

        return Project(
            id=project_id,
            user_id=user_id,
            name=name,
            url=url,
            type=project_type,
            description=description,
            is_default=False,
            settings=initial_settings,
            last_analyzed_at=None,
            created_at=datetime.fromtimestamp(now)
        )

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project if found, None otherwise
        """
        self._ensure_connected()

        rs = await self.db_client.execute(
            """
            SELECT id, userId, name, url, type, description, isDefault, settings, lastAnalyzedAt, createdAt
            FROM Project
            WHERE id = ?
            """,
            [project_id]
        )

        if rs.rows:
            return self._row_to_project(rs.rows[0])
        return None

    async def get_by_user(self, user_id: str) -> List[Project]:
        """
        Get all projects for a user.

        Args:
            user_id: User ID

        Returns:
            List of projects
        """
        self._ensure_connected()

        rs = await self.db_client.execute(
            """
            SELECT id, userId, name, url, type, description, isDefault, settings, lastAnalyzedAt, createdAt
            FROM Project
            WHERE userId = ?
            ORDER BY createdAt DESC
            """,
            [user_id]
        )

        return [self._row_to_project(row) for row in rs.rows]

    async def get_default_project(self, user_id: str) -> Optional[Project]:
        """
        Get the user's default project.

        Args:
            user_id: User ID

        Returns:
            Default project if set, None otherwise
        """
        self._ensure_connected()

        rs = await self.db_client.execute(
            """
            SELECT id, userId, name, url, type, description, isDefault, settings, lastAnalyzedAt, createdAt
            FROM Project
            WHERE userId = ? AND isDefault = 1
            LIMIT 1
            """,
            [user_id]
        )

        if rs.rows:
            return self._row_to_project(rs.rows[0])
        return None

    async def update_settings(
        self,
        project_id: str,
        settings: ProjectSettings
    ) -> Optional[Project]:
        """
        Update project settings.

        Args:
            project_id: Project ID
            settings: New settings

        Returns:
            Updated project
        """
        self._ensure_connected()

        settings_json = settings.model_dump_json()

        await self.db_client.execute(
            """
            UPDATE Project
            SET settings = ?
            WHERE id = ?
            """,
            [settings_json, project_id]
        )

        return await self.get_by_id(project_id)

    async def update_onboarding_status(
        self,
        project_id: str,
        status: OnboardingStatus,
        tech_stack: Optional[TechStackDetection] = None,
        content_directories: Optional[List[ContentDirectoryConfig]] = None,
        local_repo_path: Optional[str] = None
    ) -> Optional[Project]:
        """
        Update onboarding status and optionally detection results.

        Args:
            project_id: Project ID
            status: New onboarding status
            tech_stack: Detected tech stack
            content_directories: All detected/configured content directories
            local_repo_path: Path to cloned repository

        Returns:
            Updated project
        """
        project = await self.get_by_id(project_id)
        if not project:
            return None

        settings = project.settings or ProjectSettings()
        settings.onboarding_status = status

        if tech_stack:
            settings.tech_stack = tech_stack
        if content_directories is not None:
            settings.content_directories = content_directories
        if local_repo_path:
            settings.local_repo_path = local_repo_path

        return await self.update_settings(project_id, settings)

    async def update_last_analyzed(self, project_id: str) -> Optional[Project]:
        """
        Update the last analyzed timestamp.

        Args:
            project_id: Project ID

        Returns:
            Updated project
        """
        self._ensure_connected()

        now = int(datetime.now().timestamp())

        await self.db_client.execute(
            """
            UPDATE Project
            SET lastAnalyzedAt = ?
            WHERE id = ?
            """,
            [now, project_id]
        )

        return await self.get_by_id(project_id)

    async def set_default(self, user_id: str, project_id: str) -> Optional[Project]:
        """
        Set a project as the user's default.

        Args:
            user_id: User ID
            project_id: Project ID to set as default

        Returns:
            Updated project
        """
        self._ensure_connected()

        # First, unset all defaults for this user
        await self.db_client.execute(
            """
            UPDATE Project
            SET isDefault = 0
            WHERE userId = ?
            """,
            [user_id]
        )

        # Then set the new default
        await self.db_client.execute(
            """
            UPDATE Project
            SET isDefault = 1
            WHERE id = ? AND userId = ?
            """,
            [project_id, user_id]
        )

        return await self.get_by_id(project_id)

    async def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
        content_directories: Optional[List[ContentDirectoryConfig]] = None,
        config_overrides: Optional[ProjectConfigOverrides] = None,
        analytics_enabled: Optional[bool] = None,
    ) -> Optional[Project]:
        """
        Update project details.

        Args:
            project_id: Project ID
            name: New name
            description: New description
            content_directories: New content directories config
            config_overrides: New config overrides
            analytics_enabled: Enable/disable cookie-free analytics

        Returns:
            Updated project
        """
        self._ensure_connected()

        project = await self.get_by_id(project_id)
        if not project:
            return None

        # Update basic fields if provided
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if url is not None:
            updates.append("url = ?")
            params.append(url)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if updates:
            params.append(project_id)
            await self.db_client.execute(
                f"UPDATE Project SET {', '.join(updates)} WHERE id = ?",
                params
            )

        # Update settings if needed
        if content_directories is not None or config_overrides or analytics_enabled is not None:
            settings = project.settings or ProjectSettings()
            if content_directories is not None:
                settings.content_directories = content_directories
            if config_overrides:
                settings.config_overrides = config_overrides
            if analytics_enabled is not None:
                settings.analytics_enabled = analytics_enabled
            await self.update_settings(project_id, settings)

        return await self.get_by_id(project_id)

    async def delete(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID

        Returns:
            True if deleted
        """
        self._ensure_connected()

        await self.db_client.execute(
            "DELETE FROM Project WHERE id = ?",
            [project_id]
        )

        return True

    async def get_by_url(self, user_id: str, url: str) -> Optional[Project]:
        """
        Get project by GitHub URL for a user.

        Args:
            user_id: User ID
            url: GitHub repository URL

        Returns:
            Project if found
        """
        self._ensure_connected()

        rs = await self.db_client.execute(
            """
            SELECT id, userId, name, url, type, description, isDefault, settings, lastAnalyzedAt, createdAt
            FROM Project
            WHERE userId = ? AND url = ?
            LIMIT 1
            """,
            [user_id, url]
        )

        if rs.rows:
            return self._row_to_project(rs.rows[0])
        return None


# Global store instance
project_store = ProjectStore()

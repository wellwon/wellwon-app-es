# =============================================================================
# File: app/declarant/form_templates_service.py
# Description: Service for managing form templates (CRUD operations)
# =============================================================================

from __future__ import annotations

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

import asyncpg

log = logging.getLogger("wellwon.declarant.form_templates_service")


# =============================================================================
# Data Models
# =============================================================================

class FormTemplateData:
    """Form template data structure"""

    def __init__(
        self,
        id: Optional[str] = None,
        document_mode_id: str = "",
        gf_code: str = "",
        type_name: str = "",
        name: str = "",
        description: Optional[str] = None,
        version: int = 1,
        version_label: Optional[str] = None,
        is_draft: bool = True,
        is_published: bool = False,
        published_at: Optional[datetime] = None,
        status: str = "draft",
        sections: List[Dict[str, Any]] = None,
        default_values: Dict[str, Any] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
        updated_by: Optional[str] = None,
        usage_count: int = 0,
        last_used_at: Optional[datetime] = None,
    ):
        self.id = id
        self.document_mode_id = document_mode_id
        self.gf_code = gf_code
        self.type_name = type_name
        self.name = name
        self.description = description
        self.version = version
        self.version_label = version_label
        self.is_draft = is_draft
        self.is_published = is_published
        self.published_at = published_at
        self.status = status
        self.sections = sections or []
        self.default_values = default_values or {}
        self.created_at = created_at
        self.updated_at = updated_at
        self.created_by = created_by
        self.updated_by = updated_by
        self.usage_count = usage_count
        self.last_used_at = last_used_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_mode_id": self.document_mode_id,
            "gf_code": self.gf_code,
            "type_name": self.type_name,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "version_label": self.version_label,
            "is_draft": self.is_draft,
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "status": self.status,
            "sections": self.sections,
            "default_values": self.default_values,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "FormTemplateData":
        return cls(
            id=str(row["id"]),
            document_mode_id=row["document_mode_id"],
            gf_code=row["gf_code"],
            type_name=row["type_name"],
            name=row["name"],
            description=row.get("description"),
            version=row["version"],
            version_label=row.get("version_label"),
            is_draft=row["is_draft"],
            is_published=row["is_published"],
            published_at=row.get("published_at"),
            status=row["status"],
            sections=row["sections"] if isinstance(row["sections"], list) else json.loads(row["sections"] or "[]"),
            default_values=row["default_values"] if isinstance(row["default_values"], dict) else json.loads(row["default_values"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=str(row["created_by"]) if row.get("created_by") else None,
            updated_by=str(row["updated_by"]) if row.get("updated_by") else None,
            usage_count=row.get("usage_count", 0),
            last_used_at=row.get("last_used_at"),
        )


class FormTemplateVersionData:
    """Form template version data structure"""

    def __init__(
        self,
        id: Optional[str] = None,
        template_id: str = "",
        version: int = 1,
        version_label: Optional[str] = None,
        sections_snapshot: List[Dict[str, Any]] = None,
        default_values_snapshot: Dict[str, Any] = None,
        change_description: Optional[str] = None,
        created_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ):
        self.id = id
        self.template_id = template_id
        self.version = version
        self.version_label = version_label
        self.sections_snapshot = sections_snapshot or []
        self.default_values_snapshot = default_values_snapshot or {}
        self.change_description = change_description
        self.created_at = created_at
        self.created_by = created_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "version": self.version,
            "version_label": self.version_label,
            "sections_snapshot": self.sections_snapshot,
            "default_values_snapshot": self.default_values_snapshot,
            "change_description": self.change_description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "FormTemplateVersionData":
        return cls(
            id=str(row["id"]),
            template_id=str(row["template_id"]),
            version=row["version"],
            version_label=row.get("version_label"),
            sections_snapshot=row["sections_snapshot"] if isinstance(row["sections_snapshot"], list) else json.loads(row["sections_snapshot"] or "[]"),
            default_values_snapshot=row["default_values_snapshot"] if isinstance(row["default_values_snapshot"], dict) else json.loads(row["default_values_snapshot"] or "{}"),
            change_description=row.get("change_description"),
            created_at=row["created_at"],
            created_by=str(row["created_by"]) if row.get("created_by") else None,
        )


# =============================================================================
# Form Templates Service
# =============================================================================

class FormTemplatesService:
    """Service for managing form templates"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    async def get_templates(
        self,
        page: int = 1,
        page_size: int = 20,
        document_mode_id: Optional[str] = None,
        search: Optional[str] = None,
        is_published: Optional[bool] = None,
    ) -> tuple[List[FormTemplateData], int]:
        """Get paginated list of templates"""
        offset = (page - 1) * page_size

        # Build WHERE clause
        conditions = []
        params = []
        param_idx = 1

        if document_mode_id:
            conditions.append(f"document_mode_id = ${param_idx}")
            params.append(document_mode_id)
            param_idx += 1

        if search:
            conditions.append(f"(name ILIKE ${param_idx} OR description ILIKE ${param_idx})")
            params.append(f"%{search}%")
            param_idx += 1

        if is_published is not None:
            conditions.append(f"is_published = ${param_idx}")
            params.append(is_published)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Count total
        count_query = f"SELECT COUNT(*) FROM dc_form_templates WHERE {where_clause}"
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)

            # Get items
            query = f"""
                SELECT * FROM dc_form_templates
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            rows = await conn.fetch(query, *params, page_size, offset)

        templates = [FormTemplateData.from_row(row) for row in rows]
        return templates, total

    async def get_template_by_id(self, template_id: str) -> Optional[FormTemplateData]:
        """Get template by ID"""
        query = "SELECT * FROM dc_form_templates WHERE id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, UUID(template_id))

        if row:
            return FormTemplateData.from_row(row)
        return None

    async def get_published_template(self, document_mode_id: str) -> Optional[FormTemplateData]:
        """Get published template for document mode"""
        query = """
            SELECT * FROM dc_form_templates
            WHERE document_mode_id = $1 AND is_published = TRUE
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, document_mode_id)

        if row:
            return FormTemplateData.from_row(row)
        return None

    async def create_template(
        self,
        document_mode_id: str,
        gf_code: str,
        type_name: str,
        name: str,
        sections: List[Dict[str, Any]],
        description: Optional[str] = None,
        default_values: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> FormTemplateData:
        """Create new template"""
        query = """
            INSERT INTO dc_form_templates (
                document_mode_id, gf_code, type_name, name, description,
                sections, default_values, created_by, updated_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                document_mode_id,
                gf_code,
                type_name,
                name,
                description,
                json.dumps(sections),
                json.dumps(default_values or {}),
                UUID(user_id) if user_id else None,
            )

        log.info(f"Created form template: {name} (document_mode_id={document_mode_id})")
        return FormTemplateData.from_row(row)

    async def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sections: Optional[List[Dict[str, Any]]] = None,
        default_values: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Optional[FormTemplateData]:
        """Update template"""
        # Build SET clause
        updates = []
        params = []
        param_idx = 1

        if name is not None:
            updates.append(f"name = ${param_idx}")
            params.append(name)
            param_idx += 1

        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1

        if sections is not None:
            updates.append(f"sections = ${param_idx}")
            params.append(json.dumps(sections))
            param_idx += 1

        if default_values is not None:
            updates.append(f"default_values = ${param_idx}")
            params.append(json.dumps(default_values))
            param_idx += 1

        if user_id:
            updates.append(f"updated_by = ${param_idx}")
            params.append(UUID(user_id))
            param_idx += 1

        updates.append("is_draft = TRUE")

        if not updates:
            return await self.get_template_by_id(template_id)

        query = f"""
            UPDATE dc_form_templates
            SET {", ".join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """
        params.append(UUID(template_id))

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if row:
            log.info(f"Updated form template: {template_id}")
            return FormTemplateData.from_row(row)
        return None

    async def delete_template(self, template_id: str) -> bool:
        """Delete template"""
        query = "DELETE FROM dc_form_templates WHERE id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, UUID(template_id))

        deleted = result == "DELETE 1"
        if deleted:
            log.info(f"Deleted form template: {template_id}")
        return deleted

    async def duplicate_template(
        self,
        template_id: str,
        new_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[FormTemplateData]:
        """Duplicate template"""
        original = await self.get_template_by_id(template_id)
        if not original:
            return None

        return await self.create_template(
            document_mode_id=original.document_mode_id,
            gf_code=original.gf_code,
            type_name=original.type_name,
            name=new_name or f"{original.name} (копия)",
            description=original.description,
            sections=original.sections,
            default_values=original.default_values,
            user_id=user_id,
        )

    # -------------------------------------------------------------------------
    # Publishing
    # -------------------------------------------------------------------------

    async def publish_template(
        self,
        template_id: str,
        version_label: Optional[str] = None,
        change_description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[FormTemplateData]:
        """Publish template (creates new version)"""
        query = "SELECT dc_create_template_version($1, $2, $3, $4)"
        async with self.pool.acquire() as conn:
            new_version = await conn.fetchval(
                query,
                UUID(template_id),
                version_label,
                change_description,
                UUID(user_id) if user_id else None,
            )

        if new_version:
            log.info(f"Published form template: {template_id} (version={new_version})")
            return await self.get_template_by_id(template_id)
        return None

    async def unpublish_template(
        self,
        template_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[FormTemplateData]:
        """Unpublish template"""
        query = """
            UPDATE dc_form_templates
            SET is_published = FALSE, status = 'draft', updated_by = $2
            WHERE id = $1
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, UUID(template_id), UUID(user_id) if user_id else None)

        if row:
            log.info(f"Unpublished form template: {template_id}")
            return FormTemplateData.from_row(row)
        return None

    # -------------------------------------------------------------------------
    # Versions
    # -------------------------------------------------------------------------

    async def get_template_versions(self, template_id: str) -> List[FormTemplateVersionData]:
        """Get all versions of template"""
        query = """
            SELECT * FROM dc_form_template_versions
            WHERE template_id = $1
            ORDER BY version DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, UUID(template_id))

        return [FormTemplateVersionData.from_row(row) for row in rows]

    async def get_template_version(
        self,
        template_id: str,
        version: int,
    ) -> Optional[FormTemplateVersionData]:
        """Get specific version"""
        query = """
            SELECT * FROM dc_form_template_versions
            WHERE template_id = $1 AND version = $2
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, UUID(template_id), version)

        if row:
            return FormTemplateVersionData.from_row(row)
        return None

    async def restore_template_version(
        self,
        template_id: str,
        version: int,
        user_id: Optional[str] = None,
    ) -> Optional[FormTemplateData]:
        """Restore template to specific version"""
        query = "SELECT dc_restore_template_version($1, $2, $3)"
        async with self.pool.acquire() as conn:
            success = await conn.fetchval(
                query,
                UUID(template_id),
                version,
                UUID(user_id) if user_id else None,
            )

        if success:
            log.info(f"Restored form template: {template_id} to version {version}")
            return await self.get_template_by_id(template_id)
        return None

    # -------------------------------------------------------------------------
    # Drafts
    # -------------------------------------------------------------------------

    async def get_user_draft(
        self,
        template_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get user's draft for template"""
        query = """
            SELECT draft_data FROM dc_form_template_drafts
            WHERE template_id = $1 AND user_id = $2
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, UUID(template_id), UUID(user_id))

        if row:
            data = row["draft_data"]
            return data if isinstance(data, dict) else json.loads(data or "{}")
        return None

    async def save_user_draft(
        self,
        template_id: str,
        user_id: str,
        draft_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save user's draft"""
        query = """
            INSERT INTO dc_form_template_drafts (template_id, user_id, draft_data)
            VALUES ($1, $2, $3)
            ON CONFLICT (template_id, user_id)
            DO UPDATE SET draft_data = $3, updated_at = NOW()
            RETURNING draft_data
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                UUID(template_id),
                UUID(user_id),
                json.dumps(draft_data),
            )

        data = row["draft_data"]
        return data if isinstance(data, dict) else json.loads(data or "{}")

    async def delete_user_draft(self, template_id: str, user_id: str) -> bool:
        """Delete user's draft"""
        query = "DELETE FROM dc_form_template_drafts WHERE template_id = $1 AND user_id = $2"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, UUID(template_id), UUID(user_id))

        return result == "DELETE 1"

    async def get_all_user_drafts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all drafts for user"""
        query = """
            SELECT d.*, t.name as template_name, t.document_mode_id
            FROM dc_form_template_drafts d
            LEFT JOIN dc_form_templates t ON d.template_id = t.id
            WHERE d.user_id = $1
            ORDER BY d.updated_at DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, UUID(user_id))

        return [
            {
                "id": str(row["id"]),
                "template_id": str(row["template_id"]) if row.get("template_id") else None,
                "document_mode_id": row.get("document_mode_id"),
                "template_name": row.get("template_name"),
                "draft_data": row["draft_data"] if isinstance(row["draft_data"], dict) else json.loads(row["draft_data"] or "{}"),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }
            for row in rows
        ]

    # -------------------------------------------------------------------------
    # Usage Tracking
    # -------------------------------------------------------------------------

    async def increment_usage(self, template_id: str) -> None:
        """Increment template usage count"""
        query = "SELECT dc_increment_template_usage($1)"
        async with self.pool.acquire() as conn:
            await conn.execute(query, UUID(template_id))

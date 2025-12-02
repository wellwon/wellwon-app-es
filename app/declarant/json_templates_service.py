# =============================================================================
# File: app/declarant/json_templates_service.py
# Description: Service for managing JSON templates from Kontur API
# =============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass

from app.infra.persistence import pg_client
from app.declarant.kontur_client import get_kontur_client, KonturClientError

log = logging.getLogger("wellwon.declarant.json_templates_service")


@dataclass
class JsonTemplate:
    """JSON template entity"""
    id: str
    gf_code: str
    document_mode_id: str
    type_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    sections_count: int = 0  # Количество настроенных секций в форме


@dataclass
class SyncResult:
    """Result of sync operation"""
    total_fetched: int
    inserted: int
    updated: int
    skipped: int
    errors: int
    sync_time: datetime


class JsonTemplatesService:
    """Service for managing JSON templates"""

    TABLE_NAME = "dc_json_templates"
    REFERENCE_NAME = "Шаблоны JSON форм"
    REFERENCE_DESCRIPTION = "Шаблоны форм документов из Kontur API (GET /common/v1/jsonTemplates)"

    SECTIONS_TABLE = "dc_form_sections"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[JsonTemplate]:
        """
        Get all JSON templates from database with sections count

        Args:
            include_inactive: Include inactive templates

        Returns:
            List of JsonTemplate objects
        """
        # Подзапрос для подсчёта секций через dc_form_definitions
        query = f"""
            SELECT t.id, t.gf_code, t.document_mode_id, t.type_name,
                   t.is_active, t.created_at, t.updated_at,
                   COALESCE(s.sections_count, 0) as sections_count
            FROM {cls.TABLE_NAME} t
            LEFT JOIN (
                SELECT fd.document_mode_id, COUNT(fs.id) as sections_count
                FROM dc_form_definitions fd
                JOIN {cls.SECTIONS_TABLE} fs ON fs.form_definition_id = fd.id
                GROUP BY fd.document_mode_id
            ) s ON t.document_mode_id = s.document_mode_id
        """
        if not include_inactive:
            query += " WHERE t.is_active = TRUE"
        query += " ORDER BY t.gf_code, t.document_mode_id, t.type_name"

        rows = await pg_client.fetch(query)

        return [
            JsonTemplate(
                id=str(row["id"]),
                gf_code=row["gf_code"],
                document_mode_id=row["document_mode_id"],
                type_name=row["type_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                sections_count=row["sections_count"] or 0,
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of templates"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
        )
        return result or 0

    @classmethod
    async def get_unique_forms_count(cls) -> int:
        """Get count of unique document_mode_id (forms)"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(DISTINCT document_mode_id) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
        )
        return result or 0

    @classmethod
    async def get_last_update(cls) -> Optional[datetime]:
        """Get timestamp of last update"""
        result = await pg_client.fetchval(
            f"SELECT MAX(updated_at) FROM {cls.TABLE_NAME}"
        )
        return result

    @classmethod
    async def sync_from_api(cls) -> SyncResult:
        """
        Sync JSON templates from Kontur API

        Fetches templates from GET /common/v1/jsonTemplates
        and upserts them into dc_json_templates table.

        Returns:
            SyncResult with statistics
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            # Fetch from API
            client = get_kontur_client()
            api_templates = await client.get_document_types()

            log.info(f"Fetched {len(api_templates)} templates from Kontur API")

            for template in api_templates:
                try:
                    # Extract fields from API response
                    gf_code = template.get("gf")
                    document_mode_id = template.get("documentModeId")
                    type_name = template.get("typeName")

                    if not gf_code or not document_mode_id or not type_name:
                        log.warning(f"Skipping template with missing fields: {template}")
                        skipped += 1
                        continue

                    # Upsert (INSERT ON CONFLICT UPDATE)
                    result = await pg_client.execute(
                        f"""
                        INSERT INTO {cls.TABLE_NAME}
                            (gf_code, document_mode_id, type_name, is_active, created_at, updated_at)
                        VALUES ($1, $2, $3, TRUE, $4, $5)
                        ON CONFLICT (gf_code, document_mode_id, type_name)
                        DO UPDATE SET
                            is_active = TRUE,
                            updated_at = $5
                        """,
                        gf_code,
                        document_mode_id,
                        type_name,
                        sync_time,
                        sync_time
                    )

                    # Check if inserted or updated
                    if "INSERT" in result:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    log.error(f"Error processing template {template}: {e}")
                    errors += 1

            log.info(
                f"Sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=len(api_templates),
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during sync: {e}")
            raise

    @classmethod
    async def search(cls, query: str, limit: int = 50) -> List[JsonTemplate]:
        """Search templates by type_name or document_mode_id"""
        rows = await pg_client.fetch(
            f"""
            SELECT t.id, t.gf_code, t.document_mode_id, t.type_name,
                   t.is_active, t.created_at, t.updated_at,
                   COALESCE(s.sections_count, 0) as sections_count
            FROM {cls.TABLE_NAME} t
            LEFT JOIN (
                SELECT fd.document_mode_id, COUNT(fs.id) as sections_count
                FROM dc_form_definitions fd
                JOIN {cls.SECTIONS_TABLE} fs ON fs.form_definition_id = fd.id
                GROUP BY fd.document_mode_id
            ) s ON t.document_mode_id = s.document_mode_id
            WHERE t.is_active = TRUE
              AND (t.type_name ILIKE $1 OR t.document_mode_id ILIKE $1 OR t.gf_code ILIKE $1)
            ORDER BY t.type_name
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            JsonTemplate(
                id=str(row["id"]),
                gf_code=row["gf_code"],
                document_mode_id=row["document_mode_id"],
                type_name=row["type_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                sections_count=row["sections_count"] or 0,
            )
            for row in rows
        ]

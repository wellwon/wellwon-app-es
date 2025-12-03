# =============================================================================
# File: app/declarant/form_definitions_service.py
# Description: Service for CRUD operations on form definitions
# =============================================================================

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from app.infra.persistence import pg_client
from app.declarant.schema_transform_service import (
    SchemaTransformService,
    FormDefinition,
    FormSection,
    FieldDefinition,
    FieldType,
    FieldOption
)
from app.declarant.kontur_client import KonturClientError

log = logging.getLogger("wellwon.declarant.form_definitions")


# =============================================================================
# Sync Result
# =============================================================================

@dataclass
class SyncResult:
    """Result of sync operation"""
    total_processed: int = 0
    forms_created: int = 0
    forms_updated: int = 0
    schemas_changed: int = 0
    errors: int = 0
    error_details: List[Dict[str, str]] = None
    sync_duration_ms: int = 0
    sync_time: datetime = None

    def __post_init__(self):
        if self.error_details is None:
            self.error_details = []
        if self.sync_time is None:
            self.sync_time = datetime.now(timezone.utc)


# =============================================================================
# Form Definitions Service
# =============================================================================

class FormDefinitionsService:
    """
    Service for CRUD operations on form definitions

    Key responsibilities:
    1. Get form definition by document_mode_id
    2. Sync form definitions from Kontur API
    3. Smart merge of schema changes with customizations
    4. Log sync history
    """

    TABLE_NAME = "dc_form_definitions"
    SECTIONS_TABLE = "dc_form_sections"
    SYNC_HISTORY_TABLE = "dc_form_sync_history"

    # =========================================================================
    # Read Operations
    # =========================================================================

    @classmethod
    async def get_by_document_mode_id(
        cls,
        document_mode_id: str
    ) -> Optional[FormDefinition]:
        """Get form definition by document mode ID"""
        row = await pg_client.fetchrow(
            f"""
            SELECT id, document_mode_id, gf_code, type_name,
                   fields, default_values, kontur_schema_json,
                   kontur_schema_hash, version, form_width, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE document_mode_id = $1 AND is_active = TRUE
            """,
            document_mode_id
        )

        if not row:
            return None

        # Load sections
        sections_rows = await pg_client.fetch(
            f"""
            SELECT section_key, title_ru, description_ru, icon,
                   sort_order, field_paths, fields_config, columns, collapsible, default_expanded
            FROM {cls.SECTIONS_TABLE}
            WHERE form_definition_id = $1
            ORDER BY sort_order
            """,
            row["id"]
        )

        # Parse fields from JSONB
        fields_data = row["fields"] if row["fields"] else []
        # Handle case when JSONB comes as string
        if isinstance(fields_data, str):
            import json
            try:
                fields_data = json.loads(fields_data)
            except json.JSONDecodeError:
                fields_data = []
        fields = cls._parse_fields_from_json(fields_data)

        # Parse sections
        sections = []
        for s in sections_rows:
            # Handle field_paths - may come as string from JSONB
            field_paths = s["field_paths"] if s["field_paths"] else []
            if isinstance(field_paths, str):
                try:
                    field_paths = json.loads(field_paths)
                except json.JSONDecodeError:
                    field_paths = []

            # Handle fields_config - full field configurations from Form Builder
            fields_config = s["fields_config"] if s["fields_config"] else []
            if isinstance(fields_config, str):
                try:
                    fields_config = json.loads(fields_config)
                except json.JSONDecodeError:
                    fields_config = []

            sections.append(FormSection(
                section_key=s["section_key"],
                title_ru=s["title_ru"],
                description_ru=s["description_ru"] or "",
                icon=s["icon"] or "FileText",
                sort_order=s["sort_order"],
                field_paths=field_paths,
                fields_config=fields_config,
                columns=s["columns"],
                collapsible=s["collapsible"],
                default_expanded=s["default_expanded"]
            ))

        # Parse default_values - may come as string from JSONB
        default_values = row["default_values"] if row["default_values"] else {}
        if isinstance(default_values, str):
            try:
                default_values = json.loads(default_values)
            except json.JSONDecodeError:
                default_values = {}

        # Parse kontur_schema_json - may come as string from JSONB
        kontur_schema_json = row["kontur_schema_json"] if row["kontur_schema_json"] else {}
        if isinstance(kontur_schema_json, str):
            try:
                kontur_schema_json = json.loads(kontur_schema_json)
            except json.JSONDecodeError:
                kontur_schema_json = {}

        return FormDefinition(
            id=str(row["id"]),
            document_mode_id=row["document_mode_id"],
            gf_code=row["gf_code"],
            type_name=row["type_name"],
            fields=fields,
            sections=sections,
            default_values=default_values,
            kontur_schema_json=kontur_schema_json,
            kontur_schema_hash=row["kontur_schema_hash"] or "",
            version=row["version"],
            form_width=row["form_width"] or 100
        )

    @classmethod
    def _parse_fields_from_json(cls, fields_data: List[Dict]) -> List[FieldDefinition]:
        """Parse fields from JSON data"""
        fields = []
        for fd in fields_data:
            field = FieldDefinition(
                path=fd.get("path", ""),
                name=fd.get("name", ""),
                field_type=FieldType(fd.get("field_type", "text")),
                required=fd.get("required", False),
                label_ru=fd.get("label_ru", ""),
                hint_ru=fd.get("hint_ru", ""),
                placeholder_ru=fd.get("placeholder_ru", ""),
                min_value=fd.get("min_value"),
                max_value=fd.get("max_value"),
                max_length=fd.get("max_length"),
                pattern=fd.get("pattern"),
            )

            # Parse options
            if "options" in fd:
                field.options = [
                    FieldOption(value=o["value"], label=o["label"])
                    for o in fd["options"]
                ]

            # Parse children recursively
            if "children" in fd:
                field.children = cls._parse_fields_from_json(fd["children"])

            fields.append(field)

        return fields

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[FormDefinition]:
        """Get all form definitions"""
        query = f"""
            SELECT id, document_mode_id, gf_code, type_name,
                   fields, default_values, version, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY type_name"

        rows = await pg_client.fetch(query)

        definitions = []
        for row in rows:
            # Parse fields - may come as string from JSONB
            fields_data = row["fields"] if row["fields"] else []
            if isinstance(fields_data, str):
                try:
                    fields_data = json.loads(fields_data)
                except json.JSONDecodeError:
                    fields_data = []
            fields = cls._parse_fields_from_json(fields_data)

            # Parse default_values - may come as string from JSONB
            default_values = row["default_values"] if row["default_values"] else {}
            if isinstance(default_values, str):
                try:
                    default_values = json.loads(default_values)
                except json.JSONDecodeError:
                    default_values = {}

            definitions.append(FormDefinition(
                id=str(row["id"]),
                document_mode_id=row["document_mode_id"],
                gf_code=row["gf_code"],
                type_name=row["type_name"],
                fields=fields,
                default_values=default_values,
                version=row["version"]
            ))

        return definitions

    @classmethod
    async def get_count(cls) -> int:
        """Get count of active form definitions"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
        )
        return result or 0

    # =========================================================================
    # Sync Operations
    # =========================================================================

    @classmethod
    async def sync_from_api(
        cls,
        document_mode_id: Optional[str] = None
    ) -> SyncResult:
        """
        Sync form definitions from Kontur API

        Args:
            document_mode_id: Sync specific document or all if None
        """
        sync_start = datetime.now(timezone.utc)
        result = SyncResult(sync_time=sync_start)

        try:
            if document_mode_id:
                # Sync single document
                await cls._sync_single(document_mode_id, result)
                result.total_processed = 1
            else:
                # Sync all templates
                from app.declarant.json_templates_service import JsonTemplatesService
                templates = await JsonTemplatesService.get_all()

                # Get unique document_mode_ids with their data
                unique_templates: Dict[str, Dict] = {}
                for t in templates:
                    if t.document_mode_id not in unique_templates:
                        unique_templates[t.document_mode_id] = {
                            "gf_code": t.gf_code,
                            "type_name": t.type_name
                        }

                result.total_processed = len(unique_templates)

                for doc_id, template_data in unique_templates.items():
                    await cls._sync_single(
                        doc_id,
                        result,
                        gf_code=template_data["gf_code"],
                        type_name=template_data["type_name"]
                    )

            # Calculate duration
            sync_end = datetime.now(timezone.utc)
            result.sync_duration_ms = int((sync_end - sync_start).total_seconds() * 1000)

            # Log sync history
            status = "success" if result.errors == 0 else "partial"
            await cls._log_sync(document_mode_id, "single" if document_mode_id else "full", status, result)

            log.info(
                f"Sync completed: {result.forms_created} created, "
                f"{result.forms_updated} updated, {result.schemas_changed} changed, "
                f"{result.errors} errors"
            )

            return result

        except Exception as e:
            log.error(f"Sync failed: {e}")
            result.error_details.append({"global_error": str(e)})

            sync_end = datetime.now(timezone.utc)
            result.sync_duration_ms = int((sync_end - sync_start).total_seconds() * 1000)

            await cls._log_sync(document_mode_id, "single" if document_mode_id else "full", "failed", result)
            raise

    @classmethod
    async def _sync_single(
        cls,
        document_mode_id: str,
        result: SyncResult,
        gf_code: str = "",
        type_name: str = ""
    ):
        """Sync a single form definition"""
        try:
            # Transform schema from Kontur
            form_def = await SchemaTransformService.transform_schema(
                document_mode_id,
                gf_code=gf_code,
                type_name=type_name
            )

            # Check if exists
            existing = await cls.get_by_document_mode_id(document_mode_id)

            if existing:
                # Check if schema changed
                if existing.kontur_schema_hash != form_def.kontur_schema_hash:
                    # Schema changed - merge and update
                    merged = cls._merge_schema_changes(existing, form_def)
                    await cls._update(merged)
                    result.forms_updated += 1
                    result.schemas_changed += 1
                    log.info(f"Updated form definition for {document_mode_id} (schema changed)")
                else:
                    # No changes
                    log.debug(f"Form definition for {document_mode_id} unchanged")
            else:
                # Create new
                await cls._create(form_def)
                result.forms_created += 1
                log.info(f"Created form definition for {document_mode_id}")

        except KonturClientError as e:
            log.warning(f"Kontur API error for {document_mode_id}: {e}")
            result.errors += 1
            result.error_details.append({
                "document_mode_id": document_mode_id,
                "error": str(e)
            })
        except Exception as e:
            log.error(f"Error syncing {document_mode_id}: {e}")
            result.errors += 1
            result.error_details.append({
                "document_mode_id": document_mode_id,
                "error": str(e)
            })

    @classmethod
    def _merge_schema_changes(
        cls,
        existing: FormDefinition,
        new_def: FormDefinition
    ) -> FormDefinition:
        """
        Smart merge: add new fields, preserve customizations for existing fields

        Strategy:
        - New fields: add with default labels
        - Existing fields: keep custom labels from database
        - Removed fields: keep (mark deprecated later if needed)
        """
        # Build map of existing fields by path
        existing_fields_map: Dict[str, FieldDefinition] = {}

        def collect_existing(fields: List[FieldDefinition]):
            for f in fields:
                existing_fields_map[f.path] = f
                if f.children:
                    collect_existing(f.children)

        collect_existing(existing.fields)

        # Apply existing customizations to new fields
        def apply_customizations(fields: List[FieldDefinition]):
            for f in fields:
                if f.path in existing_fields_map:
                    old_field = existing_fields_map[f.path]
                    # Keep custom labels if they were set
                    if old_field.label_ru and old_field.label_ru != cls._default_label(old_field.name):
                        f.label_ru = old_field.label_ru
                    if old_field.hint_ru:
                        f.hint_ru = old_field.hint_ru
                    if old_field.placeholder_ru:
                        f.placeholder_ru = old_field.placeholder_ru
                if f.children:
                    apply_customizations(f.children)

        apply_customizations(new_def.fields)

        # Keep existing sections if they exist
        if existing.sections:
            new_def.sections = existing.sections

        # Increment version
        new_def.version = existing.version + 1
        new_def.id = existing.id

        return new_def

    @classmethod
    def _default_label(cls, name: str) -> str:
        """Generate default label from field name"""
        import re
        result = re.sub(r'_', ' ', name)
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)
        return result.strip()

    # =========================================================================
    # Write Operations
    # =========================================================================

    @classmethod
    async def _create(cls, form_def: FormDefinition) -> str:
        """Create new form definition"""
        fields_json = json.dumps([f.to_dict() for f in form_def.fields])

        row = await pg_client.fetchrow(
            f"""
            INSERT INTO {cls.TABLE_NAME}
                (document_mode_id, gf_code, type_name, fields,
                 default_values, kontur_schema_json, kontur_schema_hash, version)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7, 1)
            RETURNING id
            """,
            form_def.document_mode_id,
            form_def.gf_code,
            form_def.type_name,
            fields_json,
            json.dumps(form_def.default_values),
            json.dumps(form_def.kontur_schema_json),
            form_def.kontur_schema_hash
        )

        form_id = row["id"]

        # Create sections
        for section in form_def.sections:
            await pg_client.execute(
                f"""
                INSERT INTO {cls.SECTIONS_TABLE}
                    (form_definition_id, section_key, title_ru, description_ru,
                     icon, sort_order, field_paths, columns, collapsible, default_expanded)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10)
                """,
                form_id,
                section.section_key,
                section.title_ru,
                section.description_ru,
                section.icon,
                section.sort_order,
                json.dumps(section.field_paths),
                section.columns,
                section.collapsible,
                section.default_expanded
            )

        return str(form_id)

    @classmethod
    async def _update(cls, form_def: FormDefinition):
        """Update existing form definition"""
        fields_json = json.dumps([f.to_dict() for f in form_def.fields])

        await pg_client.execute(
            f"""
            UPDATE {cls.TABLE_NAME}
            SET fields = $2::jsonb,
                default_values = $3::jsonb,
                kontur_schema_json = $4::jsonb,
                kontur_schema_hash = $5,
                version = $6,
                updated_at = NOW()
            WHERE document_mode_id = $1 AND is_active = TRUE
            """,
            form_def.document_mode_id,
            fields_json,
            json.dumps(form_def.default_values),
            json.dumps(form_def.kontur_schema_json),
            form_def.kontur_schema_hash,
            form_def.version
        )

    # =========================================================================
    # Sync History
    # =========================================================================

    @classmethod
    async def _log_sync(
        cls,
        document_mode_id: Optional[str],
        sync_type: str,
        status: str,
        result: SyncResult
    ):
        """Log sync operation to history table"""
        await pg_client.execute(
            f"""
            INSERT INTO {cls.SYNC_HISTORY_TABLE}
                (document_mode_id, sync_type, status, total_processed,
                 forms_created, forms_updated, schemas_changed, errors,
                 error_details, sync_duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
            """,
            document_mode_id,
            sync_type,
            status,
            result.total_processed,
            result.forms_created,
            result.forms_updated,
            result.schemas_changed,
            result.errors,
            json.dumps(result.error_details) if result.error_details else None,
            result.sync_duration_ms
        )

    # =========================================================================
    # Section Updates (Form Builder)
    # =========================================================================

    @classmethod
    async def update_sections(cls, document_mode_id: str, sections: List) -> None:
        """
        Update sections for a form definition from Form Builder

        Args:
            document_mode_id: The document mode ID
            sections: List of FormSectionConfigRequest from Form Builder
        """
        # Get the form definition ID
        row = await pg_client.fetchrow(
            f"SELECT id FROM {cls.TABLE_NAME} WHERE document_mode_id = $1 AND is_active = TRUE",
            document_mode_id
        )

        if not row:
            raise ValueError(f"Form definition not found for {document_mode_id}")

        form_id = row["id"]

        # Delete existing sections
        await pg_client.execute(
            f"DELETE FROM {cls.SECTIONS_TABLE} WHERE form_definition_id = $1",
            form_id
        )

        # Insert new sections with full field configurations
        for section in sections:
            # Convert fields to list of dicts for JSON storage
            fields_config = []
            for f in section.fields:
                field_dict = {
                    "id": f.id,
                    "schemaPath": f.schemaPath,
                    "width": f.width,
                    "order": f.order,
                }
                # Element type (subheading, section-divider)
                if hasattr(f, 'elementType') and f.elementType:
                    field_dict["elementType"] = f.elementType
                # Field type (text, number, date, select, etc.)
                if hasattr(f, 'fieldType') and f.fieldType:
                    field_dict["fieldType"] = f.fieldType
                if f.customLabel:
                    field_dict["customLabel"] = f.customLabel
                if f.customPlaceholder:
                    field_dict["customPlaceholder"] = f.customPlaceholder
                if f.customHint:
                    field_dict["customHint"] = f.customHint
                if hasattr(f, 'prompt') and f.prompt:
                    field_dict["prompt"] = f.prompt
                if f.readonly is not None:
                    field_dict["readonly"] = f.readonly
                if f.defaultValue is not None:
                    field_dict["defaultValue"] = f.defaultValue
                # Add required field if present
                if hasattr(f, 'required') and f.required is not None:
                    field_dict["required"] = f.required
                # Add isSelect and selectOptions for dropdown fields
                if hasattr(f, 'isSelect') and f.isSelect:
                    field_dict["isSelect"] = f.isSelect
                if hasattr(f, 'selectOptions') and f.selectOptions:
                    # Convert selectOptions to list of dicts
                    field_dict["selectOptions"] = [
                        {"label": opt.label, "value": opt.value}
                        for opt in f.selectOptions
                    ]
                fields_config.append(field_dict)

            # Legacy field_paths for backwards compatibility
            field_paths = [f.schemaPath for f in section.fields]

            await pg_client.execute(
                f"""
                INSERT INTO {cls.SECTIONS_TABLE}
                    (form_definition_id, section_key, title_ru, description_ru,
                     icon, sort_order, field_paths, fields_config, columns, collapsible, default_expanded)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11)
                """,
                form_id,
                section.key,
                section.titleRu,
                section.descriptionRu or "",
                section.icon,
                section.order,
                json.dumps(field_paths),
                json.dumps(fields_config),
                section.columns,
                section.collapsible,
                section.defaultExpanded
            )

        # Update the form definition's updated_at timestamp
        await pg_client.execute(
            f"UPDATE {cls.TABLE_NAME} SET updated_at = NOW() WHERE id = $1",
            form_id
        )

        log.info(f"Updated {len(sections)} sections for form {document_mode_id}")

    @classmethod
    async def update_form_width(cls, document_mode_id: str, form_width: int) -> None:
        """
        Update form width for a form definition

        Args:
            document_mode_id: The document mode ID
            form_width: Form width in % (70-130)
        """
        # Clamp form_width to valid range
        form_width = max(70, min(130, form_width))

        await pg_client.execute(
            f"UPDATE {cls.TABLE_NAME} SET form_width = $1, updated_at = NOW() WHERE document_mode_id = $2 AND is_active = TRUE",
            form_width,
            document_mode_id
        )

        log.info(f"Updated form_width to {form_width} for form {document_mode_id}")

    # =========================================================================
    # Version Management
    # =========================================================================

    VERSIONS_TABLE = "dc_form_definition_versions"

    @classmethod
    async def create_version(
        cls,
        document_mode_id: str,
        version_label: Optional[str] = None,
        change_description: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Create a new version snapshot of the current sections configuration.

        Args:
            document_mode_id: The document mode ID
            version_label: Optional label for this version (e.g., "v1.0")
            change_description: Optional description of changes

        Returns:
            Version data dict or None if failed
        """
        # Get form definition with sections
        form_def = await cls.get_by_document_mode_id(document_mode_id)
        if not form_def:
            raise ValueError(f"Form definition not found for {document_mode_id}")

        # Get next version number
        current_max = await pg_client.fetchval(
            f"""
            SELECT COALESCE(MAX(version_number), 0)
            FROM {cls.VERSIONS_TABLE}
            WHERE document_mode_id = $1
            """,
            document_mode_id
        )
        next_version = (current_max or 0) + 1

        # Prepare sections snapshot
        sections_snapshot = []
        for section in form_def.sections:
            sections_snapshot.append({
                "section_key": section.section_key,
                "title_ru": section.title_ru,
                "description_ru": section.description_ru,
                "icon": section.icon,
                "sort_order": section.sort_order,
                "field_paths": section.field_paths,
                "fields_config": section.fields_config,
                "columns": section.columns,
                "collapsible": section.collapsible,
                "default_expanded": section.default_expanded
            })

        # Count stats
        fields_count = sum(len(s.get("fields_config", [])) for s in sections_snapshot)
        sections_count = len(sections_snapshot)

        # Insert version
        row = await pg_client.fetchrow(
            f"""
            INSERT INTO {cls.VERSIONS_TABLE}
                (document_mode_id, version_number, version_label, change_description,
                 sections_snapshot, fields_count, sections_count, is_current)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, TRUE)
            RETURNING id, version_number, version_label, change_description,
                      fields_count, sections_count, created_at, is_current
            """,
            document_mode_id,
            next_version,
            version_label or f"Версия {next_version}",
            change_description,
            json.dumps(sections_snapshot),
            fields_count,
            sections_count
        )

        # Mark previous versions as not current
        await pg_client.execute(
            f"""
            UPDATE {cls.VERSIONS_TABLE}
            SET is_current = FALSE
            WHERE document_mode_id = $1 AND version_number != $2
            """,
            document_mode_id,
            next_version
        )

        log.info(f"Created version {next_version} for {document_mode_id}")

        return {
            "id": str(row["id"]),
            "version_number": row["version_number"],
            "version_label": row["version_label"],
            "change_description": row["change_description"],
            "fields_count": row["fields_count"],
            "sections_count": row["sections_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "is_current": row["is_current"]
        }

    @classmethod
    async def get_versions(cls, document_mode_id: str) -> List[Dict]:
        """
        Get all versions for a form definition.

        Args:
            document_mode_id: The document mode ID

        Returns:
            List of version data dicts
        """
        rows = await pg_client.fetch(
            f"""
            SELECT id, version_number, version_label, change_description,
                   fields_count, sections_count, created_at, is_current
            FROM {cls.VERSIONS_TABLE}
            WHERE document_mode_id = $1
            ORDER BY version_number DESC
            """,
            document_mode_id
        )

        return [
            {
                "id": str(row["id"]),
                "version_number": row["version_number"],
                "version_label": row["version_label"],
                "change_description": row["change_description"],
                "fields_count": row["fields_count"],
                "sections_count": row["sections_count"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "is_current": row["is_current"]
            }
            for row in rows
        ]

    @classmethod
    async def get_version(cls, document_mode_id: str, version_number: int) -> Optional[Dict]:
        """
        Get a specific version with full sections data.

        Args:
            document_mode_id: The document mode ID
            version_number: The version number to retrieve

        Returns:
            Version data dict with sections_snapshot or None
        """
        row = await pg_client.fetchrow(
            f"""
            SELECT id, version_number, version_label, change_description,
                   sections_snapshot, fields_count, sections_count, created_at, is_current
            FROM {cls.VERSIONS_TABLE}
            WHERE document_mode_id = $1 AND version_number = $2
            """,
            document_mode_id,
            version_number
        )

        if not row:
            return None

        sections_snapshot = row["sections_snapshot"]
        if isinstance(sections_snapshot, str):
            sections_snapshot = json.loads(sections_snapshot)

        return {
            "id": str(row["id"]),
            "version_number": row["version_number"],
            "version_label": row["version_label"],
            "change_description": row["change_description"],
            "sections_snapshot": sections_snapshot,
            "fields_count": row["fields_count"],
            "sections_count": row["sections_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "is_current": row["is_current"]
        }

    @classmethod
    async def restore_version(cls, document_mode_id: str, version_number: int) -> bool:
        """
        Restore sections from a specific version.

        Args:
            document_mode_id: The document mode ID
            version_number: The version number to restore

        Returns:
            True if successful, False otherwise
        """
        # Get the version data
        version = await cls.get_version(document_mode_id, version_number)
        if not version:
            raise ValueError(f"Version {version_number} not found for {document_mode_id}")

        # Get the form definition ID
        row = await pg_client.fetchrow(
            f"SELECT id FROM {cls.TABLE_NAME} WHERE document_mode_id = $1 AND is_active = TRUE",
            document_mode_id
        )

        if not row:
            raise ValueError(f"Form definition not found for {document_mode_id}")

        form_id = row["id"]

        # Delete existing sections
        await pg_client.execute(
            f"DELETE FROM {cls.SECTIONS_TABLE} WHERE form_definition_id = $1",
            form_id
        )

        # Restore sections from snapshot
        sections_snapshot = version.get("sections_snapshot", [])
        for section in sections_snapshot:
            field_paths = section.get("field_paths", [])
            fields_config = section.get("fields_config", [])

            await pg_client.execute(
                f"""
                INSERT INTO {cls.SECTIONS_TABLE}
                    (form_definition_id, section_key, title_ru, description_ru,
                     icon, sort_order, field_paths, fields_config, columns, collapsible, default_expanded)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11)
                """,
                form_id,
                section.get("section_key", ""),
                section.get("title_ru", ""),
                section.get("description_ru", ""),
                section.get("icon", "FileText"),
                section.get("sort_order", 0),
                json.dumps(field_paths) if field_paths else "[]",
                json.dumps(fields_config) if fields_config else "[]",
                section.get("columns", 2),
                section.get("collapsible", False),
                section.get("default_expanded", True)
            )

        # Mark this version as current
        await pg_client.execute(
            f"UPDATE {cls.VERSIONS_TABLE} SET is_current = FALSE WHERE document_mode_id = $1",
            document_mode_id
        )
        await pg_client.execute(
            f"UPDATE {cls.VERSIONS_TABLE} SET is_current = TRUE WHERE document_mode_id = $1 AND version_number = $2",
            document_mode_id,
            version_number
        )

        # Update timestamp
        await pg_client.execute(
            f"UPDATE {cls.TABLE_NAME} SET updated_at = NOW() WHERE id = $1",
            form_id
        )

        log.info(f"Restored version {version_number} for {document_mode_id}")
        return True

    @classmethod
    async def delete_version(cls, document_mode_id: str, version_number: int) -> bool:
        """
        Delete a specific version (cannot delete current version).

        Args:
            document_mode_id: The document mode ID
            version_number: The version number to delete

        Returns:
            True if deleted, False otherwise
        """
        # Check if it's the current version
        row = await pg_client.fetchrow(
            f"SELECT is_current FROM {cls.VERSIONS_TABLE} WHERE document_mode_id = $1 AND version_number = $2",
            document_mode_id,
            version_number
        )

        if not row:
            return False

        if row["is_current"]:
            raise ValueError("Cannot delete current version")

        result = await pg_client.execute(
            f"DELETE FROM {cls.VERSIONS_TABLE} WHERE document_mode_id = $1 AND version_number = $2",
            document_mode_id,
            version_number
        )

        log.info(f"Deleted version {version_number} for {document_mode_id}")
        return result == "DELETE 1"

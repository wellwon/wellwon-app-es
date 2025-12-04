# =============================================================================
# File: app/infra/read_repos/customs_read_repo.py
# Description: Read repository for Customs domain
# =============================================================================

from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.config.logging_config import get_logger
from app.infra.persistence import pg_client
from app.customs.read_models import (
    CustomsDeclarationReadModel,
    DeclarationSummaryReadModel,
    DeclarationStatusReadModel,
    CommonOrganizationReadModel,
    OrganizationSummaryReadModel,
)

log = get_logger("wellwon.customs.read_repo")


class CustomsDeclarationReadRepo:
    """
    Read repository for CustomsDeclaration domain.

    Provides read/write operations for customs declarations read model (PostgreSQL).
    All methods are static for ease of use from projectors and query handlers.
    """

    # =========================================================================
    # Declaration Insert/Update Operations (for Projectors)
    # =========================================================================

    @staticmethod
    async def insert_declaration(
        declaration_id: uuid.UUID,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        name: str,
        declaration_type: str,
        procedure: str,
        customs_code: str,
        organization_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        form_data: Optional[Dict[str, Any]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        created_at: Optional[str] = None,
    ) -> None:
        """Insert a new customs declaration record"""
        import json

        created_dt = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()

        await pg_client.execute(
            """
            INSERT INTO customs_declarations (
                id, user_id, company_id, name, declaration_type, procedure,
                customs_code, status, organization_id, employee_id,
                form_data, documents, created_at, updated_at,
                is_deleted, aggregate_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, 0, $8, $9,
                $10::jsonb, $11::jsonb, $12, $12,
                false, 1
            )
            ON CONFLICT (id) DO NOTHING
            """,
            declaration_id, user_id, company_id, name, declaration_type, procedure,
            customs_code, organization_id, employee_id,
            json.dumps(form_data or {}), json.dumps(documents or []), created_dt,
        )

    @staticmethod
    async def mark_declaration_deleted(
        declaration_id: uuid.UUID,
        deleted_at: Optional[str] = None,
    ) -> None:
        """Mark declaration as deleted (soft delete)"""
        deleted_dt = datetime.fromisoformat(deleted_at) if deleted_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET is_deleted = true, deleted_at = $1, updated_at = $1, aggregate_version = aggregate_version + 1
            WHERE id = $2
            """,
            deleted_dt, declaration_id
        )

    @staticmethod
    async def update_form_data(
        declaration_id: uuid.UUID,
        form_data: Dict[str, Any],
        updated_at: Optional[str] = None,
    ) -> None:
        """Update declaration form data (merge)"""
        import json

        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET form_data = form_data || $1::jsonb, updated_at = $2, aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            json.dumps(form_data), updated_dt, declaration_id
        )

    @staticmethod
    async def add_goods(
        declaration_id: uuid.UUID,
        goods: List[Dict[str, Any]],
        updated_at: Optional[str] = None,
    ) -> None:
        """Add goods items to declaration"""
        import json

        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        # Append goods to existing JSONB array
        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET goods = COALESCE(goods, '[]'::jsonb) || $1::jsonb,
                updated_at = $2,
                aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            json.dumps(goods), updated_dt, declaration_id
        )

    @staticmethod
    async def add_document(
        declaration_id: uuid.UUID,
        document: Dict[str, Any],
        updated_at: Optional[str] = None,
    ) -> None:
        """Add document to declaration"""
        import json

        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET documents = COALESCE(documents, '[]'::jsonb) || $1::jsonb,
                updated_at = $2,
                aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            json.dumps([document]), updated_dt, declaration_id
        )

    @staticmethod
    async def remove_document(
        declaration_id: uuid.UUID,
        document_id: str,
        updated_at: Optional[str] = None,
    ) -> None:
        """Remove document from declaration by document_id"""
        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        # Remove document from JSONB array where document_id matches
        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET documents = (
                SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                FROM jsonb_array_elements(documents) elem
                WHERE elem->>'document_id' != $1
            ),
            updated_at = $2,
            aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            document_id, updated_dt, declaration_id
        )

    @staticmethod
    async def update_submission_status(
        declaration_id: uuid.UUID,
        kontur_docflow_id: str,
        status: int,
        submitted_at: Optional[str] = None,
    ) -> None:
        """Update declaration submission status"""
        submitted_dt = datetime.fromisoformat(submitted_at) if submitted_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET kontur_docflow_id = $1, status = $2, submitted_at = $3, updated_at = $3,
                aggregate_version = aggregate_version + 1
            WHERE id = $4
            """,
            kontur_docflow_id, status, submitted_dt, declaration_id
        )

    @staticmethod
    async def update_status(
        declaration_id: uuid.UUID,
        status: int,
        gtd_number: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        """Update declaration status"""
        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        if gtd_number:
            await pg_client.execute(
                """
                UPDATE customs_declarations
                SET status = $1, gtd_number = $2, updated_at = $3, aggregate_version = aggregate_version + 1
                WHERE id = $4
                """,
                status, gtd_number, updated_dt, declaration_id
            )
        else:
            await pg_client.execute(
                """
                UPDATE customs_declarations
                SET status = $1, updated_at = $2, aggregate_version = aggregate_version + 1
                WHERE id = $3
                """,
                status, updated_dt, declaration_id
            )

    @staticmethod
    async def update_organization(
        declaration_id: uuid.UUID,
        organization_id: str,
        updated_at: Optional[str] = None,
    ) -> None:
        """Update organization on declaration"""
        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET organization_id = $1, updated_at = $2, aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            organization_id, updated_dt, declaration_id
        )

    @staticmethod
    async def update_employee(
        declaration_id: uuid.UUID,
        employee_id: str,
        updated_at: Optional[str] = None,
    ) -> None:
        """Update employee on declaration"""
        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_declarations
            SET employee_id = $1, updated_at = $2, aggregate_version = aggregate_version + 1
            WHERE id = $3
            """,
            employee_id, updated_dt, declaration_id
        )

    @staticmethod
    async def record_sync_failure(
        declaration_id: uuid.UUID,
        error_message: str,
        failed_at: Optional[str] = None,
    ) -> None:
        """Record Kontur sync failure for audit"""
        import json
        failed_dt = datetime.fromisoformat(failed_at) if failed_at else datetime.utcnow()

        await pg_client.execute(
            """
            INSERT INTO customs_sync_failures (id, declaration_id, error_message, failed_at)
            VALUES (gen_random_uuid(), $1, $2, $3)
            """,
            declaration_id, error_message, failed_dt
        )

    # =========================================================================
    # Declaration Query Operations (for Query Handlers)
    # =========================================================================

    @staticmethod
    async def get_declaration_by_id(
        declaration_id: uuid.UUID,
    ) -> Optional[CustomsDeclarationReadModel]:
        """Get full declaration by ID"""
        row = await pg_client.fetchrow(
            """
            SELECT * FROM customs_declarations
            WHERE id = $1 AND is_deleted = false
            """,
            declaration_id
        )
        if not row:
            return None
        return CustomsDeclarationReadModel(**dict(row))

    @staticmethod
    async def get_declaration_summary_by_id(
        declaration_id: uuid.UUID,
    ) -> Optional[DeclarationSummaryReadModel]:
        """Get declaration summary by ID"""
        row = await pg_client.fetchrow(
            """
            SELECT id, name, declaration_type, procedure, customs_code, status,
                   gtd_number, organization_id, created_at, submitted_at, is_deleted
            FROM customs_declarations
            WHERE id = $1 AND is_deleted = false
            """,
            declaration_id
        )
        if not row:
            return None
        return DeclarationSummaryReadModel(**dict(row))

    @staticmethod
    async def list_declarations(
        user_id: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        status: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DeclarationSummaryReadModel]:
        """List declarations for user with optional filters"""
        conditions = ["user_id = $1", "is_deleted = false"]
        params = [user_id]
        param_idx = 2

        if company_id:
            conditions.append(f"company_id = ${param_idx}")
            params.append(company_id)
            param_idx += 1

        if status is not None:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        params.extend([limit, offset])

        rows = await pg_client.fetch(
            f"""
            SELECT id, name, declaration_type, procedure, customs_code, status,
                   gtd_number, organization_id, created_at, submitted_at, is_deleted
            FROM customs_declarations
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params
        )

        return [DeclarationSummaryReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def list_pending_declarations(
        status_list: List[int],
        has_kontur_docflow_id: bool = True,
        limit: int = 100,
    ) -> List[DeclarationStatusReadModel]:
        """List declarations pending sync (for background worker)"""
        status_condition = f"status = ANY($1::int[])"
        kontur_condition = "kontur_docflow_id IS NOT NULL" if has_kontur_docflow_id else "kontur_docflow_id IS NULL"

        rows = await pg_client.fetch(
            f"""
            SELECT id, name, status, kontur_docflow_id, gtd_number, submitted_at, updated_at
            FROM customs_declarations
            WHERE {status_condition} AND {kontur_condition} AND is_deleted = false
            ORDER BY submitted_at ASC
            LIMIT $2
            """,
            status_list, limit
        )

        return [DeclarationStatusReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_declaration_by_kontur_docflow_id(
        kontur_docflow_id: str,
    ) -> Optional[CustomsDeclarationReadModel]:
        """Get declaration by Kontur docflow ID"""
        row = await pg_client.fetchrow(
            """
            SELECT * FROM customs_declarations
            WHERE kontur_docflow_id = $1 AND is_deleted = false
            """,
            kontur_docflow_id
        )
        if not row:
            return None
        return CustomsDeclarationReadModel(**dict(row))


class CommonOrganizationReadRepo:
    """
    Read repository for CommonOrganization domain.

    Provides read/write operations for customs organizations read model (PostgreSQL).
    """

    # =========================================================================
    # Organization Insert/Update Operations (for Projectors)
    # =========================================================================

    @staticmethod
    async def insert_organization(
        org_id: uuid.UUID,
        org_name: str,
        org_type: int,
        kontur_org_id: Optional[str] = None,
        short_name: Optional[str] = None,
        inn: Optional[str] = None,
        kpp: Optional[str] = None,
        ogrn: Optional[str] = None,
        is_foreign: bool = False,
        legal_address: Optional[Dict[str, Any]] = None,
        actual_address: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> None:
        """Insert a new organization record"""
        import json

        created_dt = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()

        await pg_client.execute(
            """
            INSERT INTO customs_organizations (
                id, kontur_org_id, org_name, short_name, org_type,
                inn, kpp, ogrn, is_foreign,
                legal_address, actual_address, created_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9,
                $10::jsonb, $11::jsonb, $12
            )
            ON CONFLICT (id) DO NOTHING
            """,
            org_id, kontur_org_id, org_name, short_name, org_type,
            inn, kpp, ogrn, is_foreign,
            json.dumps(legal_address) if legal_address else None,
            json.dumps(actual_address) if actual_address else None,
            created_dt,
        )

    @staticmethod
    async def update_organization(
        org_id: uuid.UUID,
        org_name: Optional[str] = None,
        short_name: Optional[str] = None,
        org_type: Optional[int] = None,
        kpp: Optional[str] = None,
        legal_address: Optional[Dict[str, Any]] = None,
        actual_address: Optional[Dict[str, Any]] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        """Update organization details"""
        import json

        updated_dt = datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()

        # Build dynamic update query
        updates = []
        params = []
        param_idx = 1

        if org_name is not None:
            updates.append(f"org_name = ${param_idx}")
            params.append(org_name)
            param_idx += 1

        if short_name is not None:
            updates.append(f"short_name = ${param_idx}")
            params.append(short_name)
            param_idx += 1

        if org_type is not None:
            updates.append(f"org_type = ${param_idx}")
            params.append(org_type)
            param_idx += 1

        if kpp is not None:
            updates.append(f"kpp = ${param_idx}")
            params.append(kpp)
            param_idx += 1

        if legal_address is not None:
            updates.append(f"legal_address = ${param_idx}::jsonb")
            params.append(json.dumps(legal_address))
            param_idx += 1

        if actual_address is not None:
            updates.append(f"actual_address = ${param_idx}::jsonb")
            params.append(json.dumps(actual_address))
            param_idx += 1

        if not updates:
            return

        updates.append(f"updated_at = ${param_idx}")
        params.append(updated_dt)
        param_idx += 1

        params.append(org_id)

        await pg_client.execute(
            f"""
            UPDATE customs_organizations
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            """,
            *params
        )

    @staticmethod
    async def sync_from_registry(
        org_id: uuid.UUID,
        inn: Optional[str] = None,
        org_name: Optional[str] = None,
        short_name: Optional[str] = None,
        kpp: Optional[str] = None,
        ogrn: Optional[str] = None,
        kontur_org_id: Optional[str] = None,
        legal_address: Optional[Dict[str, Any]] = None,
        synced_at: Optional[str] = None,
    ) -> None:
        """Update organization with registry data (EGRUL sync)"""
        import json

        synced_dt = datetime.fromisoformat(synced_at) if synced_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_organizations
            SET inn = COALESCE($1, inn),
                org_name = COALESCE($2, org_name),
                short_name = COALESCE($3, short_name),
                kpp = COALESCE($4, kpp),
                ogrn = COALESCE($5, ogrn),
                kontur_org_id = COALESCE($6, kontur_org_id),
                legal_address = COALESCE($7::jsonb, legal_address),
                synced_at = $8,
                updated_at = $8
            WHERE id = $9
            """,
            inn, org_name, short_name, kpp, ogrn, kontur_org_id,
            json.dumps(legal_address) if legal_address else None,
            synced_dt, org_id
        )

    @staticmethod
    async def mark_deleted(
        org_id: uuid.UUID,
        deleted_at: Optional[str] = None,
    ) -> None:
        """Mark organization as deleted (soft delete)"""
        deleted_dt = datetime.fromisoformat(deleted_at) if deleted_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_organizations
            SET is_deleted = true, deleted_at = $1, updated_at = $1
            WHERE id = $2
            """,
            deleted_dt, org_id
        )

    @staticmethod
    async def link_to_kontur(
        org_id: uuid.UUID,
        kontur_org_id: str,
        linked_at: Optional[str] = None,
    ) -> None:
        """Link organization to Kontur"""
        linked_dt = datetime.fromisoformat(linked_at) if linked_at else datetime.utcnow()

        await pg_client.execute(
            """
            UPDATE customs_organizations
            SET kontur_org_id = $1, updated_at = $2
            WHERE id = $3
            """,
            kontur_org_id, linked_dt, org_id
        )

    # =========================================================================
    # Organization Query Operations (for Query Handlers)
    # =========================================================================

    @staticmethod
    async def get_organization_by_id(
        org_id: uuid.UUID,
    ) -> Optional[CommonOrganizationReadModel]:
        """Get organization by ID"""
        row = await pg_client.fetchrow(
            "SELECT * FROM customs_organizations WHERE id = $1",
            org_id
        )
        if not row:
            return None
        return CommonOrganizationReadModel(**dict(row))

    @staticmethod
    async def get_organization_by_inn(
        inn: str,
    ) -> Optional[CommonOrganizationReadModel]:
        """Get organization by INN"""
        row = await pg_client.fetchrow(
            "SELECT * FROM customs_organizations WHERE inn = $1",
            inn
        )
        if not row:
            return None
        return CommonOrganizationReadModel(**dict(row))

    @staticmethod
    async def get_organization_by_kontur_id(
        kontur_org_id: str,
    ) -> Optional[CommonOrganizationReadModel]:
        """Get organization by Kontur org ID"""
        row = await pg_client.fetchrow(
            "SELECT * FROM customs_organizations WHERE kontur_org_id = $1",
            kontur_org_id
        )
        if not row:
            return None
        return CommonOrganizationReadModel(**dict(row))

    @staticmethod
    async def list_organizations(
        limit: int = 50,
        offset: int = 0,
    ) -> List[OrganizationSummaryReadModel]:
        """List organizations"""
        rows = await pg_client.fetch(
            """
            SELECT id, kontur_org_id, org_name, short_name, inn, is_foreign
            FROM customs_organizations
            ORDER BY org_name
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )

        return [OrganizationSummaryReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def search_organizations(
        search_term: str,
        limit: int = 20,
    ) -> List[OrganizationSummaryReadModel]:
        """Search organizations by name or INN"""
        rows = await pg_client.fetch(
            """
            SELECT id, kontur_org_id, org_name, short_name, inn, is_foreign
            FROM customs_organizations
            WHERE org_name ILIKE $1 OR inn ILIKE $1
            ORDER BY org_name
            LIMIT $2
            """,
            f"%{search_term}%", limit
        )

        return [OrganizationSummaryReadModel(**dict(row)) for row in rows]


# =============================================================================
# EOF
# =============================================================================

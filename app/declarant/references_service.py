# =============================================================================
# File: app/declarant/references_service.py
# Description: Services for managing Kontur API references (customs, procedures, etc.)
# =============================================================================

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass

from app.infra.persistence import pg_client
from app.declarant.kontur_client import get_kontur_client, KonturClientError

log = logging.getLogger("wellwon.declarant.references_service")


# =============================================================================
# Helpers
# =============================================================================

def _parse_json_field(value) -> Optional[dict]:
    """Parse a JSON field that may be a string, dict, or None"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SyncResult:
    """Result of sync operation"""
    total_fetched: int
    inserted: int
    updated: int
    skipped: int
    errors: int
    sync_time: datetime


@dataclass
class CustomsOffice:
    """Customs office entity (таможенный орган)"""
    id: str
    kontur_id: str
    code: Optional[str]
    short_name: Optional[str]
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class DeclarationType:
    """Declaration type entity (тип декларации / направление перемещения)"""
    id: str
    kontur_id: int
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Procedure:
    """Customs procedure entity (таможенная процедура)"""
    id: str
    kontur_id: int
    declaration_type_id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Customs Service
# =============================================================================

class CustomsService:
    """Service for managing customs offices (таможенные органы)"""

    TABLE_NAME = "dc_customs"
    REFERENCE_NAME = "Таможенные органы"
    REFERENCE_DESCRIPTION = "Справочник таможенных органов (из Kontur API /common/v1/options/customs)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[CustomsOffice]:
        """Get all customs offices from database"""
        query = f"""
            SELECT id, kontur_id, code, short_name, full_name,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY short_name"

        rows = await pg_client.fetch(query)

        return [
            CustomsOffice(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                code=row["code"],
                short_name=row["short_name"],
                full_name=row["full_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of customs offices"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[CustomsOffice]:
        """Search customs offices by name or code"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, kontur_id, code, short_name, full_name,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (short_name ILIKE $1 OR full_name ILIKE $1 OR code ILIKE $1)
            ORDER BY short_name
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            CustomsOffice(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                code=row["code"],
                short_name=row["short_name"],
                full_name=row["full_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def sync_from_api(cls) -> SyncResult:
        """
        Sync customs offices from Kontur API

        Fetches from GET /common/v1/options/customs
        and upserts into dc_customs table.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            client = get_kontur_client()
            api_data = await client.get_customs()

            log.info(f"Fetched {len(api_data)} customs offices from Kontur API")

            for item in api_data:
                try:
                    kontur_id = str(item.get("id", ""))
                    short_name = item.get("shortName")
                    full_name = item.get("name")

                    if not kontur_id:
                        log.warning(f"Skipping customs with missing id: {item}")
                        skipped += 1
                        continue

                    # Upsert
                    result = await pg_client.execute(
                        f"""
                        INSERT INTO {cls.TABLE_NAME}
                            (kontur_id, code, short_name, full_name, is_active, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, TRUE, $5, $6)
                        ON CONFLICT (kontur_id)
                        DO UPDATE SET
                            short_name = EXCLUDED.short_name,
                            full_name = EXCLUDED.full_name,
                            is_active = TRUE,
                            updated_at = $6
                        """,
                        kontur_id,
                        None,  # code - not provided in API response
                        short_name,
                        full_name,
                        sync_time,
                        sync_time
                    )

                    if "INSERT" in result:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    log.error(f"Error processing customs {item}: {e}")
                    errors += 1

            log.info(
                f"Customs sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=len(api_data),
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during customs sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during customs sync: {e}")
            raise


# =============================================================================
# Declaration Types Service
# =============================================================================

class DeclarationTypesService:
    """Service for managing declaration types (типы деклараций / направления перемещения)"""

    TABLE_NAME = "dc_declaration_types"
    REFERENCE_NAME = "Типы деклараций"
    REFERENCE_DESCRIPTION = "Справочник направлений перемещения (из Kontur API /common/v1/options/declarationTypes)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[DeclarationType]:
        """Get all declaration types from database"""
        query = f"""
            SELECT id, kontur_id, description, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY kontur_id"

        rows = await pg_client.fetch(query)

        return [
            DeclarationType(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                description=row["description"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of declaration types"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
        Sync declaration types from Kontur API

        Fetches from GET /common/v1/options/declarationTypes
        and upserts into dc_declaration_types table.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            client = get_kontur_client()
            api_data = await client.get_declaration_types()

            log.info(f"Fetched {len(api_data)} declaration types from Kontur API")

            for item in api_data:
                try:
                    kontur_id = item.get("id")
                    description = item.get("description", "")

                    if kontur_id is None:
                        log.warning(f"Skipping declaration type with missing id: {item}")
                        skipped += 1
                        continue

                    # Upsert
                    result = await pg_client.execute(
                        f"""
                        INSERT INTO {cls.TABLE_NAME}
                            (kontur_id, description, is_active, created_at, updated_at)
                        VALUES ($1, $2, TRUE, $3, $4)
                        ON CONFLICT (kontur_id)
                        DO UPDATE SET
                            description = EXCLUDED.description,
                            is_active = TRUE,
                            updated_at = $4
                        """,
                        kontur_id,
                        description,
                        sync_time,
                        sync_time
                    )

                    if "INSERT" in result:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    log.error(f"Error processing declaration type {item}: {e}")
                    errors += 1

            log.info(
                f"Declaration types sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=len(api_data),
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during declaration types sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during declaration types sync: {e}")
            raise


# =============================================================================
# Procedures Service
# =============================================================================

class ProceduresService:
    """Service for managing customs procedures (таможенные процедуры)"""

    TABLE_NAME = "dc_procedures"
    REFERENCE_NAME = "Таможенные процедуры"
    REFERENCE_DESCRIPTION = "Справочник таможенных процедур (из Kontur API /common/v1/options/declarationProcedureTypes)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False, declaration_type_id: Optional[int] = None) -> List[Procedure]:
        """Get all procedures from database, optionally filtered by declaration type"""
        query = f"""
            SELECT id, kontur_id, declaration_type_id, code, name,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if not include_inactive:
            query += " AND is_active = TRUE"

        if declaration_type_id is not None:
            query += f" AND declaration_type_id = ${param_idx}"
            params.append(declaration_type_id)
            param_idx += 1

        query += " ORDER BY declaration_type_id, code"

        rows = await pg_client.fetch(query, *params)

        return [
            Procedure(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                declaration_type_id=row["declaration_type_id"],
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of procedures"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
        )
        return result or 0

    @classmethod
    async def get_unique_codes_count(cls) -> int:
        """Get count of unique procedure codes"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(DISTINCT code) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[Procedure]:
        """Search procedures by name or code"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, kontur_id, declaration_type_id, code, name,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (name ILIKE $1 OR code ILIKE $1)
            ORDER BY code
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            Procedure(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                declaration_type_id=row["declaration_type_id"],
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def sync_from_api(cls) -> SyncResult:
        """
        Sync procedures from Kontur API

        Fetches procedures for all known declaration types
        from GET /common/v1/options/declarationProcedureTypes
        and upserts into dc_procedures table.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0
        total_fetched = 0

        try:
            client = get_kontur_client()

            # First get all declaration types to iterate through
            declaration_types = await client.get_declaration_types()

            for decl_type in declaration_types:
                type_id = decl_type.get("id")
                if type_id is None:
                    continue

                try:
                    api_data = await client.get_declaration_procedures(type_id)
                    total_fetched += len(api_data)

                    log.info(f"Fetched {len(api_data)} procedures for type {type_id} from Kontur API")

                    for item in api_data:
                        try:
                            kontur_id = item.get("id")
                            code = item.get("code", "")
                            name = item.get("name", "")

                            if kontur_id is None or not code:
                                log.warning(f"Skipping procedure with missing fields: {item}")
                                skipped += 1
                                continue

                            # Upsert
                            result = await pg_client.execute(
                                f"""
                                INSERT INTO {cls.TABLE_NAME}
                                    (kontur_id, declaration_type_id, code, name, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, TRUE, $5, $6)
                                ON CONFLICT (kontur_id, declaration_type_id)
                                DO UPDATE SET
                                    code = EXCLUDED.code,
                                    name = EXCLUDED.name,
                                    is_active = TRUE,
                                    updated_at = $6
                                """,
                                kontur_id,
                                type_id,
                                code,
                                name,
                                sync_time,
                                sync_time
                            )

                            if "INSERT" in result:
                                inserted += 1
                            else:
                                updated += 1

                        except Exception as e:
                            log.error(f"Error processing procedure {item}: {e}")
                            errors += 1

                except Exception as e:
                    log.error(f"Error fetching procedures for type {type_id}: {e}")
                    errors += 1

            log.info(
                f"Procedures sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=total_fetched,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during procedures sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during procedures sync: {e}")
            raise


# =============================================================================
# CommonOrgs Data Classes (Контрагенты)
# =============================================================================

@dataclass
class CommonOrg:
    """Counterparty entity (контрагент)"""
    id: str
    kontur_id: str
    org_name: Optional[str]
    short_name: Optional[str]
    org_type: int  # 0=ЮЛ, 1=ИП, 2=ФЛ
    inn: Optional[str]
    kpp: Optional[str]
    ogrn: Optional[str]
    is_foreign: bool
    legal_address: Optional[dict]
    raw_data: Optional[dict]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Organization:
    """Own organization entity (своя организация)"""
    id: str
    kontur_id: str
    name: Optional[str]
    inn: Optional[str]
    kpp: Optional[str]
    ogrn: Optional[str]
    address: Optional[dict]
    raw_data: Optional[dict]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Employee:
    """Employee/Signer entity (сотрудник/подписант)"""
    id: str
    kontur_id: str
    organization_id: Optional[str]
    surname: Optional[str]
    name: Optional[str]
    patronymic: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    auth_letter_date: Optional[str]
    auth_letter_number: Optional[str]
    raw_data: Optional[dict]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# CommonOrgs Service (Контрагенты)
# =============================================================================

class CommonOrgsService:
    """Service for managing counterparties (контрагенты)"""

    TABLE_NAME = "dc_common_orgs"
    REFERENCE_NAME = "Контрагенты"
    REFERENCE_DESCRIPTION = "Справочник контрагентов (из Kontur API /common/v1/options/commonOrgs)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[CommonOrg]:
        """Get all counterparties from database"""
        query = f"""
            SELECT id, kontur_id, org_name, short_name, org_type,
                   inn, kpp, ogrn, is_foreign, legal_address, raw_data,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY short_name NULLS LAST, org_name"

        rows = await pg_client.fetch(query)

        return [
            CommonOrg(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                org_name=row["org_name"],
                short_name=row["short_name"],
                org_type=row["org_type"] or 0,
                inn=row["inn"],
                kpp=row["kpp"],
                ogrn=row["ogrn"],
                is_foreign=row["is_foreign"] or False,
                legal_address=_parse_json_field(row["legal_address"]),
                raw_data=_parse_json_field(row["raw_data"]),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of counterparties"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[CommonOrg]:
        """Search counterparties by name or INN"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, kontur_id, org_name, short_name, org_type,
                   inn, kpp, ogrn, is_foreign, legal_address, raw_data,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (org_name ILIKE $1 OR short_name ILIKE $1 OR inn ILIKE $1)
            ORDER BY short_name NULLS LAST, org_name
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            CommonOrg(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                org_name=row["org_name"],
                short_name=row["short_name"],
                org_type=row["org_type"] or 0,
                inn=row["inn"],
                kpp=row["kpp"],
                ogrn=row["ogrn"],
                is_foreign=row["is_foreign"] or False,
                legal_address=_parse_json_field(row["legal_address"]),
                raw_data=_parse_json_field(row["raw_data"]),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def sync_from_api(cls) -> SyncResult:
        """
        Sync counterparties from Kontur API

        Fetches from GET /common/v1/options/commonOrgs
        and upserts into dc_common_orgs table.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            client = get_kontur_client()
            api_data = await client.get_common_orgs()

            log.info(f"Fetched {len(api_data)} counterparties from Kontur API")

            for item in api_data:
                try:
                    kontur_id = str(item.get("id", ""))

                    if not kontur_id:
                        log.warning(f"Skipping counterparty with missing id: {item}")
                        skipped += 1
                        continue

                    org_name = item.get("orgName")
                    short_name = item.get("shortName")
                    org_type = item.get("type", 0)
                    inn = item.get("inn")
                    kpp = item.get("kpp")
                    ogrn = item.get("ogrn")
                    is_foreign = item.get("isForeign", False)
                    legal_address = item.get("legalAddress")

                    # Upsert
                    result = await pg_client.execute(
                        f"""
                        INSERT INTO {cls.TABLE_NAME}
                            (kontur_id, org_name, short_name, org_type, inn, kpp, ogrn,
                             is_foreign, legal_address, raw_data, is_active, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, TRUE, $11, $12)
                        ON CONFLICT (kontur_id)
                        DO UPDATE SET
                            org_name = EXCLUDED.org_name,
                            short_name = EXCLUDED.short_name,
                            org_type = EXCLUDED.org_type,
                            inn = EXCLUDED.inn,
                            kpp = EXCLUDED.kpp,
                            ogrn = EXCLUDED.ogrn,
                            is_foreign = EXCLUDED.is_foreign,
                            legal_address = EXCLUDED.legal_address,
                            raw_data = EXCLUDED.raw_data,
                            is_active = TRUE,
                            updated_at = $12
                        """,
                        kontur_id,
                        org_name,
                        short_name,
                        org_type,
                        inn,
                        kpp,
                        ogrn,
                        is_foreign,
                        json.dumps(legal_address) if legal_address else None,
                        json.dumps(item),
                        sync_time,
                        sync_time
                    )

                    if "INSERT" in result:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    log.error(f"Error processing counterparty {item}: {e}")
                    errors += 1

            log.info(
                f"CommonOrgs sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=len(api_data),
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during commonOrgs sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during commonOrgs sync: {e}")
            raise


# =============================================================================
# Organizations Service (Свои организации)
# =============================================================================

class OrganizationsService:
    """Service for managing own organizations (свои организации)"""

    TABLE_NAME = "dc_organizations"
    REFERENCE_NAME = "Организации"
    REFERENCE_DESCRIPTION = "Справочник организаций (из Kontur API /common/v1/options/organizations)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[Organization]:
        """Get all organizations from database"""
        query = f"""
            SELECT id, kontur_id, name, inn, kpp, ogrn, address, raw_data,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY name"

        rows = await pg_client.fetch(query)

        return [
            Organization(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                name=row["name"],
                inn=row["inn"],
                kpp=row["kpp"],
                ogrn=row["ogrn"],
                address=_parse_json_field(row["address"]),
                raw_data=_parse_json_field(row["raw_data"]),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of organizations"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
        Sync organizations from Kontur API

        Fetches from GET /common/v1/options/organizations
        and upserts into dc_organizations table.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            client = get_kontur_client()
            api_data = await client.get_organizations()

            log.info(f"Fetched {len(api_data)} organizations from Kontur API")

            for item in api_data:
                try:
                    kontur_id = str(item.get("id", ""))

                    if not kontur_id:
                        log.warning(f"Skipping organization with missing id: {item}")
                        skipped += 1
                        continue

                    name = item.get("name")
                    inn = item.get("inn")
                    kpp = item.get("kpp")
                    ogrn = item.get("ogrn")
                    address = item.get("address")

                    # Upsert
                    result = await pg_client.execute(
                        f"""
                        INSERT INTO {cls.TABLE_NAME}
                            (kontur_id, name, inn, kpp, ogrn, address, raw_data,
                             is_active, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE, $8, $9)
                        ON CONFLICT (kontur_id)
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            inn = EXCLUDED.inn,
                            kpp = EXCLUDED.kpp,
                            ogrn = EXCLUDED.ogrn,
                            address = EXCLUDED.address,
                            raw_data = EXCLUDED.raw_data,
                            is_active = TRUE,
                            updated_at = $9
                        """,
                        kontur_id,
                        name,
                        inn,
                        kpp,
                        ogrn,
                        json.dumps(address) if address else None,
                        json.dumps(item),
                        sync_time,
                        sync_time
                    )

                    if "INSERT" in result:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    log.error(f"Error processing organization {item}: {e}")
                    errors += 1

            log.info(
                f"Organizations sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=len(api_data),
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during organizations sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during organizations sync: {e}")
            raise


# =============================================================================
# Employees Service (Подписанты)
# =============================================================================

class EmployeesService:
    """Service for managing employees/signers (сотрудники/подписанты)"""

    TABLE_NAME = "dc_employees"
    REFERENCE_NAME = "Подписанты"
    REFERENCE_DESCRIPTION = "Справочник подписантов (из Kontur API /common/v1/options/employees)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False, organization_id: Optional[str] = None) -> List[Employee]:
        """Get all employees from database, optionally filtered by organization"""
        query = f"""
            SELECT id, kontur_id, organization_id, surname, name, patronymic,
                   phone, email, auth_letter_date, auth_letter_number, raw_data,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if not include_inactive:
            query += " AND is_active = TRUE"

        if organization_id:
            query += f" AND organization_id = $${param_idx}"
            params.append(organization_id)
            param_idx += 1

        query += " ORDER BY surname, name"

        rows = await pg_client.fetch(query, *params)

        return [
            Employee(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                organization_id=str(row["organization_id"]) if row["organization_id"] else None,
                surname=row["surname"],
                name=row["name"],
                patronymic=row["patronymic"],
                phone=row["phone"],
                email=row["email"],
                auth_letter_date=row["auth_letter_date"],
                auth_letter_number=row["auth_letter_number"],
                raw_data=_parse_json_field(row["raw_data"]),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of employees"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[Employee]:
        """Search employees by name"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, kontur_id, organization_id, surname, name, patronymic,
                   phone, email, auth_letter_date, auth_letter_number, raw_data,
                   is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (surname ILIKE $1 OR name ILIKE $1 OR email ILIKE $1)
            ORDER BY surname, name
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            Employee(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                organization_id=str(row["organization_id"]) if row["organization_id"] else None,
                surname=row["surname"],
                name=row["name"],
                patronymic=row["patronymic"],
                phone=row["phone"],
                email=row["email"],
                auth_letter_date=row["auth_letter_date"],
                auth_letter_number=row["auth_letter_number"],
                raw_data=_parse_json_field(row["raw_data"]),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def sync_from_api(cls) -> SyncResult:
        """
        Sync employees from Kontur API for all organizations

        First syncs organizations, then fetches employees for each.
        """
        sync_time = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0
        total_fetched = 0

        try:
            client = get_kontur_client()

            # First sync organizations to have org IDs
            await OrganizationsService.sync_from_api()

            # Get all organizations from DB
            organizations = await OrganizationsService.get_all()

            for org in organizations:
                try:
                    api_data = await client.get_employees(org.kontur_id)
                    total_fetched += len(api_data)

                    log.info(f"Fetched {len(api_data)} employees for org {org.name} from Kontur API")

                    for item in api_data:
                        try:
                            kontur_id = str(item.get("id", ""))

                            if not kontur_id:
                                skipped += 1
                                continue

                            surname = item.get("surname")
                            name = item.get("name")
                            patronymic = item.get("patronymic")
                            phone = item.get("phone")
                            email = item.get("email")
                            auth_letter_date = item.get("authLetterDate")
                            auth_letter_number = item.get("authLetterNumber")

                            # Get org UUID from our table
                            org_uuid = await pg_client.fetchval(
                                "SELECT id FROM dc_organizations WHERE kontur_id = $1",
                                org.kontur_id
                            )

                            # Upsert
                            result = await pg_client.execute(
                                f"""
                                INSERT INTO {cls.TABLE_NAME}
                                    (kontur_id, organization_id, surname, name, patronymic,
                                     phone, email, auth_letter_date, auth_letter_number,
                                     raw_data, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, TRUE, $11, $12)
                                ON CONFLICT (kontur_id, organization_id)
                                DO UPDATE SET
                                    surname = EXCLUDED.surname,
                                    name = EXCLUDED.name,
                                    patronymic = EXCLUDED.patronymic,
                                    phone = EXCLUDED.phone,
                                    email = EXCLUDED.email,
                                    auth_letter_date = EXCLUDED.auth_letter_date,
                                    auth_letter_number = EXCLUDED.auth_letter_number,
                                    raw_data = EXCLUDED.raw_data,
                                    is_active = TRUE,
                                    updated_at = $12
                                """,
                                kontur_id,
                                org_uuid,
                                surname,
                                name,
                                patronymic,
                                phone,
                                email,
                                auth_letter_date,
                                auth_letter_number,
                                json.dumps(item),
                                sync_time,
                                sync_time
                            )

                            if "INSERT" in result:
                                inserted += 1
                            else:
                                updated += 1

                        except Exception as e:
                            log.error(f"Error processing employee {item}: {e}")
                            errors += 1

                except Exception as e:
                    log.error(f"Error fetching employees for org {org.kontur_id}: {e}")
                    errors += 1

            log.info(
                f"Employees sync completed: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped, {errors} errors"
            )

            return SyncResult(
                total_fetched=total_fetched,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                errors=errors,
                sync_time=sync_time
            )

        except KonturClientError as e:
            log.error(f"Kontur API error during employees sync: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error during employees sync: {e}")
            raise


# =============================================================================
# Static Reference Data Classes
# =============================================================================

@dataclass
class PackagingGroup:
    """Packaging group entity (группа упаковки)"""
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Currency:
    """Currency entity (валюта)"""
    id: str
    code: str
    alpha_code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class EnterpriseCategory:
    """Enterprise category entity (категория предприятия)"""
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MeasurementUnit:
    """Measurement unit entity (единица измерения)"""
    id: str
    code: str
    short_name: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class DeclarationFeature:
    """Declaration feature entity (особенность декларирования)"""
    id: str
    kontur_id: Optional[int]
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class DocumentType:
    """Document type entity (вид документа)"""
    id: str
    code: str
    name: str
    ed_documents: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Packaging Groups Service (Static)
# =============================================================================

class PackagingGroupsService:
    """Service for managing packaging groups (группы упаковки)"""

    TABLE_NAME = "dc_packaging_groups"
    REFERENCE_NAME = "Группы упаковки"
    REFERENCE_DESCRIPTION = "Справочник групп упаковки (статический)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[PackagingGroup]:
        """Get all packaging groups from database"""
        query = f"""
            SELECT id, code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY code"

        rows = await pg_client.fetch(query)

        return [
            PackagingGroup(
                id=str(row["id"]),
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of packaging groups"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
        )
        return result or 0

    @classmethod
    async def get_last_update(cls) -> Optional[datetime]:
        """Get timestamp of last update"""
        result = await pg_client.fetchval(
            f"SELECT MAX(updated_at) FROM {cls.TABLE_NAME}"
        )
        return result


# =============================================================================
# Currencies Service (Static)
# =============================================================================

class CurrenciesService:
    """Service for managing currencies (валюты)"""

    TABLE_NAME = "dc_currencies"
    REFERENCE_NAME = "Валюты"
    REFERENCE_DESCRIPTION = "Справочник валют (статический)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[Currency]:
        """Get all currencies from database"""
        query = f"""
            SELECT id, code, alpha_code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY alpha_code"

        rows = await pg_client.fetch(query)

        return [
            Currency(
                id=str(row["id"]),
                code=row["code"],
                alpha_code=row["alpha_code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of currencies"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[Currency]:
        """Search currencies by code or name"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, code, alpha_code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (name ILIKE $1 OR code ILIKE $1 OR alpha_code ILIKE $1)
            ORDER BY alpha_code
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            Currency(
                id=str(row["id"]),
                code=row["code"],
                alpha_code=row["alpha_code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


# =============================================================================
# Enterprise Categories Service (Static)
# =============================================================================

class EnterpriseCategoriesService:
    """Service for managing enterprise categories (категории предприятий)"""

    TABLE_NAME = "dc_enterprise_categories"
    REFERENCE_NAME = "Категории предприятий"
    REFERENCE_DESCRIPTION = "Справочник категорий предприятий (статический)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[EnterpriseCategory]:
        """Get all enterprise categories from database"""
        query = f"""
            SELECT id, code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY code"

        rows = await pg_client.fetch(query)

        return [
            EnterpriseCategory(
                id=str(row["id"]),
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of enterprise categories"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[EnterpriseCategory]:
        """Search enterprise categories by code or name"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (name ILIKE $1 OR code ILIKE $1)
            ORDER BY code
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            EnterpriseCategory(
                id=str(row["id"]),
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


# =============================================================================
# Measurement Units Service (Static)
# =============================================================================

class MeasurementUnitsService:
    """Service for managing measurement units (единицы измерения)"""

    TABLE_NAME = "dc_measurement_units"
    REFERENCE_NAME = "Единицы измерения"
    REFERENCE_DESCRIPTION = "Справочник единиц измерения (статический)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[MeasurementUnit]:
        """Get all measurement units from database"""
        query = f"""
            SELECT id, code, short_name, full_name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY code"

        rows = await pg_client.fetch(query)

        return [
            MeasurementUnit(
                id=str(row["id"]),
                code=row["code"],
                short_name=row["short_name"],
                full_name=row["full_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of measurement units"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[MeasurementUnit]:
        """Search measurement units by code or name"""
        rows = await pg_client.fetch(
            f"""
            SELECT id, code, short_name, full_name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (short_name ILIKE $1 OR full_name ILIKE $1 OR code ILIKE $1)
            ORDER BY code
            LIMIT $2
            """,
            f"%{query}%",
            limit
        )

        return [
            MeasurementUnit(
                id=str(row["id"]),
                code=row["code"],
                short_name=row["short_name"],
                full_name=row["full_name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


# =============================================================================
# Declaration Features Service (API) - Особенности
# =============================================================================

class DeclarationFeaturesService:
    """Service for managing declaration features (особенности декларирования)"""

    TABLE_NAME = "dc_declaration_features"
    REFERENCE_NAME = "Особенности"
    REFERENCE_DESCRIPTION = "Справочник особенностей декларирования (из Kontur API /common/v1/options/declarationSingularities)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[DeclarationFeature]:
        """Get all declaration features from database"""
        query = f"""
            SELECT id, kontur_id, code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY code"

        rows = await pg_client.fetch(query)

        return [
            DeclarationFeature(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of declaration features"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
        """Sync declaration features from Kontur API"""
        client = get_kontur_client()

        try:
            api_data = await client.get_declaration_singularities()
        except KonturClientError as e:
            log.error(f"Error fetching declaration singularities from Kontur API: {e}")
            raise

        total_fetched = len(api_data)
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        for item in api_data:
            try:
                kontur_id = item.get("id")
                code = item.get("shortName") or ""
                name = item.get("name") or ""

                # Upsert by code (shortName is the unique identifier)
                result = await pg_client.fetchrow(
                    f"""
                    INSERT INTO {cls.TABLE_NAME} (kontur_id, code, name, is_active, updated_at)
                    VALUES ($1, $2, $3, TRUE, NOW())
                    ON CONFLICT (code) DO UPDATE SET
                        kontur_id = EXCLUDED.kontur_id,
                        name = EXCLUDED.name,
                        is_active = TRUE,
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS is_insert
                    """,
                    kontur_id, code, name
                )

                if result and result["is_insert"]:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                log.error(f"Error upserting declaration feature {item}: {e}")
                errors += 1

        log.info(f"Synced declaration features: {inserted} inserted, {updated} updated, {errors} errors")

        return SyncResult(
            total_fetched=total_fetched,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors,
            sync_time=datetime.now(timezone.utc)
        )

    @classmethod
    async def search(cls, query: str, limit: int = 50) -> List[DeclarationFeature]:
        """Search declaration features by code or name"""
        sql = f"""
            SELECT id, kontur_id, code, name, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (
                  code ILIKE $1
                  OR name ILIKE $1
              )
            ORDER BY code
            LIMIT $2
        """
        search_pattern = f"%{query}%"
        rows = await pg_client.fetch(sql, search_pattern, limit)

        return [
            DeclarationFeature(
                id=str(row["id"]),
                kontur_id=row["kontur_id"],
                code=row["code"],
                name=row["name"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


# =============================================================================
# Document Types Service (Static)
# =============================================================================

class DocumentTypesService:
    """Service for managing document types (виды документов)"""

    TABLE_NAME = "dc_document_types"
    REFERENCE_NAME = "Виды документов"
    REFERENCE_DESCRIPTION = "Справочник видов документов для таможенного оформления (статический)"

    @classmethod
    async def get_all(cls, include_inactive: bool = False) -> List[DocumentType]:
        """Get all document types from database"""
        query = f"""
            SELECT id, code, name, ed_documents, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
        """
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY code"

        rows = await pg_client.fetch(query)

        return [
            DocumentType(
                id=str(row["id"]),
                code=row["code"],
                name=row["name"],
                ed_documents=row["ed_documents"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @classmethod
    async def get_count(cls) -> int:
        """Get total count of document types"""
        result = await pg_client.fetchval(
            f"SELECT COUNT(*) FROM {cls.TABLE_NAME} WHERE is_active = TRUE"
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
    async def search(cls, query: str, limit: int = 50) -> List[DocumentType]:
        """Search document types by code or name"""
        sql = f"""
            SELECT id, code, name, ed_documents, is_active, created_at, updated_at
            FROM {cls.TABLE_NAME}
            WHERE is_active = TRUE
              AND (
                  code ILIKE $1
                  OR name ILIKE $1
                  OR ed_documents ILIKE $1
              )
            ORDER BY code
            LIMIT $2
        """
        search_pattern = f"%{query}%"
        rows = await pg_client.fetch(sql, search_pattern, limit)

        return [
            DocumentType(
                id=str(row["id"]),
                code=row["code"],
                name=row["name"],
                ed_documents=row["ed_documents"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

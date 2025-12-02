# =============================================================================
# File: app/infra/read_repos/company_read_repo.py
# Description: Read repository for Company domain
# =============================================================================

from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from app.config.logging_config import get_logger
from app.infra.persistence import pg_client
from app.company.read_models import (
    CompanyReadModel,
    UserCompanyReadModel,
    TelegramSupergroupReadModel,
    BalanceTransactionReadModel,
    CompanyListItemReadModel,
    UserCompanyListItemReadModel,
)

log = get_logger("wellwon.company.read_repo")


class CompanyReadRepo:
    """
    Read repository for Company domain.

    Provides read operations for company-related data from PostgreSQL read models.
    All methods are static for ease of use from projectors and query handlers.
    """

    # =========================================================================
    # Company Operations
    # =========================================================================

    @staticmethod
    async def insert_company(
        company_id: uuid.UUID,
        name: str,
        company_type: str,
        created_by: uuid.UUID,
        created_at: datetime,
        vat: Optional[str] = None,
        ogrn: Optional[str] = None,
        kpp: Optional[str] = None,
        postal_code: Optional[str] = None,
        country_id: int = 190,
        city: Optional[str] = None,
        street: Optional[str] = None,
        director: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tg_dir: Optional[str] = None,
        tg_accountant: Optional[str] = None,
        tg_manager_1: Optional[str] = None,
        tg_manager_2: Optional[str] = None,
        tg_manager_3: Optional[str] = None,
        tg_support: Optional[str] = None,
    ) -> None:
        """Insert a new company record"""
        await pg_client.execute(
            """
            INSERT INTO companies (
                id, name, company_type, created_by, created_at,
                vat, ogrn, kpp, postal_code, country_id, city, street,
                director, email, phone,
                tg_dir, tg_accountant, tg_manager_1, tg_manager_2, tg_manager_3, tg_support,
                is_active, is_deleted, balance, user_count, version
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10, $11, $12,
                $13, $14, $15,
                $16, $17, $18, $19, $20, $21,
                true, false, 0.00, 0, 1
            )
            ON CONFLICT (id) DO NOTHING
            """,
            company_id, name, company_type, created_by, created_at,
            vat, ogrn, kpp, postal_code, country_id, city, street,
            director, email, phone,
            tg_dir, tg_accountant, tg_manager_1, tg_manager_2, tg_manager_3, tg_support,
        )

    @staticmethod
    async def update_company(
        company_id: uuid.UUID,
        name: Optional[str] = None,
        company_type: Optional[str] = None,
        vat: Optional[str] = None,
        ogrn: Optional[str] = None,
        kpp: Optional[str] = None,
        postal_code: Optional[str] = None,
        country_id: Optional[int] = None,
        city: Optional[str] = None,
        street: Optional[str] = None,
        director: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tg_dir: Optional[str] = None,
        tg_accountant: Optional[str] = None,
        tg_manager_1: Optional[str] = None,
        tg_manager_2: Optional[str] = None,
        tg_manager_3: Optional[str] = None,
        tg_support: Optional[str] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update company details"""
        updates = []
        params = []
        param_idx = 1

        field_mappings = [
            ("name", name),
            ("company_type", company_type),
            ("vat", vat),
            ("ogrn", ogrn),
            ("kpp", kpp),
            ("postal_code", postal_code),
            ("country_id", country_id),
            ("city", city),
            ("street", street),
            ("director", director),
            ("email", email),
            ("phone", phone),
            ("tg_dir", tg_dir),
            ("tg_accountant", tg_accountant),
            ("tg_manager_1", tg_manager_1),
            ("tg_manager_2", tg_manager_2),
            ("tg_manager_3", tg_manager_3),
            ("tg_support", tg_support),
        ]

        for field_name, field_value in field_mappings:
            if field_value is not None:
                updates.append(f"{field_name} = ${param_idx}")
                params.append(field_value)
                param_idx += 1

        if not updates:
            return

        updates.append(f"updated_at = ${param_idx}")
        params.append(updated_at or datetime.utcnow())
        param_idx += 1

        updates.append("version = version + 1")

        params.append(company_id)

        await pg_client.execute(
            f"UPDATE companies SET {', '.join(updates)} WHERE id = ${param_idx}",
            *params
        )

    @staticmethod
    async def archive_company(
        company_id: uuid.UUID,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Archive a company (soft delete)"""
        await pg_client.execute(
            """
            UPDATE companies
            SET is_active = false, updated_at = $1, version = version + 1
            WHERE id = $2
            """,
            updated_at or datetime.utcnow(), company_id
        )

    @staticmethod
    async def restore_company(
        company_id: uuid.UUID,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Restore an archived company"""
        await pg_client.execute(
            """
            UPDATE companies
            SET is_active = true, updated_at = $1, version = version + 1
            WHERE id = $2
            """,
            updated_at or datetime.utcnow(), company_id
        )

    @staticmethod
    async def delete_company(
        company_id: uuid.UUID,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Hard delete a company and all related data (permanent deletion)"""
        # Delete user-company relationships first (FK constraint)
        await pg_client.execute(
            "DELETE FROM user_companies WHERE company_id = $1",
            company_id
        )
        # Delete company balance transactions (table may not exist yet)
        try:
            await pg_client.execute(
                "DELETE FROM company_balance_transactions WHERE company_id = $1",
                company_id
            )
        except Exception:
            pass  # Table doesn't exist yet - skip
        # Delete telegram supergroups linked to this company
        await pg_client.execute(
            "DELETE FROM telegram_supergroups WHERE company_id = $1",
            company_id
        )
        # Finally delete the company itself
        await pg_client.execute(
            "DELETE FROM companies WHERE id = $1",
            company_id
        )

    @staticmethod
    async def update_company_balance(
        company_id: uuid.UUID,
        new_balance: Decimal,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Update company balance"""
        await pg_client.execute(
            """
            UPDATE companies
            SET balance = $1, updated_at = $2, version = version + 1
            WHERE id = $3
            """,
            new_balance, updated_at or datetime.utcnow(), company_id
        )

    @staticmethod
    async def increment_user_count(company_id: uuid.UUID) -> None:
        """Increment user count"""
        await pg_client.execute(
            "UPDATE companies SET user_count = user_count + 1 WHERE id = $1",
            company_id
        )

    @staticmethod
    async def decrement_user_count(company_id: uuid.UUID) -> None:
        """Decrement user count"""
        await pg_client.execute(
            "UPDATE companies SET user_count = GREATEST(0, user_count - 1) WHERE id = $1",
            company_id
        )

    @staticmethod
    async def get_company_by_id(company_id: uuid.UUID) -> Optional[CompanyReadModel]:
        """Get company by ID"""
        row = await pg_client.fetchrow(
            "SELECT * FROM companies WHERE id = $1 AND is_deleted = false",
            company_id
        )
        if not row:
            return None
        return CompanyReadModel(**dict(row))

    @staticmethod
    async def get_company_by_vat(vat: str) -> Optional[CompanyReadModel]:
        """Get company by VAT (INN)"""
        row = await pg_client.fetchrow(
            "SELECT * FROM companies WHERE vat = $1 AND is_deleted = false",
            vat
        )
        if not row:
            return None
        return CompanyReadModel(**dict(row))

    @staticmethod
    async def get_company_by_name(
        name: str,
        company_type: Optional[str] = None,
        exact_match: bool = True,
    ) -> Optional[CompanyReadModel]:
        """
        Get company by name.

        Args:
            name: Company name to search
            company_type: Optional type filter ('company', 'project', 'individual')
            exact_match: If True, use exact match (case-insensitive). If False, use ILIKE.

        Returns:
            CompanyReadModel if found, None otherwise
        """
        if exact_match:
            if company_type:
                row = await pg_client.fetchrow(
                    """
                    SELECT * FROM companies
                    WHERE LOWER(name) = LOWER($1) AND company_type = $2 AND is_deleted = false
                    """,
                    name, company_type
                )
            else:
                row = await pg_client.fetchrow(
                    """
                    SELECT * FROM companies
                    WHERE LOWER(name) = LOWER($1) AND is_deleted = false
                    """,
                    name
                )
        else:
            if company_type:
                row = await pg_client.fetchrow(
                    """
                    SELECT * FROM companies
                    WHERE name ILIKE $1 AND company_type = $2 AND is_deleted = false
                    """,
                    f"%{name}%", company_type
                )
            else:
                row = await pg_client.fetchrow(
                    """
                    SELECT * FROM companies
                    WHERE name ILIKE $1 AND is_deleted = false
                    """,
                    f"%{name}%"
                )

        if not row:
            return None
        return CompanyReadModel(**dict(row))

    @staticmethod
    async def get_companies(
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CompanyListItemReadModel]:
        """Get all companies"""
        conditions = []
        if not include_deleted:
            conditions.append("is_deleted = false")
        if not include_archived:
            conditions.append("is_active = true")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await pg_client.fetch(
            f"""
            SELECT id, name, company_type, vat, city, user_count, balance, is_active, created_at
            FROM companies
            {where_clause}
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )

        return [CompanyListItemReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def search_companies(
        search_term: str,
        limit: int = 20,
    ) -> List[CompanyListItemReadModel]:
        """Search companies by name or VAT"""
        rows = await pg_client.fetch(
            """
            SELECT id, name, company_type, vat, city, user_count, balance, is_active, created_at
            FROM companies
            WHERE (name ILIKE $1 OR vat ILIKE $1) AND is_deleted = false AND is_active = true
            ORDER BY name
            LIMIT $2
            """,
            f"%{search_term}%", limit
        )

        return [CompanyListItemReadModel(**dict(row)) for row in rows]

    # =========================================================================
    # User-Company Relationship Operations
    # =========================================================================

    @staticmethod
    async def insert_user_company(
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        relationship_type: str,
        joined_at: datetime,
    ) -> None:
        """Insert a user-company relationship"""
        await pg_client.execute(
            """
            INSERT INTO user_companies (id, company_id, user_id, relationship_type, assigned_at, is_active)
            VALUES (gen_random_uuid(), $1, $2, $3, $4, true)
            ON CONFLICT (user_id, company_id, relationship_type) DO UPDATE SET
                is_active = true,
                updated_at = NOW()
            """,
            company_id, user_id, relationship_type, joined_at
        )

    @staticmethod
    async def update_user_company_role(
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        relationship_type: str,
    ) -> None:
        """Update user's role in company"""
        await pg_client.execute(
            """
            UPDATE user_companies
            SET relationship_type = $1
            WHERE company_id = $2 AND user_id = $3
            """,
            relationship_type, company_id, user_id
        )

    @staticmethod
    async def deactivate_user_company(
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Deactivate user-company relationship (soft delete)"""
        await pg_client.execute(
            """
            UPDATE user_companies
            SET is_active = false
            WHERE company_id = $1 AND user_id = $2
            """,
            company_id, user_id
        )

    @staticmethod
    async def get_companies_by_user(
        user_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UserCompanyListItemReadModel]:
        """Get all companies for a user"""
        active_filter = "" if include_archived else "AND c.is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT
                uc.id, uc.company_id, c.name as company_name, c.company_type,
                uc.relationship_type, uc.assigned_at as joined_at, uc.is_active
            FROM user_companies uc
            INNER JOIN companies c ON uc.company_id = c.id
            WHERE uc.user_id = $1 AND uc.is_active = true AND c.is_deleted = false {active_filter}
            ORDER BY c.name
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )

        return [UserCompanyListItemReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_company_users(
        company_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> List[UserCompanyReadModel]:
        """Get all users in a company"""
        active_filter = "" if include_inactive else "AND is_active = true"

        rows = await pg_client.fetch(
            f"""
            SELECT id, user_id, company_id, relationship_type, assigned_at as joined_at, is_active, created_at, updated_at
            FROM user_companies
            WHERE company_id = $1 {active_filter}
            ORDER BY assigned_at
            """,
            company_id
        )

        return [UserCompanyReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_user_company_relationship(
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[UserCompanyReadModel]:
        """Get user's relationship with company"""
        row = await pg_client.fetchrow(
            """
            SELECT id, company_id, user_id, relationship_type, assigned_at as joined_at, is_active, created_at, updated_at
            FROM user_companies
            WHERE company_id = $1 AND user_id = $2
            """,
            company_id, user_id
        )
        if not row:
            return None
        return UserCompanyReadModel(**dict(row))

    # =========================================================================
    # Telegram Supergroup Operations
    # =========================================================================

    @staticmethod
    async def insert_telegram_supergroup(
        company_id: uuid.UUID,
        telegram_group_id: int,
        title: str,
        username: Optional[str] = None,
        description: Optional[str] = None,
        invite_link: Optional[str] = None,
        is_forum: bool = True,
        created_at: Optional[datetime] = None,
    ) -> None:
        """Insert a Telegram supergroup.
        Note: The table uses 'id' as the telegram_group_id (BIGINT primary key).
        """
        await pg_client.execute(
            """
            INSERT INTO telegram_supergroups (
                id, company_id, title, username,
                description, invite_link, is_forum, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                company_id = $2,
                title = $3,
                username = $4,
                description = $5,
                invite_link = $6,
                updated_at = NOW()
            """,
            telegram_group_id, company_id, title, username,
            description, invite_link, is_forum, created_at or datetime.utcnow()
        )

    @staticmethod
    async def update_telegram_supergroup(
        telegram_group_id: int,
        updates_dict: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        invite_link: Optional[str] = None,
    ) -> Optional[TelegramSupergroupReadModel]:
        """Update Telegram supergroup info.

        Can be called with either:
        - updates_dict: dict with fields to update (is_active, title, description, etc.)
        - Individual keyword arguments (title, description, invite_link)

        Returns the updated record or None if not found.
        """
        updates = []
        params = []
        param_idx = 1

        # Handle dict-based updates (from API endpoint)
        if updates_dict:
            allowed_fields = {"is_active", "title", "description", "invite_link", "username", "member_count"}
            for field, value in updates_dict.items():
                if field in allowed_fields and value is not None:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
        else:
            # Handle keyword arguments (legacy)
            if title is not None:
                updates.append(f"title = ${param_idx}")
                params.append(title)
                param_idx += 1

            if description is not None:
                updates.append(f"description = ${param_idx}")
                params.append(description)
                param_idx += 1

            if invite_link is not None:
                updates.append(f"invite_link = ${param_idx}")
                params.append(invite_link)
                param_idx += 1

        if not updates:
            return None

        updates.append("updated_at = NOW()")
        params.append(telegram_group_id)

        row = await pg_client.fetchrow(
            f"UPDATE telegram_supergroups SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *",
            *params
        )

        if not row:
            return None
        return TelegramSupergroupReadModel(**dict(row))

    @staticmethod
    async def unlink_telegram_supergroup(
        company_id: uuid.UUID,
        telegram_group_id: int,
    ) -> None:
        """Unlink (delete) Telegram supergroup from company"""
        await pg_client.execute(
            """
            DELETE FROM telegram_supergroups
            WHERE company_id = $1 AND id = $2
            """,
            company_id, telegram_group_id
        )

    @staticmethod
    async def delete_telegram_supergroup(
        telegram_group_id: int,
    ) -> bool:
        """Delete Telegram supergroup by ID (regardless of company)"""
        result = await pg_client.execute(
            """
            DELETE FROM telegram_supergroups
            WHERE id = $1
            """,
            telegram_group_id
        )
        # Returns True if a row was deleted
        return result and "DELETE 1" in result

    @staticmethod
    async def get_company_telegram_supergroups(
        company_id: uuid.UUID,
    ) -> List[TelegramSupergroupReadModel]:
        """Get all Telegram supergroups for a company"""
        rows = await pg_client.fetch(
            """
            SELECT * FROM telegram_supergroups
            WHERE company_id = $1
            ORDER BY created_at
            """,
            company_id
        )

        return [TelegramSupergroupReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_company_by_telegram_group(
        telegram_group_id: int,
    ) -> Optional[CompanyReadModel]:
        """Get company by Telegram group ID.
        Note: telegram_supergroups table uses 'id' column for the Telegram group ID.
        """
        row = await pg_client.fetchrow(
            """
            SELECT c.* FROM companies c
            INNER JOIN telegram_supergroups ts ON c.id = ts.company_id
            WHERE ts.id = $1 AND c.is_deleted = false
            """,
            telegram_group_id
        )
        if not row:
            return None
        return CompanyReadModel(**dict(row))

    # =========================================================================
    # Balance Transaction Operations
    # =========================================================================

    @staticmethod
    async def insert_balance_transaction(
        transaction_id: uuid.UUID,
        company_id: uuid.UUID,
        old_balance: Decimal,
        new_balance: Decimal,
        change_amount: Decimal,
        reason: str,
        reference_id: Optional[str],
        updated_by: uuid.UUID,
        created_at: datetime,
    ) -> None:
        """Insert a balance transaction record"""
        await pg_client.execute(
            """
            INSERT INTO company_balance_transactions (
                id, company_id, old_balance, new_balance, change_amount,
                reason, reference_id, updated_by, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO NOTHING
            """,
            transaction_id, company_id, old_balance, new_balance, change_amount,
            reason, reference_id, updated_by, created_at
        )

    @staticmethod
    async def get_company_balance(company_id: uuid.UUID) -> Optional[Decimal]:
        """Get company balance"""
        result = await pg_client.fetchval(
            "SELECT balance FROM companies WHERE id = $1",
            company_id
        )
        return result

    @staticmethod
    async def get_balance_history(
        company_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BalanceTransactionReadModel]:
        """Get balance transaction history"""
        rows = await pg_client.fetch(
            """
            SELECT * FROM company_balance_transactions
            WHERE company_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            company_id, limit, offset
        )

        return [BalanceTransactionReadModel(**dict(row)) for row in rows]

    # =========================================================================
    # Telegram Supergroup Global Operations
    # =========================================================================

    @staticmethod
    async def get_all_telegram_supergroups(
        active_only: bool = True,
    ) -> List[TelegramSupergroupReadModel]:
        """Get all Telegram supergroups"""
        active_filter = "WHERE is_active = true" if active_only else ""

        rows = await pg_client.fetch(
            f"""
            SELECT * FROM telegram_supergroups
            {active_filter}
            ORDER BY title
            """
        )

        return [TelegramSupergroupReadModel(**dict(row)) for row in rows]

    @staticmethod
    async def get_telegram_supergroups_with_chat_counts() -> List[Dict[str, Any]]:
        """Get all supergroups with their chat counts"""
        rows = await pg_client.fetch(
            """
            SELECT
                ts.id,
                ts.company_id,
                ts.title,
                ts.username,
                ts.description,
                ts.invite_link,
                ts.member_count,
                ts.is_forum,
                ts.is_active,
                ts.created_at,
                COALESCE(c.name, '') as company_name,
                COUNT(DISTINCT ch.id) as chat_count
            FROM telegram_supergroups ts
            LEFT JOIN companies c ON ts.company_id = c.id
            LEFT JOIN chats ch ON ch.telegram_supergroup_id = ts.id AND ch.is_active = true
            WHERE ts.is_active = true
            GROUP BY ts.id, c.name
            ORDER BY ts.title
            """
        )

        return [dict(row) for row in rows]

    @staticmethod
    async def get_telegram_supergroup_by_id(
        telegram_group_id: int,
    ) -> Optional[TelegramSupergroupReadModel]:
        """Get Telegram supergroup by Telegram group ID"""
        row = await pg_client.fetchrow(
            """
            SELECT * FROM telegram_supergroups
            WHERE id = $1
            """,
            telegram_group_id
        )
        if not row:
            return None
        return TelegramSupergroupReadModel(**dict(row))

    @staticmethod
    async def get_telegram_supergroup(
        telegram_group_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get Telegram supergroup as dict (for handler lookups)"""
        row = await pg_client.fetchrow(
            """
            SELECT * FROM telegram_supergroups
            WHERE id = $1
            """,
            telegram_group_id
        )
        if not row:
            return None
        return dict(row)

    @staticmethod
    async def hard_delete_telegram_supergroup(
        telegram_group_id: int,
    ) -> bool:
        """Hard delete Telegram supergroup from database (permanent deletion)"""
        result = await pg_client.execute(
            """
            DELETE FROM telegram_supergroups
            WHERE id = $1
            """,
            telegram_group_id
        )
        return result and "DELETE 1" in result

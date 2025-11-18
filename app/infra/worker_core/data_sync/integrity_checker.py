# app/infra/worker_core/data_sync/integrity_checker.py
"""
Integrity Checker - Pure Validation Service for DataSyncWorker

Refactored from Data Integrity Monitor (500+ lines) to clean, focused service (200 lines).

Purpose:
- Run integrity checks on demand (NO state tracking, NO event listeners)
- Compare broker data vs database
- Return check results
- Caller decides what to do with issues (publish events, trigger recovery, etc.)

NOT responsible for:
- Recovery coordination (saga responsibility)
- Event publishing (DataSyncWorker responsibility)
- State management (DataSyncWorker responsibility)

Architecture:
- CQRS Read-Side: Uses QueryBus ONLY
- Stateless: No internal state between checks
- Clean: Single responsibility (validation)
- Reusable: Can be called from worker, API, or saga

Usage:
    checker = IntegrityChecker(query_bus, broker_ops)
    result = await checker.check_account_integrity(user_id, account_id)
    if result.issues:
        # Caller handles issues (publish events, trigger recovery)
"""

import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from uuid import UUID
from enum import Enum, auto

from pydantic import BaseModel, Field

# CQRS - Read-side only (NO service injection!)
from app.infra.cqrs.query_bus import QueryBus
from app.infra.cqrs.command_bus import CommandBus

# Queries (CQRS compliant)
from app.broker_account.queries import GetAccountByIdQuery
from app.order.queries import GetOrdersByAccountQuery
from app.position.queries import GetPositionsByAccountQuery

# Commands for fetching broker data (CQRS compliant)
from app.order.commands import FetchOrdersFromBrokerCommand
from app.broker_account.commands import RefreshAccountDataFromBrokerCommand

log = logging.getLogger("wellwon.integrity_checker")


# =============================================================================
# MODELS (Extracted from Data Integrity Monitor)
# =============================================================================

class IntegrityStatus(Enum):
    """Status of integrity check"""
    HEALTHY = auto()
    DEGRADED = auto()
    CRITICAL = auto()
    UNKNOWN = auto()


class CheckLevel(Enum):
    """Level of integrity check"""
    BASIC = "basic"      # Quick: account existence only
    STANDARD = "standard"  # Normal: accounts + balances + orders
    DEEP = "deep"        # Thorough: all checks including positions


class IssueType(Enum):
    """Types of integrity issues"""
    MISSING_ORDERS = "MISSING_ORDERS"
    ORDER_STATUS_MISMATCH = "ORDER_STATUS_MISMATCH"
    MISSING_POSITIONS = "MISSING_POSITIONS"
    POSITION_QUANTITY_MISMATCH = "POSITION_QUANTITY_MISMATCH"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"
    STALE_DATA = "STALE_DATA"


class IssueSeverity(Enum):
    """Severity levels for issues"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IntegrityIssue(BaseModel):
    """Represents a single integrity issue"""
    issue_id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    type: IssueType
    severity: IssueSeverity
    account_id: UUID
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    auto_recoverable: bool = True


class IntegrityCheckResult(BaseModel):
    """Result of an integrity check"""
    check_id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    account_id: UUID
    user_id: UUID
    broker_id: str
    status: IntegrityStatus
    level: CheckLevel = CheckLevel.STANDARD
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Issues found
    issues: List[IntegrityIssue] = Field(default_factory=list)

    # Summary counts
    missing_orders_count: int = 0
    balance_discrepancy_amount: Decimal = Decimal("0.00")
    stale_data_count: int = 0

    # Check metadata
    check_duration_ms: int = 0
    checks_performed: List[str] = Field(default_factory=list)


# =============================================================================
# INTEGRITY CHECKER SERVICE
# =============================================================================

class IntegrityChecker:
    """
    Stateless integrity validation service - CQRS COMPLIANT.

    Extracted and refactored from DataIntegrityMonitor.
    Pure validation logic without state management or event publishing.

    CQRS Compliance:
    - Uses QueryBus ONLY for reading database
    - Uses CommandBus for fetching broker data (not direct service calls!)
    - NO direct service injection
    - NO direct broker adapter calls
    """

    def __init__(
        self,
        query_bus: QueryBus,
        command_bus: CommandBus
    ):
        """
        Initialize integrity checker.

        Args:
            query_bus: For reading database state (CQRS read-side)
            command_bus: For fetching broker data via commands (CQRS write-side)
        """
        self.query_bus = query_bus
        self.command_bus = command_bus

    async def check_account_integrity(
        self,
        user_id: UUID,
        account_id: UUID,
        broker_id: str,
        level: CheckLevel = CheckLevel.STANDARD
    ) -> IntegrityCheckResult:
        """
        Run integrity checks for a single account.

        Args:
            user_id: User ID
            account_id: Account ID to check
            broker_id: Broker identifier
            level: Check thoroughness level

        Returns:
            IntegrityCheckResult with issues found (if any)
        """
        start_time = datetime.now(timezone.utc)
        issues = []
        checks_performed = []

        log.debug(f"Running {level.value} integrity check for account {account_id}")

        try:
            # Check 1: Missing orders (always run)
            if level in [CheckLevel.STANDARD, CheckLevel.DEEP]:
                order_issues = await self._check_missing_orders(user_id, account_id, broker_id)
                if order_issues:
                    issues.extend(order_issues)
                checks_performed.append("order_sync")

            # Check 2: Balance mismatch (always run)
            balance_issue = await self._check_balance_mismatch(user_id, account_id, broker_id)
            if balance_issue:
                issues.append(balance_issue)
            checks_performed.append("balance_verification")

            # Check 3: Stale data (standard and deep)
            if level in [CheckLevel.STANDARD, CheckLevel.DEEP]:
                stale_issue = await self._check_stale_data(account_id)
                if stale_issue:
                    issues.append(stale_issue)
                checks_performed.append("staleness_check")

            # Check 4: Missing positions (deep only)
            if level == CheckLevel.DEEP:
                position_issues = await self._check_missing_positions(user_id, account_id, broker_id)
                if position_issues:
                    issues.extend(position_issues)
                checks_performed.append("position_sync")

        except Exception as e:
            log.error(f"Error during integrity check for account {account_id}: {e}", exc_info=True)
            issues.append(IntegrityIssue(
                type=IssueType.STALE_DATA,
                severity=IssueSeverity.MEDIUM,
                account_id=account_id,
                description=f"Integrity check failed: {e}",
                auto_recoverable=False
            ))

        # Calculate duration
        duration = datetime.now(timezone.utc) - start_time
        duration_ms = int(duration.total_seconds() * 1000)

        # Determine overall status
        status = self._calculate_status(issues)

        # Build result
        result = IntegrityCheckResult(
            account_id=account_id,
            user_id=user_id,
            broker_id=broker_id,
            status=status,
            level=level,
            issues=issues,
            missing_orders_count=sum(1 for i in issues if i.type == IssueType.MISSING_ORDERS),
            balance_discrepancy_amount=sum(
                Decimal(i.details.get('difference', '0'))
                for i in issues if i.type == IssueType.BALANCE_MISMATCH
            ),
            stale_data_count=sum(1 for i in issues if i.type == IssueType.STALE_DATA),
            check_duration_ms=duration_ms,
            checks_performed=checks_performed
        )

        log.info(
            f"Integrity check complete for account {account_id}: "
            f"status={status.name}, issues={len(issues)}, duration={duration_ms}ms"
        )

        return result

    async def _check_missing_orders(
        self,
        user_id: UUID,
        account_id: UUID,
        broker_id: str
    ) -> List[IntegrityIssue]:
        """
        Check for orders missing from database.

        CQRS Compliant: Uses CommandBus to fetch broker data via FetchOrdersFromBrokerCommand.
        """
        issues = []

        try:
            # Get orders from database (QueryBus - CQRS read-side)
            db_orders = await self.query_bus.query(
                GetOrdersByAccountQuery(
                    account_id=account_id,
                    status_filter="open"
                )
            )

            # Get orders from broker via CommandBus (CQRS write-side)
            # This triggers FetchOrdersFromBrokerHandler which returns broker data
            fetch_result = await self.command_bus.send(
                FetchOrdersFromBrokerCommand(
                    user_id=user_id,
                    account_id=account_id,
                    status_filter="open",
                    skip_terminal=True,
                    force=False,  # Use cache if available
                    metadata={'source': 'integrity_check', 'dry_run': True}
                )
            )

            # Extract broker order IDs from result
            broker_order_ids = set(fetch_result.get('broker_order_ids', []))

            # Compare
            db_order_ids = {o.broker_order_id for o in db_orders if o.broker_order_id}

            missing_in_db = broker_order_ids - db_order_ids

            if missing_in_db:
                issues.append(IntegrityIssue(
                    type=IssueType.MISSING_ORDERS,
                    severity=IssueSeverity.HIGH,
                    account_id=account_id,
                    description=f"Found {len(missing_in_db)} orders in broker but not in database",
                    details={
                        'missing_count': len(missing_in_db),
                        'missing_order_ids': list(missing_in_db)
                    },
                    auto_recoverable=True
                ))

        except Exception as e:
            log.error(f"Error checking missing orders for {account_id}: {e}")

        return issues

    async def _check_balance_mismatch(
        self,
        user_id: UUID,
        account_id: UUID,
        broker_id: str
    ) -> Optional[IntegrityIssue]:
        """
        Check for balance discrepancies.

        CQRS Compliant: Uses CommandBus to refresh account from broker.
        """

        try:
            # Get account from database (QueryBus - read-side)
            db_account = await self.query_bus.query(
                GetAccountByIdQuery(account_id=account_id)
            )

            # Refresh account data from broker (CommandBus - write-side)
            # This returns updated account data from broker
            refresh_result = await self.command_bus.send(
                RefreshAccountDataFromBrokerCommand(
                    account_aggregate_id=account_id,
                    user_id=user_id
                )
            )

            broker_equity = Decimal(str(refresh_result.get('equity', 0)))

            # Compare equity
            db_equity = Decimal(str(db_account.equity or 0))

            difference = abs(db_equity - broker_equity)

            # Tolerance: $0.01 (1 cent)
            if difference > Decimal("0.01"):
                return IntegrityIssue(
                    type=IssueType.BALANCE_MISMATCH,
                    severity=self._classify_balance_severity(difference),
                    account_id=account_id,
                    description=f"Balance mismatch: DB=${db_equity}, Broker=${broker_equity}",
                    details={
                        'db_equity': str(db_equity),
                        'broker_equity': str(broker_equity),
                        'difference': str(difference)
                    },
                    auto_recoverable=True
                )

        except Exception as e:
            log.error(f"Error checking balance for {account_id}: {e}")

        return None

    async def _check_stale_data(self, account_id: UUID) -> Optional[IntegrityIssue]:
        """Check if account data is stale"""

        try:
            db_account = await self.query_bus.query(
                GetAccountByIdQuery(account_id=account_id)
            )

            if db_account.last_updated:
                age = datetime.now(timezone.utc) - db_account.last_updated

                # Stale if not updated in 24 hours
                if age > timedelta(hours=24):
                    return IntegrityIssue(
                        type=IssueType.STALE_DATA,
                        severity=IssueSeverity.LOW,
                        account_id=account_id,
                        description=f"Account data stale for {age.total_seconds() / 3600:.1f} hours",
                        details={'age_hours': age.total_seconds() / 3600},
                        auto_recoverable=True
                    )

        except Exception as e:
            log.error(f"Error checking stale data for {account_id}: {e}")

        return None

    async def _check_missing_positions(
        self,
        user_id: UUID,
        account_id: UUID,
        broker_id: str
    ) -> List[IntegrityIssue]:
        """
        Check for positions missing from database (deep check only).

        CQRS Compliant: Uses QueryBus for DB + CommandBus for broker data.
        """
        issues = []

        try:
            # Get positions from database (QueryBus - read-side)
            db_positions = await self.query_bus.query(
                GetPositionsByAccountQuery(account_id=account_id)
            )

            # Refresh positions from broker via CommandBus (write-side)
            # RefreshAccountData includes positions
            refresh_result = await self.command_bus.send(
                RefreshAccountDataFromBrokerCommand(
                    account_aggregate_id=account_id,
                    user_id=user_id
                )
            )

            # Extract position symbols from result
            broker_positions = refresh_result.get('positions', [])
            broker_symbols = {p.get('symbol') for p in broker_positions if p.get('symbol')}

            # Compare symbols
            db_symbols = {p.symbol for p in db_positions}

            missing_in_db = broker_symbols - db_symbols

            if missing_in_db:
                issues.append(IntegrityIssue(
                    type=IssueType.MISSING_POSITIONS,
                    severity=IssueSeverity.MEDIUM,
                    account_id=account_id,
                    description=f"Found {len(missing_in_db)} positions in broker but not in database",
                    details={
                        'missing_count': len(missing_in_db),
                        'missing_symbols': list(missing_in_db)
                    },
                    auto_recoverable=True
                ))

        except Exception as e:
            log.error(f"Error checking missing positions for {account_id}: {e}")

        return issues

    def _calculate_status(self, issues: List[IntegrityIssue]) -> IntegrityStatus:
        """Calculate overall status based on issues"""
        if not issues:
            return IntegrityStatus.HEALTHY

        # Check for critical issues
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        if critical_count > 0:
            return IntegrityStatus.CRITICAL

        # Check for high severity
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
        if high_count > 0:
            return IntegrityStatus.DEGRADED

        # Only low/medium issues
        return IntegrityStatus.DEGRADED

    def _classify_balance_severity(self, difference: Decimal) -> IssueSeverity:
        """Classify balance mismatch severity based on amount"""
        if difference > Decimal("1000"):
            return IssueSeverity.CRITICAL
        elif difference > Decimal("100"):
            return IssueSeverity.HIGH
        elif difference > Decimal("10"):
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW

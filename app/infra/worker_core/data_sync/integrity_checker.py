"""
Integrity Checker - WellWon Platform

Generic integrity validation for data consistency checks.
Validates that local data matches external API sources.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass

from app.infra.cqrs.query_bus import QueryBus

log = logging.getLogger("wellwon.data_sync.integrity_checker")


class IntegrityStatus(str, Enum):
    """Overall integrity status"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class CheckLevel(str, Enum):
    """Integrity check depth"""
    BASIC = "basic"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class IntegrityCheckResult:
    """Result of integrity check"""
    status: IntegrityStatus
    entity_type: str
    entity_id: str
    issues_found: int = 0
    issues_auto_fixed: int = 0
    check_duration_ms: int = 0
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class IntegrityChecker:
    """
    Validates data integrity between local database and external APIs.

    Use cases:
    - Check customs declaration status matches external API
    - Verify shipment tracking data is current
    - Validate document processing status
    """

    def __init__(self, query_bus: QueryBus):
        self.query_bus = query_bus

    async def check_entity_integrity(
        self,
        entity_type: str,
        entity_id: str,
        check_level: CheckLevel = CheckLevel.STANDARD
    ) -> IntegrityCheckResult:
        """
        Check integrity for a specific entity.

        Args:
            entity_type: Type of entity (customs_declaration, shipment, document)
            entity_id: Entity ID
            check_level: Depth of checking

        Returns:
            IntegrityCheckResult with status and issues found
        """
        start_time = datetime.now(timezone.utc)

        log.info(f"Checking integrity: {entity_type}:{entity_id} (level: {check_level})")

        try:
            if entity_type == "customs_declaration":
                result = await self.check_customs_integrity(entity_id, check_level)
            elif entity_type == "shipment":
                result = await self.check_shipment_integrity(entity_id, check_level)
            elif entity_type == "document":
                result = await self.check_document_integrity(entity_id, check_level)
            else:
                log.warning(f"Unknown entity_type: {entity_type}")
                return IntegrityCheckResult(
                    status=IntegrityStatus.UNKNOWN,
                    entity_type=entity_type,
                    entity_id=entity_id
                )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result.check_duration_ms = int(duration)

            return result

        except Exception as e:
            log.error(f"Integrity check failed: {e}", exc_info=True)
            return IntegrityCheckResult(
                status=IntegrityStatus.CRITICAL,
                entity_type=entity_type,
                entity_id=entity_id,
                details={"error": str(e)}
            )

    async def check_customs_integrity(
        self,
        declaration_id: str,
        check_level: CheckLevel
    ) -> IntegrityCheckResult:
        """
        Check customs declaration data integrity.

        TODO: Implement when Customs domain exists
        - Query local declaration
        - Query customs API
        - Compare status, amounts, items
        - Report discrepancies
        """
        log.debug(f"Checking customs integrity: {declaration_id}")

        return IntegrityCheckResult(
            status=IntegrityStatus.HEALTHY,
            entity_type="customs_declaration",
            entity_id=declaration_id
        )

    async def check_shipment_integrity(
        self,
        shipment_id: str,
        check_level: CheckLevel
    ) -> IntegrityCheckResult:
        """
        Check shipment tracking data integrity.

        TODO: Implement when Logistics domain exists
        - Query local shipment
        - Query logistics API
        - Compare status, location, ETA
        - Report discrepancies
        """
        log.debug(f"Checking shipment integrity: {shipment_id}")

        return IntegrityCheckResult(
            status=IntegrityStatus.HEALTHY,
            entity_type="shipment",
            entity_id=shipment_id
        )

    async def check_document_integrity(
        self,
        document_id: str,
        check_level: CheckLevel
    ) -> IntegrityCheckResult:
        """
        Check document processing integrity.

        TODO: Implement when Document domain exists
        - Query local document
        - Check AI processing status
        - Validate extracted data
        - Report issues
        """
        log.debug(f"Checking document integrity: {document_id}")

        return IntegrityCheckResult(
            status=IntegrityStatus.HEALTHY,
            entity_type="document",
            entity_id=document_id
        )

    async def batch_check_integrity(
        self,
        entities: List[Dict[str, str]],
        check_level: CheckLevel = CheckLevel.BASIC
    ) -> List[IntegrityCheckResult]:
        """
        Check integrity for multiple entities in batch.

        Args:
            entities: List of {entity_type, entity_id} dicts
            check_level: Depth of checking

        Returns:
            List of IntegrityCheckResult
        """
        results = []

        for entity in entities:
            result = await self.check_entity_integrity(
                entity_type=entity["entity_type"],
                entity_id=entity["entity_id"],
                check_level=check_level
            )
            results.append(result)

        return results

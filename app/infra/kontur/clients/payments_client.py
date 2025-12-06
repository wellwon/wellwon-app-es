# =============================================================================
# File: app/infra/kontur/clients/payments_client.py
# Description: Client for Kontur Payments API (customs duty calculations)
# Endpoints: 1
# =============================================================================

from typing import Optional
from app.config.logging_config import get_logger
from app.infra.kontur.clients.base_client import BaseClient
from app.infra.kontur.models import (
    VehiclePaymentRequest,
    VehiclePaymentResult
)

log = get_logger("wellwon.infra.kontur.payments")


class PaymentsClient(BaseClient):
    """
    Client for Payments API (customs duty and tax calculations).

    Currently supports:
    - Vehicle import payment calculations (duties, excise, VAT)

    Future: May expand to cover general goods duty calculations.
    """

    def __init__(self, http_client, config, session_refresh_callback=None):
        super().__init__(http_client, config, category="payments", session_refresh_callback=session_refresh_callback)

    async def calculate_vehicle_payments(
        self,
        request: VehiclePaymentRequest
    ) -> Optional[VehiclePaymentResult]:
        """
        Calculate customs payments for vehicle import.

        Calculates:
        - Customs duty (based on engine volume and age)
        - Excise tax (for luxury vehicles)
        - VAT (value-added tax)
        - Total amount payable

        Rates are automatically fetched from Russian customs regulations.

        Args:
            request: Vehicle payment request with:
                - vehicle_type: "passenger", "truck", etc.
                - engine_volume: Engine displacement in liters
                - year: Manufacturing year
                - customs_value: Declared value
                - currency_code: Currency (e.g., "USD", "EUR", "RUB")

        Returns:
            Payment calculation result with breakdown, or None on error

        Example:
            >>> request = VehiclePaymentRequest(
            ...     vehicle_type="passenger",
            ...     engine_volume=2.0,
            ...     year=2020,
            ...     customs_value=25000.0,
            ...     currency_code="USD"
            ... )
            >>> result = await client.calculate_vehicle_payments(request)
            >>> print(f"Total: {result.total_amount} {result.currency_code}")
        """
        if not request:
            log.warning("request is required for calculate_vehicle_payments")
            return None

        log.info(
            f"Calculating vehicle payments: {request.vehicle_type}, "
            f"{request.engine_volume}L, year {request.year}, "
            f"value {request.customs_value} {request.currency_code}"
        )

        result = await self._request(
            "POST",
            "/vehiclePayments/calculate",
            json=request.model_dump(by_alias=True, exclude_none=True)
        )

        if result:
            payment_result = VehiclePaymentResult.model_validate(result)
            log.info(
                f"Calculated payments: duty={payment_result.customs_duty}, "
                f"excise={payment_result.excise}, VAT={payment_result.vat}, "
                f"total={payment_result.total_amount} {payment_result.currency_code}"
            )
            return payment_result

        return None

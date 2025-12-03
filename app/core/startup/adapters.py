# app/core/startup/adapters.py
# =============================================================================
# File: app/core/startup/adapters.py
# Description: External adapter infrastructure initialization
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI
from app.config.kontur_config import is_kontur_configured
from app.infra.kontur.adapter import get_kontur_adapter

logger = logging.getLogger("wellwon.startup.adapters")


async def initialize_adapters(app: FastAPI) -> None:
    """
    Initialize external adapter infrastructure.

    Adapters:
    - Kontur Declarant API (customs declarations)
    - Telegram Bot API (messaging integration)
    - DaData API (company data enrichment)

    Future adapters:
    - Carrier adapters (DHL, FedEx, UPS, etc.)
    - Payment gateway adapters
    - Logistics platform integrations
    """
    logger.info("Initializing external adapters...")

    # Kontur Declarant adapter (customs)
    if is_kontur_configured():
        kontur_adapter = get_kontur_adapter()
        app.state.kontur_adapter = kontur_adapter
        logger.info("Kontur Declarant adapter initialized")
    else:
        logger.warning("Kontur not configured - customs declaration features disabled")
        logger.info("To enable: Set KONTUR_API_KEY environment variable")
        app.state.kontur_adapter = None

    # Telegram adapter (messaging)
    enable_telegram = os.getenv("ENABLE_TELEGRAM_SYNC", "true").lower() == "true"

    if enable_telegram:
        from app.infra.telegram.adapter import get_telegram_adapter

        telegram_adapter = await get_telegram_adapter()
        app.state.telegram_adapter = telegram_adapter
        logger.info("Telegram adapter initialized")
    else:
        logger.info("Telegram adapter disabled by configuration")
        app.state.telegram_adapter = None

    # DaData adapter (company lookup)
    from app.config.dadata_config import is_dadata_configured
    from app.infra.dadata.adapter import get_dadata_adapter

    if is_dadata_configured():
        dadata_adapter = get_dadata_adapter()
        app.state.dadata_adapter = dadata_adapter
        logger.info("DaData adapter initialized")
    else:
        logger.warning("DaData not configured - company lookup features disabled")
        logger.info("To enable: Set DADATA_API_KEY environment variable")
        app.state.dadata_adapter = None

    logger.info("External adapters initialized")

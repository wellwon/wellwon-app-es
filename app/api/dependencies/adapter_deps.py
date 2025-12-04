# app/api/dependencies/adapter_deps.py
# =============================================================================
# File: app/api/dependencies/adapter_deps.py
# Description: FastAPI dependencies for external adapters
# =============================================================================

from typing import Optional
from fastapi import Depends, Request, HTTPException

from app.infra.kontur.adapter import KonturAdapter
from app.config.logging_config import get_logger

log = get_logger("wellwon.api.dependencies.adapters")


def get_kontur_adapter(request: Request) -> KonturAdapter:
    """
    Get Kontur adapter from app state.

    Usage in API routes:
        @router.post("/customs/declaration")
        async def create_declaration(
            kontur: KonturAdapter = Depends(get_kontur_adapter)
        ):
            docflow = await kontur.create_docflow(request)
            return docflow

    Raises:
        HTTPException: If Kontur adapter is not configured

    Returns:
        KonturAdapter instance
    """
    kontur_adapter: Optional[KonturAdapter] = getattr(
        request.app.state,
        "kontur_adapter",
        None
    )

    if kontur_adapter is None:
        log.error("Kontur adapter not available - check KONTUR_API_KEY configuration")
        raise HTTPException(
            status_code=503,
            detail="Customs declaration service unavailable. Kontur API not configured."
        )

    return kontur_adapter


def get_kontur_adapter_optional(request: Request) -> Optional[KonturAdapter]:
    """
    Get Kontur adapter from app state (optional).

    Returns None if Kontur is not configured instead of raising an exception.

    Usage in API routes:
        @router.get("/customs/status")
        async def get_customs_status(
            kontur: Optional[KonturAdapter] = Depends(get_kontur_adapter_optional)
        ):
            if kontur is None:
                return {"available": False}
            return {"available": True}

    Returns:
        KonturAdapter instance or None
    """
    return getattr(request.app.state, "kontur_adapter", None)

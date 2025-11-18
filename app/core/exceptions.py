# app/core/exceptions.py
# =============================================================================
# File: app/core/exceptions.py
# Description: Exception handlers for FastAPI application
# =============================================================================

import os
import logging
from fastapi import Request
from app.core.fastapi_types import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.responses import JSONResponse

from app.common.exceptions.exceptions import BrokerAuthError

logger = logging.getLogger("wellwon.exceptions")


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application"""

    # Register specific exception handlers
    app.add_exception_handler(BrokerAuthError, broker_auth_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered")


async def broker_auth_exception_handler(request: Request, exc: BrokerAuthError) -> JSONResponse:
    """Handle BrokerAuthError exceptions"""
    logger.warning(f"BrokerAuthError on path {request.url.path}: {getattr(exc, 'message', str(exc))}")

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": getattr(exc, 'message', str(exc)) or "Broker authentication failed."},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors"""
    logger.warning(f"Validation error on path {request.url.path}: {exc.errors()}")

    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"],
        }

        # Handle context if present
        if "ctx" in error:
            ctx = {}
            for key, value in error["ctx"].items():
                if isinstance(value, Exception):
                    ctx[key] = str(value)
                else:
                    ctx[key] = value
            error_dict["ctx"] = ctx

        # Handle input if present
        if "input" in error:
            error_dict["input"] = error["input"]

        errors.append(error_dict)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general unhandled exceptions"""
    logger.error(f"Unhandled exception on path {request.url.path}: {str(exc)}", exc_info=True)

    # Return appropriate response based on environment
    if os.getenv("ENVIRONMENT", "development") == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
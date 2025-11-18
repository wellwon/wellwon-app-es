# app/core/middleware.py
# =============================================================================
# File: app/core/middleware.py
# Description: Middleware configuration for FastAPI application
# =============================================================================

import os
import logging
from app.core.fastapi_types import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("tradecore.middleware")


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI application"""

    # CORS Configuration
    setup_cors(app)

    # Add other middleware here as needed
    # setup_request_logging(app)
    # setup_rate_limiting(app)
    # setup_compression(app)


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware"""

    # Get allowed origins from environment variable
    cors_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    )

    # Parse and clean origins
    allowed_origins = [origin.strip() for origin in cors_origins.split(",")]

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )

    logger.info(f"CORS configured with allowed origins: {allowed_origins}")
# =============================================================================
# File: app/infra/storage/__init__.py
# Description: Storage infrastructure module
# =============================================================================

from app.infra.storage.local_adapter import LocalStorageAdapter, get_storage_adapter

__all__ = ["LocalStorageAdapter", "get_storage_adapter"]

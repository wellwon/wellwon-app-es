# =============================================================================
# File: app/user_account/read_models.py
# Description: Pydantic models for User read projections
#              for 
# UPDATED: Added missing fields to match database schema
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict, EmailStr
import uuid
from datetime import datetime


class UserAccountReadModel(BaseModel):
    """Read model for user profile information (for API responses)."""
    id: uuid.UUID
    username: str
    email: EmailStr
    role: str = "user"
    is_active: bool = True
    email_verified: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Additional profile fields
    mfa_enabled: bool = False
    security_alerts_enabled: bool = True
    last_password_change: Optional[datetime] = None

    # Computed fields
    user_id_str: str = Field(default="", description="String representation of user ID")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )

    def model_post_init(self, __context) -> None:
        """Set computed fields after initialization."""
        self.user_id_str = str(self.id)


class UserAuthDataReadModel(BaseModel):
    """Read model for internal authentication data (matches database schema)."""
    user_id: uuid.UUID = Field(alias="id")
    email: EmailStr  # ADDED - was missing
    username: str
    hashed_password: str
    hashed_secret: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: datetime  # ADDED - was missing
    updated_at: Optional[datetime] = None  # ADDED - was missing
    last_login: Optional[datetime] = None  # ADDED - was missing

    # Additional fields from database
    email_verified: bool = False
    mfa_enabled: bool = False
    security_alerts_enabled: bool = True
    last_password_change: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )


class UserRuntimeStateReadModel(BaseModel):
    """Runtime projection of user's dynamic state (stored in Redis)."""
    user_id: uuid.UUID
    account_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps asset types to account IDs"
    )
    connected_brokers: List[str] = Field(
        default_factory=list,
        description="List of connected broker:environment pairs"
    )

    # Computed properties
    @property
    def connected_broker_ids(self) -> List[str]:
        """Get unique broker IDs (without environment)."""
        return list(set(b.split(':')[0] for b in self.connected_brokers if ':' in b))

    @property
    def has_live_brokers(self) -> bool:
        """Check if user has any live environment brokers."""
        return any(':live' in b for b in self.connected_brokers)

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            uuid.UUID: lambda v: str(v)
        }
    )


class UserSummaryReadModel(BaseModel):
    """Lightweight user summary for lists and references."""
    id: uuid.UUID
    username: str
    email: EmailStr
    role: str = "user"
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v)
        }
    )

# =============================================================================
# EOF
# =============================================================================
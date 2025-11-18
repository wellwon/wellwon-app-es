# API Router Implementation Guide

## Table of Contents

1. [Introduction](#introduction)
2. [FastAPI Router Basics](#fastapi-router-basics)
3. [Router Structure](#router-structure)
4. [Step-by-Step Router Creation](#step-by-step-router-creation)
5. [CQRS Integration](#cqrs-integration)
6. [Authentication & Authorization](#authentication--authorization)
7. [Error Handling](#error-handling)
8. [Request/Response Models](#requestresponse-models)
9. [WebSocket Endpoints](#websocket-endpoints)
10. [Testing API Routers](#testing-api-routers)
11. [Complete Examples](#complete-examples)
12. [Best Practices](#best-practices)

---

## Introduction

API routers in TradeCore are FastAPI-based HTTP/WebSocket endpoints that serve as the **entry point** for client requests. They follow clean architecture principles and integrate with the CQRS pattern via `CommandBus` and `QueryBus`.

**Key Responsibilities:**
- Validate incoming HTTP requests
- Authenticate and authorize users
- Transform API models to domain commands/queries
- Route commands/queries to the appropriate bus
- Transform domain results to API responses
- Handle errors and return appropriate HTTP status codes

**What Routers Should NOT Do:**
- ❌ Contain business logic (belongs in aggregates)
- ❌ Access database directly (use QueryBus)
- ❌ Call broker adapters directly (use CommandBus)
- ❌ Implement domain rules (belongs in domain layer)

---

## FastAPI Router Basics

### What is a Router?

A `FastAPI APIRouter` is a modular component that groups related endpoints together. Multiple routers are mounted to the main FastAPI application.

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def list_items():
    return {"items": []}

@router.post("/items")
async def create_item():
    return {"status": "created"}
```

### Router Registration

Routers are registered in `app/api/__init__.py`:

```python
from fastapi import FastAPI
from app.api.routers import user_account_router, broker_connection_router

app = FastAPI()

app.include_router(
    user_account_router.router,
    prefix="/api/user",
    tags=["User Account"]
)

app.include_router(
    broker_connection_router.router,
    prefix="/api/broker-connection",
    tags=["Broker Connection"]
)
```

---

## Router Structure

### File Organization

```
app/api/
├── __init__.py                          # Router registration
├── routers/                             # All routers
│   ├── user_account_router.py          # User authentication
│   ├── broker_connection_router.py     # Broker connections
│   ├── broker_account_router.py        # Broker accounts
│   ├── wse_router.py                   # WebSocket endpoints
│   └── ...
├── models/                              # API request/response models
│   ├── user_account_api_models.py
│   ├── broker_connection_api_models.py
│   └── ...
├── wse/                                 # WebSocket Engine components
│   ├── wse_connection.py
│   ├── wse_handlers.py
│   └── ...
└── dependencies/                        # Shared dependencies
    ├── wse_dependencies.py
    └── ...
```

### Standard Router Template

```python
# app/api/routers/example_router.py

from __future__ import annotations

import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query

# API Models
from app.api.models.example_api_models import (
    CreateExampleRequest,
    ExampleResponse,
    ExampleListResponse,
)

# Security
from app.security.jwt_auth import get_current_user

# Domain Commands
from app.example_domain.commands import (
    CreateExampleCommand,
    UpdateExampleCommand,
)

# Domain Queries
from app.example_domain.queries import (
    GetExampleByIdQuery,
    GetExamplesByUserQuery,
)

# Custom Exceptions
from app.common.exceptions.exceptions import (
    ResourceNotFoundError,
    PermissionError,
)

log = logging.getLogger("tradecore.api.example_router")
router = APIRouter()

# Dependency Injection Providers
async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured in application state")
    return request.app.state.command_bus

async def get_query_bus(request: Request):
    """Get query bus from application state"""
    if not hasattr(request.app.state, 'query_bus'):
        raise RuntimeError("Query bus not configured in application state")
    return request.app.state.query_bus

# Routes go here...
```

---

## Step-by-Step Router Creation

### Step 1: Create Router File

Create a new router file in `app/api/routers/`:

```bash
touch app/api/routers/example_router.py
```

### Step 2: Import Dependencies

```python
from __future__ import annotations

import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
```

**Required imports:**
- `APIRouter` - Router class
- `Depends` - Dependency injection
- `HTTPException` - Error responses
- `status` - HTTP status codes
- `Request` - Access to request object
- `Query` - Query parameter parsing

### Step 3: Add Authentication Dependencies

```python
from app.security.jwt_auth import get_current_user

@router.get("/protected")
async def protected_endpoint(
    current_user_id: str = Depends(get_current_user)
):
    """This endpoint requires authentication"""
    return {"user_id": current_user_id}
```

**Authentication dependency:**
- `get_current_user` - Extracts user ID from JWT token
- Returns `user_id` as string (UUID format)
- Raises `HTTPException(401)` if token is invalid

### Step 4: Implement POST Endpoints (Commands)

POST endpoints execute **write operations** using the CommandBus:

```python
@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: CreateItemRequest,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """
    Create a new item.

    - **payload**: Item creation data
    - **Returns**: Created item details
    """
    log.info(f"Creating item for user {current_user_id}")
    user_id = uuid.UUID(current_user_id)

    # Create command from API payload
    command = CreateItemCommand(
        user_id=user_id,
        name=payload.name,
        description=payload.description
    )

    try:
        # Send command via command bus
        item_id = await command_bus.send(command)

        return {
            "status": "created",
            "item_id": str(item_id)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Failed to create item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item"
        )
```

**Command Pattern:**
1. Extract user ID from JWT token
2. Parse request payload
3. Create domain command
4. Send command via `CommandBus`
5. Return success response
6. Handle errors appropriately

### Step 5: Implement GET Endpoints (Queries)

GET endpoints execute **read operations** using the QueryBus:

```python
@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str,
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    """
    Get a specific item by ID.

    - **item_id**: UUID of the item
    - **Returns**: Item details
    """
    log.info(f"Getting item {item_id} for user {current_user_id}")
    user_id = uuid.UUID(current_user_id)
    item_uuid = uuid.UUID(item_id)

    # Create query
    query = GetItemByIdQuery(
        item_id=item_uuid,
        user_id=user_id
    )

    try:
        # Execute query via query bus
        item_details = await query_bus.query(query)

        if not item_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )

        # Transform to API response
        return ItemResponse(
            id=str(item_details.id),
            name=item_details.name,
            description=item_details.description,
            created_at=item_details.created_at
        )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Failed to get item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve item"
        )
```

**Query Pattern:**
1. Extract user ID from JWT token
2. Parse path/query parameters
3. Create domain query
4. Execute query via `QueryBus`
5. Transform domain result to API response
6. Handle not found and permission errors

### Step 6: Add Request/Response Pydantic Models

Create API models in `app/api/models/example_api_models.py`:

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])

class CamelModel(BaseModel):
    """BaseModel that uses camelCase aliases"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Allow snake_case on input
    )

class CreateItemRequest(CamelModel):
    """Request payload for creating an item"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class ItemResponse(CamelModel):
    """Response model for a single item"""
    id: str = Field(..., description="Item UUID")
    name: str
    description: Optional[str] = None
    created_at: datetime

class ItemListResponse(CamelModel):
    """Response model for list of items"""
    items: list[ItemResponse]
    total: int
    page: int
    page_size: int
```

**Key points:**
- Use `CamelModel` base class for camelCase JSON serialization
- Use `Field()` for validation and documentation
- All UUIDs serialized as strings
- Use `Optional` for nullable fields

### Step 7: Error Handling and Status Codes

**Standard HTTP Status Codes:**

| Code | Usage | Example |
|------|-------|---------|
| 200 | Success (GET, PATCH) | Retrieved data |
| 201 | Created (POST) | Resource created |
| 202 | Accepted (async POST) | Command accepted for processing |
| 204 | No Content (DELETE) | Resource deleted |
| 400 | Bad Request | Invalid input data |
| 401 | Unauthorized | Invalid JWT token |
| 403 | Forbidden | User lacks permission |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable Entity | Validation failed |
| 500 | Internal Server Error | Unexpected server error |
| 502 | Bad Gateway | Broker API error |

**Error Handling Pattern:**

```python
try:
    result = await command_bus.send(command)
    return {"status": "success", "result": result}

except ValueError as e:
    # Validation errors from domain
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )

except ResourceNotFoundError as e:
    # Domain resource not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(e)
    )

except PermissionError as e:
    # User lacks permission
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(e)
    )

except InvalidOperationError as e:
    # Business rule violation
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(e)
    )

except BrokerRequestError as e:
    # Broker API error
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Broker error: {str(e)}"
    )

except Exception as e:
    # Unexpected error
    log.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred"
    )
```

### Step 8: Register Router in `app/api/__init__.py`

```python
# app/api/__init__.py

from fastapi import FastAPI
from app.api.routers import example_router

def register_routers(app: FastAPI):
    """Register all API routers"""

    app.include_router(
        example_router.router,
        prefix="/api/example",
        tags=["Example"]
    )
```

### Step 9: Add OpenAPI Documentation

Add docstrings and metadata to endpoints:

```python
@router.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
    description="Creates a new item for the authenticated user",
    responses={
        201: {"description": "Item created successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def create_item(
    payload: CreateItemRequest,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    """
    Create a new item with the following information:

    - **name**: Item name (required, 1-100 characters)
    - **description**: Item description (optional, max 500 characters)

    Returns the created item with ID and timestamp.
    """
    pass
```

---

## CQRS Integration

### CommandBus Integration

**Commands** represent **write operations** (create, update, delete):

```python
# 1. Define command in domain layer
from pydantic import BaseModel
from uuid import UUID

class CreateOrderCommand(BaseModel):
    user_id: UUID
    symbol: str
    quantity: int
    order_type: str
    price: float | None = None

# 2. Send command from router
from app.order.commands import CreateOrderCommand

@router.post("/orders")
async def create_order(
    payload: CreateOrderPayload,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus)
):
    command = CreateOrderCommand(
        user_id=uuid.UUID(current_user_id),
        symbol=payload.symbol,
        quantity=payload.quantity,
        order_type=payload.order_type,
        price=payload.price
    )

    order_id = await command_bus.send(command)
    return {"order_id": str(order_id)}
```

**Command Flow:**
```
API Request → Router → CommandBus → CommandHandler → Aggregate → Events
```

### QueryBus Integration

**Queries** represent **read operations** (fetch data):

```python
# 1. Define query in domain layer
from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class GetOrdersByUserQuery(BaseModel):
    user_id: UUID
    status: Optional[str] = None
    limit: int = 50

# 2. Execute query from router
from app.order.queries import GetOrdersByUserQuery, OrderDetails

@router.get("/orders")
async def list_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    query = GetOrdersByUserQuery(
        user_id=uuid.UUID(current_user_id),
        status=status,
        limit=limit
    )

    orders: list[OrderDetails] = await query_bus.query(query)

    return {
        "orders": [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "quantity": o.quantity,
                "status": o.status
            }
            for o in orders
        ]
    }
```

**Query Flow:**
```
API Request → Router → QueryBus → QueryHandler → Read Model → Results
```

### When to Use Commands vs Queries

| Operation | Use | Example |
|-----------|-----|---------|
| Create resource | Command | `CreateUserCommand` |
| Update resource | Command | `UpdatePositionCommand` |
| Delete resource | Command | `DeleteAccountCommand` |
| Fetch single resource | Query | `GetUserByIdQuery` |
| List resources | Query | `GetOrdersByUserQuery` |
| Search/filter | Query | `SearchSymbolsQuery` |
| Aggregation | Query | `GetPortfolioSummaryQuery` |

---

## Authentication & Authorization

### JWT Authentication

TradeCore uses JWT tokens for authentication:

```python
from app.security.jwt_auth import get_current_user

@router.get("/protected")
async def protected_endpoint(
    current_user_id: str = Depends(get_current_user)
):
    """
    This endpoint requires a valid JWT token.
    Token must be provided in Authorization header:
    Authorization: Bearer <token>
    """
    user_id = uuid.UUID(current_user_id)
    return {"user_id": str(user_id)}
```

**JWT Token Structure:**
```json
{
  "sub": "user-uuid",
  "username": "johndoe",
  "role": "user",
  "session_id": "session-uuid",
  "fp": "fingerprint-hash",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### Public Endpoints (No Authentication)

Endpoints that don't require authentication:

```python
@router.post("/login")
async def login(
    payload: AuthRequest,
    command_bus=Depends(get_command_bus)
):
    """Public endpoint - no authentication required"""
    # Login logic...
    pass

@router.get("/health")
async def health_check():
    """Public endpoint - health check"""
    return {"status": "healthy"}
```

### Authorization (Permission Checking)

Check permissions within command/query handlers:

```python
@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus)
):
    """Delete an item - checks ownership"""
    user_id = uuid.UUID(current_user_id)
    item_uuid = uuid.UUID(item_id)

    # First verify ownership via query
    verify_query = GetItemByIdQuery(
        item_id=item_uuid,
        user_id=user_id
    )

    item = await query_bus.query(verify_query)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    if item.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this item"
        )

    # Now safe to delete
    command = DeleteItemCommand(item_id=item_uuid, user_id=user_id)
    await command_bus.send(command)

    return {"status": "deleted"}
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Custom Exception Mapping

Map domain exceptions to HTTP exceptions:

```python
from app.common.exceptions.exceptions import (
    ResourceNotFoundError,
    PermissionError,
    InvalidOperationError,
    BrokerRequestError
)

@router.get("/items/{item_id}")
async def get_item(item_id: str, ...):
    try:
        result = await query_bus.query(query)
        return result

    except ResourceNotFoundError as e:
        # 404 Not Found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except PermissionError as e:
        # 403 Forbidden
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )

    except InvalidOperationError as e:
        # 409 Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    except BrokerRequestError as e:
        # 502 Bad Gateway
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Broker error: {str(e)}"
        )

    except ValueError as e:
        # 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # 500 Internal Server Error
        log.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
```

### Validation Errors

FastAPI automatically handles Pydantic validation errors:

```python
from pydantic import BaseModel, Field, validator

class CreateOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    quantity: int = Field(..., gt=0, le=10000)
    price: float | None = Field(None, ge=0)

    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.isupper():
            raise ValueError('Symbol must be uppercase')
        return v
```

If validation fails, FastAPI returns:
```json
{
  "detail": [
    {
      "loc": ["body", "quantity"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt"
    }
  ]
}
```

---

## Request/Response Models

### CamelCase Conversion

Frontend uses camelCase, Python uses snake_case. Use `CamelModel`:

```python
from pydantic import BaseModel, Field, ConfigDict

def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])

class CamelModel(BaseModel):
    """Base model with camelCase serialization"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Accept both snake_case and camelCase
    )

class UserProfileResponse(CamelModel):
    """
    Python: user_id, created_at
    JSON:   userId, createdAt
    """
    user_id: str
    username: str
    created_at: str
```

**JSON Output:**
```json
{
  "userId": "123e4567-e89b-12d3-a456-426614174000",
  "username": "johndoe",
  "createdAt": "2025-01-01T00:00:00Z"
}
```

### Pagination Support

```python
class PaginatedRequest(CamelModel):
    """Standard pagination parameters"""
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=100)
    sort_by: str | None = None
    sort_order: str = Field("asc", pattern="^(asc|desc)$")

class PaginatedResponse(CamelModel):
    """Standard pagination response"""
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.get("/items", response_model=PaginatedResponse)
async def list_items_paginated(
    pagination: PaginatedRequest = Depends(),
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    query = GetItemsQuery(
        user_id=uuid.UUID(current_user_id),
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order
    )

    result = await query_bus.query(query)

    return PaginatedResponse(
        items=[item.dict() for item in result.items],
        total=result.total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(result.total + pagination.page_size - 1) // pagination.page_size
    )
```

### Filtering Support

```python
from typing import Optional
from datetime import datetime

class OrderFilters(CamelModel):
    """Filter parameters for orders"""
    status: Optional[str] = None
    symbol: Optional[str] = None
    order_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

@router.get("/orders")
async def list_orders_filtered(
    filters: OrderFilters = Depends(),
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    query = GetOrdersQuery(
        user_id=uuid.UUID(current_user_id),
        status=filters.status,
        symbol=filters.symbol,
        order_type=filters.order_type,
        from_date=filters.from_date,
        to_date=filters.to_date
    )

    orders = await query_bus.query(query)

    return {"orders": orders}
```

---

## WebSocket Endpoints

TradeCore uses WebSocket for real-time bidirectional communication.

### WebSocket Router Example

```python
# app/api/routers/wse_router.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Header
from app.api.wse import WSEConnection, WSEHandler
from app.security.jwt_auth import JwtTokenManager

router = APIRouter()

@router.websocket("/ws/events")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT token"),
    authorization: Optional[str] = Header(None),
    protocol_version: Optional[int] = Query(2),
):
    """
    WebSocket endpoint for real-time events.

    Authentication via:
    - Query parameter: ?token=<jwt>
    - Header: Authorization: Bearer <jwt>
    """

    # Accept connection
    await websocket.accept()

    # Extract and validate token
    token_to_validate = token or (
        authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    )

    if not token_to_validate:
        await websocket.send_json({
            't': 'error',
            'p': {'message': 'Authentication required', 'code': 'AUTH_FAILED'}
        })
        await websocket.close(code=4401, reason="Authentication required")
        return

    # Validate JWT token
    token_manager = JwtTokenManager()
    try:
        payload = token_manager.decode_token_payload(token_to_validate)
        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Invalid token")

    except Exception as e:
        await websocket.send_json({
            't': 'error',
            'p': {'message': f'Authentication failed: {str(e)}', 'code': 'AUTH_FAILED'}
        })
        await websocket.close(code=4401, reason="Invalid token")
        return

    # Create connection
    conn_id = f"ws_{user_id[:8]}_{uuid.uuid4().hex[:8]}"

    connection = WSEConnection(
        conn_id=conn_id,
        user_id=user_id,
        ws=websocket,
        protocol_version=protocol_version
    )

    # Initialize and send ready
    await connection.initialize()
    await connection.send_message({
        't': 'server_ready',
        'p': {
            'message': 'Connected',
            'connection_id': conn_id,
            'protocol_version': protocol_version
        }
    })

    try:
        # Message loop
        while connection._running:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=1.0
                )

                if message['type'] == 'websocket.receive':
                    if 'text' in message:
                        data = message['text']
                        parsed = await connection.handle_incoming(data)

                        if parsed:
                            # Handle message (subscribe, unsubscribe, etc.)
                            await message_handler.handle_message(parsed)

                elif message['type'] == 'websocket.disconnect':
                    break

            except asyncio.TimeoutError:
                continue

            except WebSocketDisconnect:
                break

    finally:
        await connection.cleanup()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1000)
```

### WebSocket Message Protocol

**Client → Server Messages:**

```typescript
// Subscribe to topics
{
  "t": "subscription",
  "p": {
    "action": "subscribe",
    "topics": ["broker_connection_events", "order_events"]
  }
}

// Unsubscribe from topics
{
  "t": "subscription",
  "p": {
    "action": "unsubscribe",
    "topics": ["order_events"]
  }
}

// Request snapshot
{
  "t": "request_snapshot",
  "p": {}
}

// Ping
{
  "t": "ping",
  "p": {}
}
```

**Server → Client Messages:**

```typescript
// Server ready
{
  "t": "server_ready",
  "p": {
    "message": "Connected",
    "connection_id": "ws_12345678_abcdef12",
    "protocol_version": 2
  }
}

// Domain event
{
  "t": "broker_connection_events",
  "p": {
    "event_type": "BrokerConnectionEstablished",
    "broker_id": "alpaca",
    "environment": "paper",
    "timestamp": "2025-01-01T00:00:00Z"
  }
}

// Error
{
  "t": "error",
  "p": {
    "message": "Subscription failed",
    "code": "SUBSCRIPTION_ERROR",
    "recoverable": true
  }
}

// Pong
{
  "t": "pong",
  "p": {}
}
```

---

## Testing API Routers

### Unit Testing with pytest

```python
# tests/unit/api/test_example_router.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from uuid import uuid4

from app.server import app
from app.infra.cqrs.command_bus import CommandBus
from app.infra.cqrs.query_bus import QueryBus

@pytest.fixture
def mock_command_bus():
    """Mock command bus"""
    bus = AsyncMock(spec=CommandBus)
    return bus

@pytest.fixture
def mock_query_bus():
    """Mock query bus"""
    bus = AsyncMock(spec=QueryBus)
    return bus

@pytest.fixture
def authenticated_client(mock_command_bus, mock_query_bus):
    """Test client with mocked dependencies"""
    app.state.command_bus = mock_command_bus
    app.state.query_bus = mock_query_bus

    client = TestClient(app)

    # Mock JWT token
    token = "mock-jwt-token"
    client.headers = {"Authorization": f"Bearer {token}"}

    return client

def test_create_item_success(authenticated_client, mock_command_bus):
    """Test successful item creation"""
    # Arrange
    item_id = uuid4()
    mock_command_bus.send.return_value = item_id

    payload = {
        "name": "Test Item",
        "description": "Test description"
    }

    # Act
    response = authenticated_client.post("/api/items", json=payload)

    # Assert
    assert response.status_code == 201
    assert response.json()["itemId"] == str(item_id)
    mock_command_bus.send.assert_called_once()

def test_get_item_not_found(authenticated_client, mock_query_bus):
    """Test getting non-existent item"""
    # Arrange
    mock_query_bus.query.return_value = None

    # Act
    response = authenticated_client.get("/api/items/123e4567-e89b-12d3-a456-426614174000")

    # Assert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_create_item_unauthorized(authenticated_client):
    """Test unauthorized access"""
    # Arrange
    client = TestClient(app)  # No auth header

    payload = {"name": "Test Item"}

    # Act
    response = client.post("/api/items", json=payload)

    # Assert
    assert response.status_code == 401
```

### Integration Testing

```python
# tests/integration/test_item_api_integration.py

import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_and_get_item_integration(
    authenticated_client,
    command_bus,
    query_bus
):
    """Full integration test: create and retrieve item"""

    # Create item
    create_payload = {
        "name": "Integration Test Item",
        "description": "Created during integration test"
    }

    create_response = authenticated_client.post("/api/items", json=create_payload)
    assert create_response.status_code == 201

    item_id = create_response.json()["itemId"]

    # Retrieve item
    get_response = authenticated_client.get(f"/api/items/{item_id}")
    assert get_response.status_code == 200

    item_data = get_response.json()
    assert item_data["id"] == item_id
    assert item_data["name"] == create_payload["name"]
    assert item_data["description"] == create_payload["description"]
```

---

## Complete Examples

### Example 1: User Account Router (Authentication)

```python
# app/api/routers/user_account_router.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from app.api.models.user_account_api_models import (
    AuthRequest,
    AuthResponse,
    RegisterRequest,
    UserProfileResponse,
)
from app.security.jwt_auth import JwtTokenManager, get_current_user
from app.user_account.commands import (
    CreateUserAccountCommand,
    AuthenticateUserCommand,
)
from app.user_account.queries import GetUserProfileQuery

router = APIRouter()

@router.post("/login", response_model=AuthResponse)
async def login(
    payload: AuthRequest,
    request: Request,
    response: Response,
    command_bus=Depends(get_command_bus)
):
    """User login endpoint"""
    cmd = AuthenticateUserCommand(
        username=payload.username,
        password=payload.password
    )

    try:
        auth_result = await command_bus.send(cmd)
        user_id, username, role = auth_result

        # Create JWT tokens
        jwt_manager = JwtTokenManager()
        access_token = jwt_manager.create_access_token(
            subject=str(user_id),
            additional_claims={"username": username, "role": role}
        )

        return AuthResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=900
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    command_bus=Depends(get_command_bus)
):
    """User registration endpoint"""
    cmd = CreateUserAccountCommand(
        user_id=uuid4(),
        username=payload.username,
        email=payload.email,
        password=payload.password,
        secret=payload.secret
    )

    try:
        await command_bus.send(cmd)
        return {"status": "success", "message": "User registered"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    """Get current user profile"""
    query = GetUserProfileQuery(user_id=uuid.UUID(current_user_id))
    profile = await query_bus.query(query)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserProfileResponse(
        user_id=str(profile.id),
        username=profile.username,
        email=profile.email,
        role=profile.role,
        created_at=profile.created_at
    )
```

### Example 2: Broker Connection Router (OAuth Flow)

```python
# app/api/routers/broker_connection_router.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.api.models.broker_connection_api_models import (
    ConnectBrokerRequestPayload,
    ConnectedBrokerInfoResponse,
)
from app.broker_connection.commands import InitiateBrokerConnectionCommand
from app.broker_connection.queries import GetAllUserBrokerConnectionsQuery

router = APIRouter()

@router.post("/connect", status_code=status.HTTP_200_OK)
async def connect_broker(
    payload: ConnectBrokerRequestPayload,
    current_user_id: str = Depends(get_current_user),
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus)
):
    """
    Initiate broker connection.
    Returns OAuth URL if OAuth is required.
    """
    user_id = uuid.UUID(current_user_id)

    # Extract credentials
    api_key = api_secret = None
    oauth_required = False

    if payload.credentials:
        api_key = getattr(payload.credentials, 'api_key', None)
        api_secret = getattr(payload.credentials, 'secret_key', None)

    if payload.auth_method == 'oauth':
        oauth_required = True

    # Create connection command
    command = InitiateBrokerConnectionCommand(
        user_id=user_id,
        broker_id=payload.broker_id.value,
        environment=payload.environment.value,
        api_key=api_key if not oauth_required else None,
        api_secret=api_secret if not oauth_required else None,
        auth_method=payload.auth_method or 'api_key'
    )

    try:
        connection_id = await command_bus.send(command)

        if oauth_required:
            return {
                "requires_oauth": True,
                "broker_connection_id": str(connection_id),
                "message": f"OAuth required for {payload.broker_id.value}"
            }
        else:
            return {
                "status": "success",
                "connection_id": str(connection_id),
                "message": "Connection established"
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.get("/connection_status", response_model=list[ConnectedBrokerInfoResponse])
async def get_connection_status(
    current_user_id: str = Depends(get_current_user),
    query_bus=Depends(get_query_bus)
):
    """Get status of all broker connections"""
    query = GetAllUserBrokerConnectionsQuery(
        user_id=uuid.UUID(current_user_id),
        include_disconnected=False
    )

    connections = await query_bus.query(query)

    response = []
    for conn in connections:
        response.append(ConnectedBrokerInfoResponse(
            id=str(conn.id),
            broker_id=conn.broker_id,
            name=conn.broker_name,
            environment=conn.environment,
            status=conn.last_connection_status,
            reauth_required=conn.reauth_required,
            connected=conn.connected,
            last_connected_at=conn.last_connected_at.isoformat() if conn.last_connected_at else None
        ))

    return response
```

---

## Best Practices

### 1. **Separation of Concerns**

✅ **DO:**
- Routers handle HTTP concerns only
- Business logic in domain aggregates
- Data access via QueryBus/CommandBus

❌ **DON'T:**
- Put business logic in routers
- Access database directly from routers
- Call broker adapters directly

### 2. **Error Handling**

✅ **DO:**
- Use specific HTTP status codes
- Map domain exceptions to HTTP exceptions
- Log errors with context
- Return user-friendly error messages

❌ **DON'T:**
- Return generic 500 errors for everything
- Expose internal errors to clients
- Ignore exceptions

### 3. **Authentication**

✅ **DO:**
- Always validate JWT tokens for protected endpoints
- Check permissions in command/query handlers
- Use `get_current_user` dependency

❌ **DON'T:**
- Skip authentication checks
- Trust client-provided user IDs
- Implement custom JWT validation (use `JwtTokenManager`)

### 4. **Request/Response Models**

✅ **DO:**
- Use Pydantic models for validation
- Use `CamelModel` for camelCase JSON
- Serialize UUIDs as strings
- Add Field() descriptions

❌ **DON'T:**
- Use raw dictionaries
- Return domain models directly
- Mix snake_case and camelCase

### 5. **Async/Await**

✅ **DO:**
- All route handlers must be `async def`
- Use `await` for I/O operations
- Use `asyncio.gather()` for concurrent operations

❌ **DON'T:**
- Use blocking calls in async handlers
- Mix sync and async code incorrectly

### 6. **Logging**

✅ **DO:**
- Log important operations (create, update, delete)
- Log errors with stack traces (`exc_info=True`)
- Use structured logging with context

❌ **DON'T:**
- Log sensitive data (passwords, tokens)
- Over-log (every request)
- Use print statements

### 7. **Documentation**

✅ **DO:**
- Add docstrings to all endpoints
- Use `response_model` for type hints
- Document error responses
- Use `summary` and `description` parameters

❌ **DON'T:**
- Leave endpoints undocumented
- Use generic descriptions

### 8. **Testing**

✅ **DO:**
- Write unit tests for routers
- Mock CommandBus/QueryBus
- Test error cases
- Write integration tests for critical paths

❌ **DON'T:**
- Skip testing
- Test only happy paths
- Ignore edge cases

---

## Summary

This guide covered:

1. ✅ **FastAPI Router Basics** - What routers are and how they work
2. ✅ **Router Structure** - File organization and standard template
3. ✅ **Step-by-Step Creation** - 9 steps to create a complete router
4. ✅ **CQRS Integration** - CommandBus and QueryBus usage
5. ✅ **Authentication** - JWT tokens and authorization
6. ✅ **Error Handling** - HTTP status codes and exception mapping
7. ✅ **Request/Response Models** - Pydantic models and camelCase
8. ✅ **WebSocket Endpoints** - Real-time communication
9. ✅ **Testing** - Unit and integration testing patterns
10. ✅ **Complete Examples** - Production-ready router implementations
11. ✅ **Best Practices** - Do's and don'ts

**Next Steps:**
- Read `01_DOMAIN_CREATION_TEMPLATE.md` for domain layer
- Read `02_CQRS_HANDBOOK.md` for CQRS patterns
- Study existing routers in `app/api/routers/`
- Practice by creating a new router

**Related Documentation:**
- `/docs/cqrs.md` - CQRS architecture overview
- `/docs/mvp/DOMAIN_IMPLEMENTATION_BEST_PRACTICES.md` - Domain patterns
- FastAPI documentation: https://fastapi.tiangolo.com

# =============================================================================
# File: app/chat/query_handlers/template_query_handlers.py
# Description: Query handlers for Message Templates - CQRS COMPLIANT
#
# All query handlers use ChatReadRepo via HandlerDependencies.
# Never import pg_client or database pools directly in handlers.
# =============================================================================

from __future__ import annotations

import json
import logging
from typing import Optional, TYPE_CHECKING

from app.infra.cqrs.cqrs_decorators import cached_query_handler
from app.common.base.base_query_handler import BaseQueryHandler
from app.chat.queries import (
    GetAllTemplatesQuery,
    GetTemplateByIdQuery,
    GetTemplatesByCategoryQuery,
    MessageTemplateDetail,
)

if TYPE_CHECKING:
    from app.infra.cqrs.handler_dependencies import HandlerDependencies

log = logging.getLogger("wellwon.chat.query_handlers.template")


# =============================================================================
# Query Handlers - Using ChatReadRepo via deps
# =============================================================================

@cached_query_handler(GetAllTemplatesQuery, ttl=300)
class GetAllTemplatesQueryHandler(BaseQueryHandler[GetAllTemplatesQuery, list[MessageTemplateDetail]]):
    """Handler for GetAllTemplatesQuery - uses ChatReadRepo via deps"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo = deps.chat_read_repo

    async def handle(self, query: GetAllTemplatesQuery) -> list[MessageTemplateDetail]:
        rows = await self.chat_read_repo.get_all_templates(active_only=query.active_only)
        return [self._row_to_detail(row) for row in rows]

    def _row_to_detail(self, row) -> MessageTemplateDetail:
        template_data = row['template_data']
        if isinstance(template_data, str):
            template_data = json.loads(template_data)

        return MessageTemplateDetail(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            category=row['category'],
            template_data=template_data,
            image_url=row['image_url'],
            created_by=row['created_by'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


@cached_query_handler(GetTemplateByIdQuery, ttl=300)
class GetTemplateByIdQueryHandler(BaseQueryHandler[GetTemplateByIdQuery, Optional[MessageTemplateDetail]]):
    """Handler for GetTemplateByIdQuery - uses ChatReadRepo via deps"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo = deps.chat_read_repo

    async def handle(self, query: GetTemplateByIdQuery) -> Optional[MessageTemplateDetail]:
        row = await self.chat_read_repo.get_template_by_id(query.template_id)
        if not row:
            return None

        template_data = row['template_data']
        if isinstance(template_data, str):
            template_data = json.loads(template_data)

        return MessageTemplateDetail(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            category=row['category'],
            template_data=template_data,
            image_url=row['image_url'],
            created_by=row['created_by'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


@cached_query_handler(GetTemplatesByCategoryQuery, ttl=300)
class GetTemplatesByCategoryQueryHandler(BaseQueryHandler[GetTemplatesByCategoryQuery, list[MessageTemplateDetail]]):
    """Handler for GetTemplatesByCategoryQuery - uses ChatReadRepo via deps"""

    def __init__(self, deps: 'HandlerDependencies'):
        super().__init__()
        self.chat_read_repo = deps.chat_read_repo

    async def handle(self, query: GetTemplatesByCategoryQuery) -> list[MessageTemplateDetail]:
        rows = await self.chat_read_repo.get_templates_by_category(
            category=query.category,
            active_only=query.active_only
        )
        return [self._row_to_detail(row) for row in rows]

    def _row_to_detail(self, row) -> MessageTemplateDetail:
        template_data = row['template_data']
        if isinstance(template_data, str):
            template_data = json.loads(template_data)

        return MessageTemplateDetail(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            category=row['category'],
            template_data=template_data,
            image_url=row['image_url'],
            created_by=row['created_by'],
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )

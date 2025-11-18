# app/infra/cqrs/decorators.py
"""
Auto-registration decorators for CQRS handlers
Provides automatic handler discovery and registration
"""
from typing import Type, Dict, Any, Callable, Optional, List, Set
from dataclasses import dataclass
import logging
import inspect
from functools import wraps

log = logging.getLogger("wellwon.cqrs.decorators")

# Global registries for handlers
_COMMAND_HANDLERS: Dict[Type, Type] = {}
_QUERY_HANDLERS: Dict[Type, Type] = {}

# Track which modules have been imported
_IMPORTED_MODULES: Set[str] = set()


@dataclass
class HandlerMetadata:
    """Metadata for registered handlers"""
    handler_class: Type
    message_type: Type
    module: str
    requires_deps: List[str]


def command_handler(command_type: Type):
    """
    Decorator for command handler auto-registration

    Usage:
        @command_handler(CreateUserCommand)
        class CreateUserHandler(BaseCommandHandler):
            def __init__(self, deps):
                self.user_service = deps.user_service

            async def handle(self, command: CreateUserCommand):
                ...
    """

    def decorator(handler_class: Type):
        # CRITICAL: Check for duplicate handler registration
        if command_type in _COMMAND_HANDLERS:
            existing_handler = _COMMAND_HANDLERS[command_type]
            log.error(
                f"🔴 DUPLICATE COMMAND HANDLER DETECTED!\n"
                f"  Command: {command_type.__name__}\n"
                f"  Existing Handler: {existing_handler.__name__} ({existing_handler.__module__})\n"
                f"  New Handler: {handler_class.__name__} ({handler_class.__module__})\n"
                f"  This violates CQRS principles - each command must have exactly ONE handler."
            )
            raise ValueError(
                f"Duplicate command handler: {command_type.__name__} already handled by "
                f"{existing_handler.__name__} in {existing_handler.__module__}"
            )

        # Store handler in registry
        _COMMAND_HANDLERS[command_type] = handler_class

        # Add metadata to handler class
        handler_class._command_type = command_type
        handler_class._handler_type = 'command'
        handler_class._module = handler_class.__module__

        # Analyze dependencies from __init__
        try:
            init_method = inspect.signature(handler_class.__init__)
            params = list(init_method.parameters.keys())
            if 'self' in params:
                params.remove('self')
            handler_class._required_deps = params
        except:
            handler_class._required_deps = ['deps']

        log.debug(
            f"Auto-registered command handler: {handler_class.__name__} "
            f"for {command_type.__name__} in {handler_class.__module__}"
        )

        return handler_class

    return decorator


def query_handler(query_type: Type):
    """
    Decorator for query handler auto-registration

    Usage:
        @query_handler(GetUserByIdQuery)
        class GetUserByIdHandler(BaseQueryHandler):
            def __init__(self, deps):
                self.user_repo = deps.user_read_repo

            async def handle(self, query: GetUserByIdQuery):
                ...
    """

    def decorator(handler_class: Type):
        # CRITICAL: Check for duplicate handler registration
        if query_type in _QUERY_HANDLERS:
            existing_handler = _QUERY_HANDLERS[query_type]
            log.error(
                f"🔴 DUPLICATE QUERY HANDLER DETECTED!\n"
                f"  Query: {query_type.__name__}\n"
                f"  Existing Handler: {existing_handler.__name__} ({existing_handler.__module__})\n"
                f"  New Handler: {handler_class.__name__} ({handler_class.__module__})\n"
                f"  This violates CQRS principles - each query must have exactly ONE handler."
            )
            raise ValueError(
                f"Duplicate query handler: {query_type.__name__} already handled by "
                f"{existing_handler.__name__} in {existing_handler.__module__}"
            )

        # Store handler in registry
        _QUERY_HANDLERS[query_type] = handler_class

        # Add metadata to handler class
        handler_class._query_type = query_type
        handler_class._handler_type = 'query'
        handler_class._module = handler_class.__module__

        # Analyze dependencies from __init__
        try:
            init_method = inspect.signature(handler_class.__init__)
            params = list(init_method.parameters.keys())
            if 'self' in params:
                params.remove('self')
            handler_class._required_deps = params
        except:
            handler_class._required_deps = ['deps']

        log.debug(
            f"Auto-registered query handler: {handler_class.__name__} "
            f"for {query_type.__name__} in {handler_class.__module__}"
        )

        return handler_class

    return decorator


def auto_register_all_handlers(
        command_bus,
        query_bus,
        dependencies,
        skip_missing_deps: bool = False
) -> Dict[str, Any]:
    """
    Register all decorated handlers with their buses

    Args:
        command_bus: The command bus instance
        query_bus: The query bus instance
        dependencies: HandlerDependencies instance with all services
        skip_missing_deps: If True, skip handlers with missing dependencies

    Returns:
        Statistics about registered handlers
    """
    registered_commands = 0
    registered_queries = 0
    skipped_handlers = []

    # Register command handlers
    for command_type, handler_class in _COMMAND_HANDLERS.items():
        try:
            # Check if handler has required dependencies
            if hasattr(handler_class, '_required_deps') and skip_missing_deps:
                missing_deps = _check_missing_dependencies(handler_class, dependencies)
                if missing_deps:
                    log.warning(
                        f"Skipping {handler_class.__name__} due to missing dependencies: {missing_deps}"
                    )
                    skipped_handlers.append({
                        'handler': handler_class.__name__,
                        'type': 'command',
                        'missing': missing_deps
                    })
                    continue

            # Create a factory function that returns handler instances
            # This closure captures the handler_class and dependencies
            def make_factory(h_class, deps):
                def factory():
                    return h_class(deps)

                return factory

            factory_func = make_factory(handler_class, dependencies)

            # Register the factory function with the bus
            command_bus.register_handler(command_type, factory_func)
            registered_commands += 1

            log.debug(f"Registered {handler_class.__name__} for {command_type.__name__}")

        except Exception as e:
            log.error(f"Failed to register {handler_class.__name__}: {e}", exc_info=True)
            skipped_handlers.append({
                'handler': handler_class.__name__,
                'type': 'command',
                'error': str(e)
            })

    # Register query handlers
    for query_type, handler_class in _QUERY_HANDLERS.items():
        try:
            # Check if handler has required dependencies
            if hasattr(handler_class, '_required_deps') and skip_missing_deps:
                missing_deps = _check_missing_dependencies(handler_class, dependencies)
                if missing_deps:
                    log.warning(
                        f"Skipping {handler_class.__name__} due to missing dependencies: {missing_deps}"
                    )
                    skipped_handlers.append({
                        'handler': handler_class.__name__,
                        'type': 'query',
                        'missing': missing_deps
                    })
                    continue

            # Create a factory function that returns handler instances
            # This closure captures the handler_class and dependencies
            def make_factory(h_class, deps):
                def factory():
                    return h_class(deps)

                return factory

            factory_func = make_factory(handler_class, dependencies)

            # Register the factory function with the bus
            query_bus.register_handler(query_type, factory_func)
            registered_queries += 1

            log.debug(f"Registered {handler_class.__name__} for {query_type.__name__}")

        except Exception as e:
            log.error(f"Failed to register {handler_class.__name__}: {e}", exc_info=True)
            skipped_handlers.append({
                'handler': handler_class.__name__,
                'type': 'query',
                'error': str(e)
            })

    total_registered = registered_commands + registered_queries

    log.info(
        f"Auto-registration complete: {registered_commands} commands, "
        f"{registered_queries} queries, {len(skipped_handlers)} skipped"
    )

    return {
        'commands': registered_commands,
        'queries': registered_queries,
        'total': total_registered,
        'skipped': skipped_handlers,
        'success_rate': (total_registered / (total_registered + len(skipped_handlers)) * 100)
        if (total_registered + len(skipped_handlers)) > 0 else 100
    }


def _check_missing_dependencies(handler_class: Type, dependencies) -> List[str]:
    """Check if handler has all required dependencies"""
    missing = []

    # Special handling for 'deps' parameter - it gets the whole dependencies object
    if handler_class._required_deps == ['deps']:
        return []

    # Check each required dependency
    for dep in handler_class._required_deps:
        if not hasattr(dependencies, dep) or getattr(dependencies, dep) is None:
            missing.append(dep)

    return missing


def get_registered_handlers() -> Dict[str, Any]:
    """Get information about all registered handlers"""
    command_info = []
    query_info = []

    # Gather command handler info
    for cmd_type, handler_class in _COMMAND_HANDLERS.items():
        command_info.append({
            'command': cmd_type.__name__,
            'handler': handler_class.__name__,
            'module': getattr(handler_class, '_module', 'unknown'),
            'deps': getattr(handler_class, '_required_deps', [])
        })

    # Gather query handler info
    for query_type, handler_class in _QUERY_HANDLERS.items():
        query_info.append({
            'query': query_type.__name__,
            'handler': handler_class.__name__,
            'module': getattr(handler_class, '_module', 'unknown'),
            'deps': getattr(handler_class, '_required_deps', [])
        })

    return {
        'commands': command_info,
        'queries': query_info,
        'command_count': len(_COMMAND_HANDLERS),
        'query_count': len(_QUERY_HANDLERS),
        'total_count': len(_COMMAND_HANDLERS) + len(_QUERY_HANDLERS),
        'modules': list(set(
            [h.get('module', 'unknown') for h in command_info] +
            [h.get('module', 'unknown') for h in query_info]
        ))
    }


def clear_registries():
    """Clear all handler registries - useful for testing"""
    _COMMAND_HANDLERS.clear()
    _QUERY_HANDLERS.clear()
    _IMPORTED_MODULES.clear()
    log.info("Cleared all handler registries")


def validate_handler_registrations() -> Dict[str, List[str]]:
    """
    Validate that all registered handlers follow conventions
    Returns dict of issues found
    """
    issues = {
        'missing_handle_method': [],
        'invalid_naming': [],
        'duplicate_handlers': []
    }

    # Check command handlers
    for cmd_type, handler_class in _COMMAND_HANDLERS.items():
        # Check for handle method
        if not hasattr(handler_class, 'handle'):
            issues['missing_handle_method'].append(handler_class.__name__)

        # Check naming convention
        if not handler_class.__name__.endswith('Handler'):
            issues['invalid_naming'].append(
                f"{handler_class.__name__} should end with 'Handler'"
            )

    # Check query handlers
    for query_type, handler_class in _QUERY_HANDLERS.items():
        # Check for handle method
        if not hasattr(handler_class, 'handle'):
            issues['missing_handle_method'].append(handler_class.__name__)

        # Check naming convention
        if not handler_class.__name__.endswith('Handler'):
            issues['invalid_naming'].append(
                f"{handler_class.__name__} should end with 'Handler'"
            )

    # Remove empty issue lists
    issues = {k: v for k, v in issues.items() if v}

    return issues


# Optional: Helper decorators for specific handler types

def saga_command_handler(command_type: Type):
    """
    Special decorator for saga-specific command handlers
    Adds saga context validation
    """

    def decorator(handler_class: Type):
        # First apply regular command handler decorator
        handler_class = command_handler(command_type)(handler_class)

        # Add saga flag
        handler_class._is_saga_handler = True

        # Wrap handle method to validate saga_id
        original_handle = handler_class.handle

        @wraps(original_handle)
        async def wrapped_handle(self, command):
            if not hasattr(command, 'saga_id') or command.saga_id is None:
                log.warning(
                    f"Saga command {command.__class__.__name__} called without saga_id"
                )
            return await original_handle(self, command)

        handler_class.handle = wrapped_handle

        return handler_class

    return decorator


def cached_query_handler(query_type: Type, ttl: int = 60):
    """
    Decorator for query handlers that should cache results
    """

    def decorator(handler_class: Type):
        # First apply regular query handler decorator
        handler_class = query_handler(query_type)(handler_class)

        # Add cache metadata
        handler_class._cache_ttl = ttl
        handler_class._is_cached = True

        log.debug(f"Query handler {handler_class.__name__} will cache results for {ttl}s")

        return handler_class

    return decorator


def readonly_query(query_type: Type):
    """
    Decorator for query handlers that explicitly marks them as read-only operations.

    This decorator serves as:
    1. Documentation - Makes it clear this handler only reads data
    2. Validation - Can be extended to enforce read-only constraints
    3. Industry compliance - Matches best practices from .NET, Java Spring (@Transactional(readOnly=true))

    Usage:
        @readonly_query(GetPositionQuery)
        class GetPositionQueryHandler(BaseQueryHandler[GetPositionQuery, Optional[PositionReadModel]]):
            def __init__(self, deps):
                super().__init__()
                self.position_repo = deps.position_read_repo

            async def handle(self, query: GetPositionQuery):
                # This handler will only read data, never modify
                return await self.position_repo.get_by_id(query.position_id)

    Benefits:
    - Self-documenting code: Developers know this handler only reads
    - Future-proof: Can add transaction hints, monitoring, etc.
    - Industry standard: Matches @Transactional(readOnly=true) from Java/Spring

    Note: This is a marker decorator. It doesn't change behavior, but can be
    extended in the future for:
    - Read-only transaction hints to database
    - Performance monitoring specific to read operations
    - Validation that handler doesn't call command bus
    """

    def decorator(handler_class: Type):
        # First apply regular query handler decorator
        handler_class = query_handler(query_type)(handler_class)

        # Add read-only metadata
        handler_class._is_readonly = True
        handler_class._operation_type = 'read_only_query'

        # Optional: Could wrap handle method to validate no writes
        # For now, just mark it - can extend later

        log.debug(
            f"Query handler {handler_class.__name__} marked as read-only "
            f"for {query_type.__name__}"
        )

        return handler_class

    return decorator


# Module initialization logging
log.info("CQRS decorators module initialized")
# app/infra/cqrs/command_bus.py
# =============================================================================
# File: app/infra/cqrs/command_bus.py
# Description: Production-ready Command Bus with string-based routing
# UPDATED: Using Pydantic v2 for all commands
# =============================================================================

import logging
from typing import Dict, Type, Any, Optional, List, Callable, Awaitable, Union
from abc import ABC, abstractmethod
import uuid

from pydantic import BaseModel

log = logging.getLogger("tradecore.cqrs.command")


# =============================================================================
# Base Classes
# =============================================================================

class Command(BaseModel):
    """Base class for all commands using Pydantic v2"""
    saga_id: Optional[uuid.UUID] = None


class ICommandHandler(ABC):
    """Base class for all command handlers"""

    @abstractmethod
    async def handle(self, command: Command) -> Any:
        """Handle the command and return result"""
        pass


# =============================================================================
# Middleware Support
# =============================================================================

class Middleware(ABC):
    """Base middleware class for commands"""

    @abstractmethod
    async def process(
            self,
            message: Any,
            next_handler: Callable[[Any], Awaitable[Any]]
    ) -> Any:
        """Process message and call next handler"""
        pass


class LoggingMiddleware(Middleware):
    """Logs all commands with saga context"""

    async def process(self, message: Any, next_handler: Callable) -> Any:
        message_type = type(message).__name__
        saga_id = getattr(message, 'saga_id', None)

        if saga_id:
            log.info(f"Processing command {message_type} [saga: {saga_id}]")
        else:
            log.info(f"Processing command {message_type}")

        try:
            result = await next_handler(message)
            if saga_id:
                log.info(f"Successfully processed command {message_type} [saga: {saga_id}]")
            else:
                log.info(f"Successfully processed command {message_type}")
            return result
        except Exception as e:
            if saga_id:
                log.error(f"Failed to process command {message_type} [saga: {saga_id}]: {e}")
            else:
                log.error(f"Failed to process command {message_type}: {e}")
            raise


class SagaContextMiddleware(Middleware):
    """Adds saga context logging"""

    async def process(self, message: Any, next_handler: Callable) -> Any:
        saga_id = getattr(message, 'saga_id', None)
        correlation_id = getattr(message, 'correlation_id', None)
        causation_id = getattr(message, 'causation_id', None)

        if saga_id:
            log_context = {
                'saga_id': str(saga_id),
                'message_type': type(message).__name__
            }
            if correlation_id:
                log_context['correlation_id'] = correlation_id
            if causation_id:
                log_context['causation_id'] = causation_id

            log.info(f"Saga context: {log_context}")

        return await next_handler(message)


class ValidationMiddleware(Middleware):
    """Validates commands"""

    async def process(self, message: Any, next_handler: Callable) -> Any:
        # For Pydantic v2 models, validation happens during construction
        # Additional validation can be done here if needed

        # Validate saga context if present
        if hasattr(message, 'saga_id') and message.saga_id:
            if not isinstance(message.saga_id, uuid.UUID):
                raise ValueError(f"Invalid saga_id type: {type(message.saga_id)}")

        # Ensure the command is a Pydantic model (for type safety)
        if isinstance(message, BaseModel):
            # Pydantic models are already validated
            pass
        else:
            log.warning(f"Command {type(message).__name__} is not a Pydantic model")

        return await next_handler(message)


class MetricsMiddleware(Middleware):
    """Tracks command execution metrics"""

    def __init__(self):
        self.command_counts: Dict[str, int] = {}
        self.command_errors: Dict[str, int] = {}

    async def process(self, message: Any, next_handler: Callable) -> Any:
        command_name = type(message).__name__

        # Increment command count
        self.command_counts[command_name] = self.command_counts.get(command_name, 0) + 1

        try:
            result = await next_handler(message)
            return result
        except Exception as e:
            # Increment error count
            self.command_errors[command_name] = self.command_errors.get(command_name, 0) + 1
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get command execution metrics"""
        return {
            "command_counts": self.command_counts.copy(),
            "command_errors": self.command_errors.copy(),
            "total_commands": sum(self.command_counts.values()),
            "total_errors": sum(self.command_errors.values())
        }


# =============================================================================
# Command Bus Implementation with String-Based Routing
# =============================================================================

class CommandBus:
    """
    Production-ready Command Bus with middleware pipeline.
    Supports both type-based and string-based routing for flexibility.
    """

    def __init__(self):
        # Type-based handlers (for backward compatibility)
        self._handlers: Dict[Type[Command], ICommandHandler] = {}
        self._handler_factories: Dict[Type[Command], Callable[[], ICommandHandler]] = {}

        # String-based handlers (for saga compatibility)
        self._string_handlers: Dict[str, ICommandHandler] = {}
        self._string_handler_factories: Dict[str, Callable[[], ICommandHandler]] = {}

        self._middleware: List[Middleware] = []

        # Metrics middleware
        self._metrics_middleware = MetricsMiddleware()

        # Add default middleware
        self.use(LoggingMiddleware())
        self.use(SagaContextMiddleware())
        self.use(ValidationMiddleware())
        self.use(self._metrics_middleware)

    def use(self, middleware: Middleware) -> 'CommandBus':
        """Add middleware to the pipeline"""
        self._middleware.append(middleware)
        return self

    def register_handler(
            self,
            command_type: Union[Type[Command], str],
            handler_factory: Callable[[], ICommandHandler]
    ) -> None:
        """
        Register a handler factory for a command type.
        Can accept either a type or a string name.
        Raises ValueError if duplicate handler detected (CQRS compliance).
        """
        if isinstance(command_type, str):
            # String-based registration - check for duplicates
            if command_type in self._string_handler_factories:
                existing_factory = self._string_handler_factories[command_type]
                if existing_factory != handler_factory:
                    raise ValueError(
                        f"❌ DUPLICATE COMMAND HANDLER: Command '{command_type}' already has a registered handler. "
                        f"CQRS principle: each command must have exactly ONE handler. "
                        f"Existing: {existing_factory}, Attempted: {handler_factory}"
                    )
            self._string_handler_factories[command_type] = handler_factory
            log.debug(f"Registered handler for command name '{command_type}'")
        else:
            # Type-based registration - check for duplicates
            if command_type in self._handler_factories:
                existing_factory = self._handler_factories[command_type]
                if existing_factory != handler_factory:
                    raise ValueError(
                        f"❌ DUPLICATE COMMAND HANDLER: Command '{command_type.__name__}' already has a registered handler. "
                        f"CQRS principle: each command must have exactly ONE handler. "
                        f"Existing: {existing_factory}, Attempted: {handler_factory}"
                    )

            self._handler_factories[command_type] = handler_factory
            # Also register by string name for saga compatibility
            command_name = command_type.__name__

            # Check string registry for duplicates too
            if command_name in self._string_handler_factories:
                existing_factory = self._string_handler_factories[command_name]
                if existing_factory != handler_factory:
                    raise ValueError(
                        f"❌ DUPLICATE COMMAND HANDLER: Command '{command_name}' already registered by string name. "
                        f"Existing: {existing_factory}, Attempted: {handler_factory}"
                    )

            self._string_handler_factories[command_name] = handler_factory
            log.debug(f"Registered handler for {command_name} (type and string)")

    def register_handlers(self, registry: Dict[Union[Type[Command], str], Callable]) -> None:
        """Bulk register handlers"""
        for cmd_type, factory in registry.items():
            self.register_handler(cmd_type, factory)

    def validate_registrations(self) -> None:
        """
        Validate that all command handler registrations are unique.
        Call this during application startup to fail-fast on CQRS violations.
        Raises ValueError if duplicate handlers are detected.
        """
        log.info(f"Validating command handler registrations...")

        total_commands = len(self._string_handler_factories)
        type_based = len(self._handler_factories)

        log.info(
            f"✓ Command bus validation passed: "
            f"{total_commands} command handlers registered "
            f"({type_based} type-based, {total_commands - type_based} string-only)"
        )

        # Note: Duplicate detection happens at registration time (in register_handler)
        # This method provides a summary validation checkpoint at startup

    async def send(self, command: Command) -> Any:
        """
        Send a command through the middleware pipeline to its handler.
        This is the main entry point for command execution.
        """
        # Build the handler chain
        handler = self._build_handler_chain(command)

        # Execute through middleware pipeline
        return await handler(command)

    def _build_handler_chain(self, command: Command) -> Callable:
        """Build the middleware chain ending with the actual handler"""
        command_type = type(command)
        command_name = command_type.__name__

        # Try string-based lookup first (for saga compatibility)
        if command_name not in self._string_handlers:
            factory = self._string_handler_factories.get(command_name)

            # Fallback to type-based lookup
            if not factory and command_type not in self._handlers:
                factory = self._handler_factories.get(command_type)

            if not factory:
                # Provide helpful error message
                registered_types = [t.__name__ for t in self._handler_factories.keys()]
                registered_strings = list(self._string_handler_factories.keys())
                all_registered = sorted(set(registered_types + registered_strings))

                raise ValueError(
                    f"No handler registered for {command_name}. "
                    f"Registered handlers: {all_registered}"
                )

            # Create and cache the handler
            handler_instance = factory()
            self._string_handlers[command_name] = handler_instance
            if command_type in self._handler_factories:
                self._handlers[command_type] = handler_instance

        final_handler = self._string_handlers.get(command_name) or self._handlers.get(command_type)

        # Build the chain from the inside out
        async def handler_wrapper(cmd):
            return await final_handler.handle(cmd)

        chain = handler_wrapper

        # Wrap with middleware in reverse order
        for middleware in reversed(self._middleware):
            current_chain = chain

            async def wrapped(cmd, mw=middleware, next_h=current_chain):
                return await mw.process(cmd, lambda c: next_h(c))

            chain = wrapped

        return chain

    def get_metrics(self) -> Dict[str, Any]:
        """Get command execution metrics"""
        return self._metrics_middleware.get_metrics()

    def get_handler_info(self) -> Dict[str, Any]:
        """Get information about registered handlers"""
        return {
            "type_handlers": [h.__name__ for h in self._handler_factories.keys()],
            "string_handlers": list(self._string_handler_factories.keys()),
            "total_handlers": len(self._handler_factories) + len(
                set(self._string_handler_factories.keys()) - {h.__name__ for h in self._handler_factories.keys()}),
            "middleware_count": len(self._middleware)
        }


# =============================================================================
# Batch Command Support for Sagas (Using Pydantic v2)
# =============================================================================

class BatchDeleteAccountsCommand(Command):
    """Command to delete multiple accounts"""
    user_id: uuid.UUID
    account_ids: List[uuid.UUID]


class BatchPurgeConnectionsCommand(Command):
    """Command to purge multiple connections"""
    user_id: uuid.UUID
    connection_ids: List[uuid.UUID]
    force: bool = True

# =============================================================================
# EOF
# =============================================================================
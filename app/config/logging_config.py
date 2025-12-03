# app/config/logging_config.py
# =============================================================================
# File: app/config/logging_config.py
# Description: Enhanced logging configuration using Rich framework
# UPDATED: Added DLQ Service to startup table display
# =============================================================================

import logging
import logging.handlers
import os
import sys
import re
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from collections import OrderedDict

# Try to import Rich, but don't fail if it's not available
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme
    from rich.box import ROUNDED, HEAVY, MINIMAL, SIMPLE, SQUARE, DOUBLE
    from rich.columns import Columns
    from rich.align import Align
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.layout import Layout
    from rich.rule import Rule

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    RichHandler = logging.StreamHandler
    Panel = None
    Table = None
    Text = None
    Theme = None


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    value = os.getenv(key, '').lower()
    return value in ('true', '1', 'yes', 'on') if value else default


def get_env_int(key: str, default: int) -> int:
    """Get integer value from environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_env_float(key: str, default: float) -> float:
    """Get float value from environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# Custom theme with muted colors - only if Rich is available
if RICH_AVAILABLE:
    WELLWON_THEME = Theme({
        "debug": "magenta dim",
        "info": "green",  # Changed: muted green for INFO logs
        "warning": "dark_goldenrod",  # Changed: muted yellow for WARNING logs
        "error": "red",
        "critical": "bold red",
        "success": "green3",  # Changed: muted green
        "timestamp": "grey70",
        "logger_name": "grey35",
        "message": "grey85",  # Changed: muted white for log messages
        "dim": "bright_black",
        "frame": "bright_blue",
        "header": "bold cyan",
        "table.header": "white on grey23",
        "table.row": "white",
        "table.row.alt": "white on grey11",
    })
else:
    WELLWON_THEME = None


class StartupCollector:
    """Enhanced startup collector that captures all initialization messages"""

    def __init__(self):
        self.services = OrderedDict()
        self.is_collecting = True
        self._lock = threading.Lock()
        self._console = None
        self.service_type = os.getenv('SERVICE_TYPE', 'api')  # Read from env
        self.collection_timeout = get_env_float('STARTUP_COLLECTION_TIMEOUT', 10.0)
        self.collection_start_time = datetime.now()
        self._force_display_triggered = False

        # Categories for grouping services
        self.categories = OrderedDict([
            ('core', {'name': 'Core Infrastructure', 'services': OrderedDict()}),
            ('persistence', {'name': 'Persistence', 'services': OrderedDict()}),
            ('database', {'name': 'Databases', 'services': OrderedDict()}),
            ('messaging', {'name': 'Messaging & Events', 'services': OrderedDict()}),
            ('adapters', {'name': 'Adapter Infrastructure', 'services': OrderedDict()}),
            ('services', {'name': 'Services', 'services': OrderedDict()}),
            ('features', {'name': 'Features', 'services': OrderedDict()}),
            ('monitoring', {'name': 'Monitoring & Admin', 'services': OrderedDict()}),
        ])

        # Track initialization phases
        self.phase_timings = OrderedDict()
        self.start_time = datetime.now()
        self.last_phase_time = self.start_time

        # Collect raw messages for detailed view
        self.raw_messages = []

    def set_console(self, console):
        """Set the console for output"""
        self._console = console

    def should_force_display(self) -> bool:
        """Check if we should force display due to timeout"""
        if self._force_display_triggered:
            return False

        elapsed = (datetime.now() - self.collection_start_time).total_seconds()
        if elapsed > self.collection_timeout:
            self._force_display_triggered = True
            return True
        return False

    def add_service(self, name: str, status: str, category: str = 'core',
                    details: Optional[Dict[str, Any]] = None, raw_message: str = None):
        """Add a service initialization info with category"""
        with self._lock:
            if self.is_collecting:
                # Store in appropriate category
                if category in self.categories:
                    self.categories[category]['services'][name] = {
                        'status': status,
                        'details': details or {},
                        'timestamp': datetime.now()
                    }

                # Store raw message
                if raw_message:
                    self.raw_messages.append({
                        'time': datetime.now(),
                        'message': raw_message,
                        'service': name
                    })

    def mark_phase(self, phase_name: str):
        """Mark the completion of an initialization phase"""
        with self._lock:
            now = datetime.now()
            duration = (now - self.last_phase_time).total_seconds()
            self.phase_timings[phase_name] = duration
            self.last_phase_time = now

    def stop_collecting(self):
        """Stop collecting and return all services"""
        with self._lock:
            self.is_collecting = False
            total_time = (datetime.now() - self.start_time).total_seconds()
            return self.categories, self.phase_timings, total_time

    def reset(self):
        """Reset the collector for a new session"""
        with self._lock:
            self.__init__()


# Global startup collector
_startup_collector = StartupCollector()

# Global service type storage
_service_type = os.getenv('SERVICE_TYPE', 'api')


class SmartRichHandler(RichHandler if RICH_AVAILABLE else logging.StreamHandler):
    """Enhanced RichHandler that intelligently collects startup messages"""

    def __init__(self, *args, **kwargs):
        if not RICH_AVAILABLE:
            # Fallback to StreamHandler
            super().__init__()
            self.formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)-8s  %(name)-40s  %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            self.setFormatter(self.formatter)
            return

        # Override defaults for cleaner output during runtime
        kwargs.setdefault('show_time', False)
        kwargs.setdefault('show_level', False)
        kwargs.setdefault('show_path', False)
        kwargs.setdefault('enable_link_path', False)
        kwargs.setdefault('markup', True)
        kwargs.setdefault('rich_tracebacks', True)
        kwargs.setdefault('tracebacks_show_locals', False)

        super().__init__(*args, **kwargs)

        # Store console reference
        if RICH_AVAILABLE and hasattr(self, 'console'):
            self.console = kwargs.get('console') or self.console
            _startup_collector.set_console(self.console)

        self._displayed_startup = False
        self._startup_complete_logged = False
        self._normal_logging_active = False

        # Configuration from environment
        self.show_detailed_table = get_env_bool('STARTUP_SHOW_DETAILED_TABLE', True)
        self.show_performance = get_env_bool('STARTUP_SHOW_PERFORMANCE', True)
        self.clear_screen = get_env_bool('STARTUP_CLEAR_SCREEN', True)

        # Enhanced message patterns for collection
        self.collection_patterns = {
            # Persistence Layer (PostgreSQL, Redis, MinIO, ScyllaDB infrastructure)
            # NOTE: More specific patterns MUST come before generic patterns
            r'Reference PostgreSQL pool initialized': ('database', 'WellWon Reference DB'),
            r'Main PostgreSQL pool initialized': ('database', 'WellWon DB'),
            r'PostgreSQL.*pool.*initialized': ('persistence', 'PostgreSQL'),
            r'Redis.*initialized': ('persistence', 'Redis'),
            r'MinIO.*storage.*initialized': ('persistence', 'MinIO Storage'),
            r'ScyllaDB.*client.*initialized': ('persistence', 'ScyllaDB'),
            r'Global ScyllaDB client initialized': ('persistence', 'ScyllaDB'),

            # Databases (Application-specific databases)
            r'Reference database schema checked.applied': ('database', 'WellWon Reference DB'),
            r'Main database schema checked.applied': ('database', 'WellWon DB'),
            r'Reference database.*checked|applied': ('database', 'WellWon Reference DB'),
            r'Main database.*checked|applied': ('database', 'WellWon DB'),
            r'Schema from.*wellwon_reference\.sql.*applied.*REFERENCE': ('database', 'WellWon Reference DB'),
            r'Virtual Broker.*database.*initialized': ('database', 'Virtual Broker DB'),
            r'Virtual Broker.*PostgreSQL.*initialized': ('database', 'Virtual Broker DB'),
            r'Virtual Broker schema.*': ('database', 'Virtual Broker DB'),
            r'Virtual broker PostgreSQL database initialized': ('database', 'Virtual Broker DB'),

            # External Adapters (Third-party integrations)
            r'Telegram adapter initialized': ('adapters', 'Telegram Adapter'),
            r'Telegram adapter disabled': ('adapters', 'Telegram Adapter'),
            r'DaData adapter initialized': ('adapters', 'DaData Adapter'),
            r'DaData not configured': ('adapters', 'DaData Adapter'),
            r'Kontur.*adapter initialized': ('adapters', 'Kontur Adapter'),
            r'Kontur not configured': ('adapters', 'Kontur Adapter'),

            # Messaging & Events
            r'EventBus.*initialized': ('messaging', 'Event Bus'),
            r'Reactive.*EventBus.*initialized': ('messaging', 'Reactive Bus'),
            r'Event Store.*initialized': ('messaging', 'Event Store'),
            r'DLQ.*Service.*started': ('messaging', 'DLQ Service'),
            r'DLQ.*Service.*initialized': ('messaging', 'DLQ Service'),
            r'Dead.*Letter.*Queue.*started': ('messaging', 'DLQ Service'),
            r'Dead.*Letter.*Queue.*initialized': ('messaging', 'DLQ Service'),
            r'Outbox.*service.*initialized': ('messaging', 'Outbox Service'),
            r'Outbox publisher started': ('messaging', 'Outbox Publisher'),
            r'Snapshots enabled': ('messaging', 'Snapshots'),
            r'Snapshots disabled': ('messaging', 'Snapshots'),
            r'Automatic snapshot processor started': ('messaging', 'Auto Snapshots'),

            # Features (CQRS, Sync/Async Projections, etc.)
            r'Sync projections registered': ('features', 'Sync Projections'),
            r'Synchronous projections.*registered': ('features', 'Sync Projections'),
            r'Async projections available': ('features', 'Async Projections'),
            r'CQRS.*initialized': ('features', 'CQRS'),
            r'Command Bus.*initialized': ('features', 'CQRS'),
            r'CQRS handlers registered': ('features', 'CQRS Handlers'),
            # NOTE: Removed redundant r'handlers.*registered' pattern - CQRS Handlers above is sufficient
            r'Distributed.*Lock.*initialized': ('features', 'Distributed Locks'),
            r'Sequence.*Tracker.*initialized': ('features', 'Sequence Tracking'),

            # Cache
            r'Cache manager.*initialized|started': ('core', 'Cache Manager'),

            # Adapters
            r'Broker adapter factory.*initialized': ('adapters', 'Adapter Factory'),
            r'Adapter.*[Pp]ool.*initialized': ('adapters', 'Adapter Pool'),
            r'AdapterManager.*initialized': ('adapters', 'Adapter Manager'),
            r'adapter.*registered': ('adapters', None),

            # Services
            r'Authentication.*[Ss]ervice.*initialized': ('services', 'Auth Service'),
            r'BrokerOperationService.*initialized': ('services', 'Operation Service'),
            r'AdapterMonitoringService.*initialized': ('services', 'Monitoring Service'),
            r'Broker Streaming Service.*initialized': ('services', 'Streaming Service'),
            r'Virtual.*Broker.*Service.*initialized': ('services', 'Virtual Broker'),
            r'Virtual Market Data Service.*initialized': ('services', 'Market Data'),
            r'Saga.*Service.*initialized|created': ('services', 'Saga Service'),
            r'STARTUP_SUBSCRIPTION.*Broker streaming initialized': ('services', 'Broker Streaming'),
            r'Telegram.*polling.*started': ('services', 'Telegram MTProto'),
            r'MTProto.*client.*connected': ('services', 'Telegram MTProto'),
            r'MTProto.*user.*client.*started': ('services', 'Telegram MTProto'),

            # Monitoring & Admin - Workers
            # Data Integrity
            r'Data.*Integrity.*Monitor.*started.*worker.*mode': ('monitoring', 'Data Integrity Worker'),
            r'Data.*Integrity.*Monitor.*runs.*separate.*worker': ('monitoring', 'Data Integrity Worker'),
            r'Data.*Integrity.*Monitor.*worker.*mode': ('monitoring', 'Data Integrity Worker'),
            r'Data.*Integrity.*Monitor.*initialized.*worker': ('monitoring', 'Data Integrity Worker'),
            r'Data.*Integrity.*Monitor.*enabled': ('monitoring', 'Data Integrity'),
            r'Data.*Integrity.*Monitor.*initialized': ('monitoring', 'Data Integrity'),

            # Connection Recovery Worker
            r'Connection.*Recovery.*started.*worker.*mode': ('monitoring', 'Connection Recovery Worker'),
            r'Connection.*Recovery.*runs.*separate.*worker': ('monitoring', 'Connection Recovery Worker'),
            r'Connection.*Recovery.*worker.*mode': ('monitoring', 'Connection Recovery Worker'),
            r'Connection.*Recovery.*initialized.*worker': ('monitoring', 'Connection Recovery Worker'),
            r'Connection.*Recovery.*enabled': ('monitoring', 'Connection Recovery'),
            r'Connection.*Recovery.*initialized': ('monitoring', 'Connection Recovery'),

            # Consumer Worker
            r'Consumer.*started.*worker.*mode': ('monitoring', 'Consumer Worker'),
            r'Consumer.*runs.*separate.*worker': ('monitoring', 'Consumer Worker'),
            r'Consumer.*worker.*mode': ('monitoring', 'Consumer Worker'),
            r'Consumer.*initialized.*worker': ('monitoring', 'Consumer Worker'),

            # Projection Rebuilder
            r'ProjectionRebuilderService.*created': ('monitoring', 'Projection Rebuilder'),

            # Worker specific
            r'Worker.*started|ready': ('core', 'Worker Status'),
            r'Worker.*initialized': ('core', 'Worker Status'),
            r'Status:.*Worker Ready': ('core', 'Worker Status'),
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format with custom layout for runtime logs"""
        if not RICH_AVAILABLE:
            return super().format(record)

        try:
            # Always format properly, regardless of collection state
            time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

            level_colors = {
                'DEBUG': 'debug',
                'INFO': 'info',
                'WARNING': 'warning',
                'ERROR': 'error',
                'CRITICAL': 'critical',
            }
            level_style = level_colors.get(record.levelname, 'white')
            level_str = f"[{level_style}]{record.levelname:>7}[/{level_style}]"

            logger_name = record.name
            if len(logger_name) > 30:
                parts = logger_name.split('.')
                if len(parts) > 2:
                    logger_name = f"{parts[0]}...{parts[-1]}"
            logger_str = f"[logger_name]{logger_name:>30}[/logger_name]"

            # Include additional info if configured
            extra_info = []
            if get_env_bool('LOG_CALLER_INFO', True) and record.pathname:
                extra_info.append(f"{record.filename}:{record.lineno}")
            if get_env_bool('LOG_THREAD_INFO', False):
                extra_info.append(f"Thread: {record.threadName}")
            if get_env_bool('LOG_PROCESS_INFO', False):
                extra_info.append(f"PID: {record.process}")

            message = record.getMessage()
            if extra_info:
                message = f"{message} [{', '.join(extra_info)}]"

            return f"[timestamp]{time_str}[/timestamp] {level_str} {logger_str}  {message}"
        except:
            return record.getMessage()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit with enhanced startup collection"""
        if not RICH_AVAILABLE:
            super().emit(record)
            return

        try:
            message = record.getMessage()

            # Check for force display due to timeout (for workers)
            if _startup_collector.is_collecting and _startup_collector.should_force_display():
                self._display_startup_summary()
                self._normal_logging_active = True

            # During startup collection phase
            if _startup_collector.is_collecting and not self._normal_logging_active:
                self._collect_startup_message(message, record)

                # Check if this is a startup complete trigger
                if self._is_startup_complete(message):
                    self._display_startup_summary()
                    self._normal_logging_active = True
                    # Don't print the trigger message itself
                    return

                # For workers, also display critical messages immediately
                if record.levelname in ['ERROR', 'CRITICAL', 'WARNING']:
                    log_output = self.format(record)
                    if hasattr(self, 'console'):
                        self.console.print(log_output, soft_wrap=True)
                    else:
                        print(log_output)

                # Don't print info/debug messages during collection
                return

            # Normal logging mode - always print
            log_output = self.format(record)
            if hasattr(self, 'console'):
                self.console.print(log_output, soft_wrap=True)
            else:
                print(log_output)

        except Exception as e:
            # In case of error, ensure we still log
            print(f"Logging error: {e}")
            print(record.getMessage())
            if sys.meta_path is not None:
                self.handleError(record)

    def _collect_startup_message(self, message: str, record: logging.LogRecord):
        """Enhanced message collection with pattern matching"""
        # Try to match against patterns
        for pattern, (category, service_name) in self.collection_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                # Extract details from message
                details = self._extract_details(message)

                # Use extracted service name if not provided
                if not service_name:
                    service_name = self._extract_service_name(message, pattern)

                if service_name:
                    status = self._extract_status(message)
                    _startup_collector.add_service(
                        service_name, status, category, details, message
                    )
                break

    def _extract_details(self, message: str) -> Dict[str, Any]:
        """Extract details from log message"""
        details = {}

        # Extract numbers
        numbers = re.findall(r'\b(\d+)\b', message)
        if numbers:
            # For sync projections, extract events and handlers
            if 'sync projections registered' in message.lower():
                if len(numbers) >= 2:
                    details['events'] = numbers[0]
                    details['handlers'] = numbers[1]
            # For async projections, extract events count
            elif 'async projections available' in message.lower():
                if len(numbers) >= 1:
                    details['events'] = numbers[0]
            # For CQRS handlers
            elif 'cqrs handlers registered' in message.lower():
                if len(numbers) >= 2:
                    details['commands'] = numbers[0]
                    details['queries'] = numbers[1]
            else:
                details['count'] = numbers[0]

        # Extract configuration values (key=value or key: value)
        config_patterns = [
            r'(\w+)=(\w+)',  # key=value
            r'(\w+):\s*(\w+)',  # key: value
        ]

        for pattern in config_patterns:
            for match in re.finditer(pattern, message):
                key = match.group(1)
                value = match.group(2)
                # Don't overwrite existing keys
                if key not in details:
                    details[key] = value

        # Extract parenthetical info - enhanced for snapshots
        if match := re.search(r'\(([^)]+)\)', message):
            paren_content = match.group(1)
            # Check if it's key-value pairs
            if ',' in paren_content or ':' in paren_content:
                # Parse the parenthetical content
                parts = paren_content.split(',')
                for part in parts:
                    part = part.strip()
                    if ':' in part:
                        k, v = part.split(':', 1)
                        details[k.strip()] = v.strip()
                    else:
                        details['info'] = paren_content
            else:
                details['info'] = paren_content

        return details

    def _extract_service_name(self, message: str, pattern: str) -> Optional[str]:
        """Try to extract service name from message"""
        # Common patterns for service names
        if match := re.search(r'(\w+\s+\w+)\s+initialized', message, re.IGNORECASE):
            return match.group(1)
        if match := re.search(r'Registered\s+(\w+)', message):
            return match.group(1)
        return None

    def _extract_status(self, message: str) -> str:
        """Extract status from message"""
        message_lower = message.lower()

        # Special handling for worker mode / separate process - check first
        if any(phrase in message_lower for phrase in ['worker mode', 'separate worker', 'runs as separate worker']):
            return '[yellow]→[/yellow] Runs as Worker'

        # Check for explicit worker indication
        if 'started in worker mode' in message_lower:
            return '[yellow]→[/yellow] Worker Mode'

        status_keywords = {
            'initialized': '[green]✓[/green] Initialized',
            'started': '[green]✓[/green] Started',
            'connected': '[green]✓[/green] Connected',
            'ready': '[green]✓[/green] Ready',
            'enabled': '[green]✓[/green] Enabled',
            'registered': '[green]✓[/green] Registered',
            'configured': '[green]✓[/green] Configured',
            'created': '[green]✓[/green] Created',
            'applied': '[green]✓[/green] Applied',
            'checked': '[green]✓[/green] Checked',
            'disabled': '[red]✗[/red] Disabled',
            'failed': '[red]✗[/red] Failed',
        }

        for keyword, status in status_keywords.items():
            if keyword in message_lower:
                return status

        return '[green]✓[/green] OK'

    def _is_startup_complete(self, message: str) -> bool:
        """Check if startup is complete - case insensitive"""
        # Enhanced triggers for completion
        complete_keywords = [
            'application startup complete',
            'startup sync complete',
            'worker ready',  # For workers
            'worker started successfully',  # For workers
            'switching to normal logging',  # Explicit trigger
        ]

        message_lower = message.lower()

        # Also check for the configuration summary message
        if 'configuration summary' in message_lower:
            _startup_collector.mark_phase('Configuration')

        return any(keyword in message_lower for keyword in complete_keywords)

    def _display_startup_summary(self):
        """Display comprehensive startup summary"""
        if not hasattr(self, 'console') or self._startup_complete_logged:
            return

        self._startup_complete_logged = True
        categories, phase_timings, total_time = _startup_collector.stop_collecting()

        # Don't clear screen for workers - it's jarring
        if _startup_collector.service_type == 'api' and self.clear_screen:
            self.console.clear()

        # Determine service type and border color
        global _service_type
        service_type = _service_type

        # Get version dynamically
        from app import __version__

        service_names = {
            'api': f'WellWon v{__version__}',
            'data_integrity': 'DATA INTEGRITY WORKER',
            'consumer': 'CONSUMER WORKER',
            'connection_recovery': 'CONNECTION RECOVERY WORKER'
        }

        border_colors = {
            'api': 'bright_green',
            'data_integrity': 'yellow',  # Yellow/Amber
            'consumer': 'magenta',  # Purple/Violet
            'connection_recovery': 'cyan'  # Cyan for Connection Recovery
        }

        service_name = service_names.get(service_type, 'WellWon Service')
        border_color = border_colors.get(service_type, 'bright_blue')

        # Only show detailed table for API, simplified for workers
        if service_type == 'api' and self.show_detailed_table:
            # Header
            self.console.print()
            self.console.rule(f"[bold white]{service_name}[/bold white]", style=border_color)
            self.console.print()

            # Create main table
            main_table = Table(
                show_header=True,
                header_style="white on grey23",
                border_style=border_color,
                box=ROUNDED,
                padding=(0, 1),
                expand=True
            )

            main_table.add_column("Component", style="cyan", width=25)
            main_table.add_column("Status", style="white", width=20, justify="center")
            main_table.add_column("Details", style="grey70", width=35)
            main_table.add_column("Time", style="yellow", width=12, justify="right")

            # Add services by category
            for cat_key, category in categories.items():
                if category['services']:
                    # Add category header
                    main_table.add_row(
                        f"[bold white]{category['name']}[/bold white]",
                        "",
                        "",
                        "",
                        style="white on grey23"
                    )

                    # Add services in this category
                    for service_name, info in category['services'].items():
                        # Calculate time
                        service_time = (info['timestamp'] - _startup_collector.start_time).total_seconds()
                        time_str = f"{service_time:.2f}s"

                        # Format details
                        details_parts = []
                        for key, value in info['details'].items():
                            if key == 'info':
                                details_parts.append(str(value))
                            elif key in ['events', 'handlers']:
                                details_parts.append(f"{key}: {value}")
                            elif key in ['commands', 'queries']:
                                details_parts.append(f"{key}: {value}")
                            else:
                                details_parts.append(f"{key}: {value}")
                        details_str = ", ".join(details_parts) if details_parts else "—"

                        main_table.add_row(
                            f"  {service_name}",
                            info['status'],
                            details_str,
                            time_str
                        )

                    # Add separator between categories
                    if cat_key != list(categories.keys())[-1]:
                        main_table.add_row("", "", "", "", style="dim")

            # Display table
            self.console.print(main_table)
        else:
            # Simplified display for workers
            self.console.print()
            self.console.rule(f"[bold white]{service_name} Initialization Complete[/bold white]", style=border_color)

        # Performance summary for all services
        if self.show_performance:
            self.console.print()

            # Performance summary table
            perf_table = Table(
                show_header=False,
                border_style=border_color,
                box=MINIMAL,
                padding=(0, 1)
            )

            perf_table.add_column("Metric", style="grey70")
            perf_table.add_column("Value", style="bold white", justify="right")

            perf_table.add_row("Total Startup Time", f"{total_time:.2f} seconds")
            perf_table.add_row("Components Initialized", str(sum(len(cat['services']) for cat in categories.values())))

            # Show performance metrics
            self.console.print(Panel(
                perf_table,
                title="[bold white]Performance Metrics[/bold white]",
                border_style=border_color,
                padding=(0, 1)
            ))

        self.console.print()
        self.console.rule(f"[bold white]System Ready[/bold white]", style=border_color)
        self.console.print()

        # Indicate normal logging is active
        logger = logging.getLogger("wellwon.startup")
        logger.info("Startup complete - normal logging active")


class ProductionFormatter(logging.Formatter):
    """JSON formatter for production environments"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        import json

        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if configured
        if get_env_bool('LOG_JSON_INCLUDE_EXTRAS', True):
            if get_env_bool('LOG_USER_ID', True) and hasattr(record, 'user_id'):
                log_obj['user_id'] = record.user_id
            if get_env_bool('LOG_TRACE_ID', True) and hasattr(record, 'trace_id'):
                log_obj['trace_id'] = record.trace_id
            if get_env_bool('LOG_REQUEST_ID', True) and hasattr(record, 'request_id'):
                log_obj['request_id'] = record.request_id
            if get_env_bool('LOG_CORRELATION_ID', True) and hasattr(record, 'correlation_id'):
                log_obj['correlation_id'] = record.correlation_id

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def get_logger_level_from_env(logger_name: str, default_level: int) -> int:
    """Get logger level from environment variable."""
    # Convert logger name to env variable format
    # e.g., "aiokafka" -> "LOGLEVEL_AIOKAFKA"
    # e.g., "wellwon.infra.broker_conn_state" -> "LOGLEVEL_WELLWON_INFRA_BROKER_CONN_STATE"
    env_name = f"LOGLEVEL_{logger_name.replace('.', '_').upper()}"

    level_str = os.getenv(env_name, '').upper()
    if level_str:
        # Convert string level to logging constant
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'WARN': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }
        return level_map.get(level_str, default_level)

    return default_level


def setup_logging(
        service_name: str = "wellwon",
        log_level: Optional[str] = None,
        log_file: Optional[str] = None,
        enable_json: bool = None,
        rich_tracebacks: bool = True,
        service_type: str = None,
) -> None:
    """
    Configure beautiful logging with Rich framework.

    Args:
        service_name: Name of the service (e.g., "api", "worker")
        log_level: Override log level
        log_file: Optional log file path
        enable_json: Enable JSON formatting for production
        rich_tracebacks: Enable rich tracebacks (pretty exceptions)
        service_type: Type of service ("api", "data_integrity", "consumer", "connection_recovery")
    """
    # Reset startup collector for new session
    global _startup_collector, _service_type

    # Get service type from parameter or environment
    service_type = service_type or os.getenv('SERVICE_TYPE', 'api')
    _service_type = service_type

    _startup_collector = StartupCollector()
    _startup_collector.service_type = service_type

    # Get configuration from environment
    level = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = log_file or os.getenv("LOG_FILE")

    # Check if JSON format is enabled
    if enable_json is None:
        enable_json = get_env_bool('LOG_JSON_FORMAT', False)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Determine if we should use Rich output
    use_rich = RICH_AVAILABLE and not enable_json and (
            sys.stdout.isatty() or
            get_env_bool("FORCE_COLOR", False)
    )

    if use_rich:
        # Get console configuration from environment
        console_width = get_env_int('LOG_CONSOLE_WIDTH', 0) or None
        color_system = os.getenv('LOG_COLOR_SYSTEM', 'truecolor')
        if os.getenv('COLORTERM') == 'truecolor':
            color_system = 'truecolor'

        # Create Rich console with custom theme
        console = Console(
            theme=WELLWON_THEME,
            force_terminal=get_env_bool("FORCE_COLOR", False),
            width=console_width,
            legacy_windows=False,
            color_system=color_system,
        )

        # Create custom Rich handler
        rich_handler = SmartRichHandler(console=console)
        root_logger.addHandler(rich_handler)

    elif enable_json:
        # Production JSON handler
        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(ProductionFormatter())
        root_logger.addHandler(json_handler)

    else:
        # Fallback plain handler
        plain_handler = logging.StreamHandler(sys.stdout)
        plain_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)-8s] [%(name)-40s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        plain_handler.setFormatter(plain_formatter)
        root_logger.addHandler(plain_handler)

    # File handler (optional)
    if log_file:
        max_bytes = get_env_int('LOG_MAX_SIZE_MB', 100) * 1024 * 1024
        backup_count = get_env_int('LOG_BACKUP_COUNT', 5)
        file_encoding = os.getenv('LOG_FILE_ENCODING', 'utf-8')

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=file_encoding
        )
        # Always use plain formatter for files
        file_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)-8s] [%(name)-40s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Configure third-party loggers to reduce noise
    # Default noise configuration
    default_noise_config = {
        # Silence noisy libraries
        "aiokafka": logging.WARNING,
        "kafka": logging.WARNING,
        # Suppress benign sticky assignor rebalance warnings (temporary multi-assignments during generation phase)
        "aiokafka.coordinator.assignors.sticky.sticky_assignor": logging.ERROR,
        "urllib3": logging.WARNING,
        "asyncio": logging.WARNING,
        "aioredis": logging.WARNING,
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "websockets": logging.WARNING,
        "sqlalchemy.engine": logging.WARNING,
        "sqlalchemy.pool": logging.WARNING,
        "alembic": logging.INFO,
        "prometheus_client": logging.WARNING,
        "concurrent.futures": logging.WARNING,
        "parso": logging.WARNING,

        # WellWon components
        "wellwon.infra.broker_conn_state": logging.INFO,
        "wellwon.event_bus": logging.INFO,
        "wellwon.redpanda_adapter": logging.INFO,

        # Data Integrity specific loggers
        "wellwon.services.integrity_monitor": logging.INFO,
        "wellwon.workers.data_integrity": logging.DEBUG,
        "wellwon.infra.reliability.circuit_breaker": logging.INFO,
        "wellwon.infra.reliability.retry": logging.WARNING,
    }

    # Apply logger levels from environment or defaults
    for logger_name, default_level in default_noise_config.items():
        level = get_logger_level_from_env(logger_name, default_level)
        logging.getLogger(logger_name).setLevel(level)

    # Also check for additional third-party loggers
    additional_loggers = [
        "granian", "granian.access", "granian.server",
        "fastapi", "starlette", "multipart",
        "aiohttp", "aiohttp.access"
    ]

    for logger_name in additional_loggers:
        env_level = get_logger_level_from_env(logger_name, logging.WARNING)
        if env_level is not logging.WARNING:  # Only set if explicitly configured
            logging.getLogger(logger_name).setLevel(env_level)

    # CRITICAL FIX: Apply LOG_LEVEL environment variable to worker loggers
    # This ensures that when LOG_LEVEL=DEBUG is set, worker loggers will show DEBUG messages
    if level == "DEBUG":
        # Set specific worker loggers to DEBUG when global LOG_LEVEL is DEBUG
        worker_loggers = [
            f"wellwon.worker.{service_type}",
            f"wellwon.worker.{service_type}.state",
            f"wellwon.workers.{service_type}",
            "wellwon.worker.data-integrity",
            "wellwon.worker.connection-recovery",
            "wellwon.worker.consumer",
            "wellwon.worker.event-processor",
        ]

        for worker_logger_name in worker_loggers:
            logging.getLogger(worker_logger_name).setLevel(logging.DEBUG)

        # Also check for any LOGLEVEL_ environment variables that might override
        # and apply them AFTER setting the base levels
        for key, value in os.environ.items():
            if key.startswith('LOGLEVEL_'):
                # Extract logger name from environment variable
                logger_name_from_env = key[9:].lower()

                # Handle special cases for worker loggers
                if 'workers_data_integrity' in logger_name_from_env:
                    logger_name_from_env = 'wellwon.worker.data-integrity'
                elif 'workers_connection_recovery' in logger_name_from_env:
                    logger_name_from_env = 'wellwon.worker.connection-recovery'
                else:
                    logger_name_from_env = logger_name_from_env.replace('_', '.')

                try:
                    level_value = getattr(logging, value.upper())
                    logging.getLogger(logger_name_from_env).setLevel(level_value)
                except AttributeError:
                    pass  # Invalid log level, ignore

    # Log initial configuration
    logger = logging.getLogger(f"{service_name}.startup")
    logger.info(f"Logging configured for {service_name} service")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Keep all the other functions unchanged...
def force_normal_logging():
    """Force switch to normal logging mode (useful for workers)"""
    global _startup_collector
    if _startup_collector.is_collecting:
        # Find all handlers and force them to display startup
        for handler in logging.getLogger().handlers:
            if isinstance(handler, SmartRichHandler):
                handler._display_startup_summary()
                handler._normal_logging_active = True


def log_section(logger: logging.Logger, title: str):
    """Log a section separator"""
    if not RICH_AVAILABLE:
        logger.info(f"{'=' * 60}")
        logger.info(f"  {title.upper()}")
        logger.info(f"{'=' * 60}")
        return

    console = Console(theme=WELLWON_THEME)
    width = min(console.width - 2, 80)

    # Determine border color based on service type
    global _service_type
    border_colors = {
        'api': 'bright_green',
        'data_integrity': 'yellow',
        'consumer': 'magenta',
        'connection_recovery': 'cyan'
    }
    border_color = border_colors.get(_service_type, 'frame')

    # Create a section header
    header = Panel(
        f"[bold]{title.upper()}[/bold]",
        box=HEAVY,
        border_style=border_color,
        padding=(0, 1),
        width=width,
    )
    console.print()
    console.print(header)
    console.print()


def trigger_startup_display():
    """Manually trigger the startup summary display"""
    force_normal_logging()


def add_startup_info(service: str, status: str, category: str = 'core', **details):
    """Manually add service info to startup collector"""
    _startup_collector.add_service(service, status, category, details)


def log_worker_banner(logger: logging.Logger, worker_name: str, instance_id: str, version: str | None = None,
                      service_type: str = "api"):
    """Log a beautiful banner for worker startup"""
    # Get version dynamically if not provided
    if version is None:
        from app import __version__
        version = __version__
    # Update global service type if provided
    global _service_type
    _service_type = service_type

    if not RICH_AVAILABLE:
        logger.info(f"{'=' * 60}")
        logger.info(f"  {worker_name.upper()} v{version}")
        logger.info(f"  Instance: {instance_id}")
        logger.info(f"{'=' * 60}")
        return

    console = Console(theme=WELLWON_THEME)

    # Determine border color based on service type
    border_colors = {
        'api': 'bright_green',
        'data_integrity': 'yellow',
        'consumer': 'magenta',
        'connection_recovery': 'cyan'
    }
    border_color = border_colors.get(service_type, 'bright_blue')

    # Create banner content
    banner_text = f"""[bold cyan]{worker_name.upper()}[/bold cyan]
[dim]Version {version}[/dim]

[bold]Instance:[/bold] {instance_id}
[bold]PID:[/bold] {os.getpid()}
[bold]Started:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    # Create the banner
    banner = Panel(
        banner_text,
        title="[bold]WORKER STARTUP[/bold]",
        title_align="center",
        border_style=border_color,
        box=DOUBLE,
        padding=(1, 2),
        width=min(console.width - 2, 60),
    )

    console.print()
    console.print(banner)
    console.print()


def log_metrics_table(logger: logging.Logger, title: str, metrics: Dict[str, Any]):
    """Log metrics in a nice table format"""
    if not RICH_AVAILABLE:
        logger.info(f"{title}:")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value}")
        return

    console = Console(theme=WELLWON_THEME)

    # Create metrics table
    table = Table(
        title=title,
        show_header=True,
        header_style="white on grey30",
        box=MINIMAL,
        padding=(0, 1)
    )

    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="white", justify="right", width=15)

    for key, value in metrics.items():
        # Format the key nicely
        formatted_key = key.replace('_', ' ').title()

        # Format the value
        if isinstance(value, float):
            formatted_value = f"{value:,.2f}"
        elif isinstance(value, int):
            formatted_value = f"{value:,}"
        else:
            formatted_value = str(value)

        table.add_row(formatted_key, formatted_value)

    # Determine border color based on service type
    global _service_type
    border_colors = {
        'api': 'bright_green',
        'data_integrity': 'yellow',
        'consumer': 'magenta',
        'connection_recovery': 'cyan'
    }
    border_color = border_colors.get(_service_type, 'bright_blue')

    # Create panel for the table
    panel = Panel(
        table,
        border_style=border_color,
        box=ROUNDED,
        padding=(1, 1),
        width=min(console.width - 2, 60),
    )

    console.print()
    console.print(panel)
    console.print()


def log_status_update(logger: logging.Logger, status: str, details: Optional[Dict[str, Any]] = None):
    """Log a status update with optional details"""
    if not RICH_AVAILABLE:
        logger.info(f"Status: {status}")
        if details:
            for key, value in details.items():
                logger.info(f"  {key}: {value}")
        return

    console = Console(theme=WELLWON_THEME)

    # Build status text with better formatting for long values
    status_text = f"[bold]Status:[/bold] [info]{status}[/info]"

    if details:
        status_text += "\n\n[bold]Details:[/bold]\n"

        def format_value(value, indent_level=0):
            """Recursively format values, handling nested dicts and lists"""
            indent = "  " * indent_level

            if isinstance(value, dict):
                # Format nested dictionary
                formatted_lines = []
                for k, v in value.items():
                    formatted_key = k.replace('_', ' ').title()
                    if isinstance(v, (dict, list)):
                        formatted_lines.append(f"{indent}• {formatted_key}:")
                        formatted_lines.append(format_value(v, indent_level + 1))
                    else:
                        formatted_lines.append(f"{indent}• {formatted_key}: {v}")
                return "\n".join(formatted_lines)

            elif isinstance(value, list):
                # Format list items
                formatted_lines = []
                for item in value:
                    if isinstance(item, (dict, list)):
                        formatted_lines.append(format_value(item, indent_level + 1))
                    else:
                        formatted_lines.append(f"{indent}  - {item}")
                return "\n".join(formatted_lines)

            else:
                # Simple value
                return f"{indent}{value}"

        for key, value in details.items():
            formatted_key = key.replace('_', ' ').title()

            if isinstance(value, dict):
                # Nested dictionary - format on new lines
                status_text += f"  • {formatted_key}:\n"
                status_text += format_value(value, 2) + "\n"
            elif isinstance(value, list):
                # List - format each item
                status_text += f"  • {formatted_key}:\n"
                for item in value:
                    status_text += f"    - {item}\n"
            else:
                # Simple value
                value_str = str(value)
                if len(value_str) > 50:
                    # For very long values like worker IDs, put them on a new line
                    status_text += f"  • {formatted_key}:\n    {value_str}\n"
                else:
                    status_text += f"  • {formatted_key}: {value_str}\n"

    # Determine border color based on service type
    global _service_type
    border_colors = {
        'api': 'bright_green',
        'data_integrity': 'yellow',
        'consumer': 'magenta',
        'connection_recovery': 'cyan'
    }
    border_color = border_colors.get(_service_type, 'info')

    # Calculate optimal width based on content
    # For workers with long IDs, we need wider panels
    console_width = console.width if hasattr(console, 'width') else 120
    optimal_width = min(console_width - 2, 90)

    # Create status panel
    panel = Panel(
        status_text.strip(),
        border_style=border_color,
        box=MINIMAL,
        padding=(1, 2),
        width=optimal_width,
    )

    console.print()
    console.print(panel)


def log_error_box(logger: logging.Logger, error_msg: str, error_type: str = "Error"):
    """Log an error in a highlighted box"""
    if not RICH_AVAILABLE:
        logger.error(f"{error_type}: {error_msg}")
        return

    console = Console(theme=WELLWON_THEME)

    # Create error panel
    error_panel = Panel(
        f"[bold red]{error_type}:[/bold red]\n\n{error_msg}",
        border_style="red",
        box=HEAVY,
        padding=(1, 2),
        width=min(console.width - 2, 80),
    )

    console.print()
    console.print(error_panel)
    console.print()

# =============================================================================
# EOF
# =============================================================================
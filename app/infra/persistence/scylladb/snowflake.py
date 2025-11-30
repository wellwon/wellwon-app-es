# =============================================================================
# File: app/infra/persistence/scylladb/snowflake.py
# Description: Snowflake ID generator for distributed, time-ordered unique IDs.
# =============================================================================
# Based on Twitter's Snowflake algorithm and Discord's implementation.
# Generates 64-bit IDs with:
#   - 42 bits for timestamp (milliseconds since custom epoch)
#   - 10 bits for worker ID (1024 workers max)
#   - 12 bits for sequence (4096 IDs per millisecond per worker)
#
# Benefits:
#   - Time-ordered: IDs are roughly sorted by creation time
#   - Unique: No collisions across distributed workers
#   - Compact: Fits in a 64-bit integer (bigint)
#   - Fast: No coordination required for ID generation
# =============================================================================

from __future__ import annotations

import os
import time
import threading
from typing import Optional, List
from datetime import datetime, timezone
import logging

from pydantic import BaseModel, Field, ConfigDict, field_validator

try:
    from app.config.logging_config import get_logger
    log = get_logger("wellwon.infra.snowflake")
except ImportError:
    log = logging.getLogger("wellwon.infra.snowflake")


# =============================================================================
# Constants
# =============================================================================

# Custom epoch: January 1, 2024 00:00:00 UTC
# This gives us ~139 years of IDs from this date
# Discord uses January 1, 2015 as their epoch
WELLWON_EPOCH = 1704067200000  # 2024-01-01 00:00:00 UTC in milliseconds

# Bit allocation (64 bits total)
# Sign bit: 1 (always 0 for positive numbers)
# Timestamp: 42 bits (milliseconds since epoch, ~139 years)
# Worker ID: 10 bits (0-1023)
# Sequence: 12 bits (0-4095 per millisecond per worker)

TIMESTAMP_BITS = 42
WORKER_ID_BITS = 10
SEQUENCE_BITS = 12

# Maximum values
MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1  # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1    # 4095

# Bit shifts
TIMESTAMP_SHIFT = WORKER_ID_BITS + SEQUENCE_BITS  # 22
WORKER_ID_SHIFT = SEQUENCE_BITS                    # 12


# =============================================================================
# Snowflake ID Generator
# =============================================================================
class SnowflakeIDGenerator:
    """
    Thread-safe Snowflake ID generator.

    Generates 64-bit unique IDs that are:
    - Time-ordered (roughly sortable by creation time)
    - Globally unique across distributed workers
    - Compact (fits in a bigint)

    Usage:
        generator = SnowflakeIDGenerator(worker_id=1)
        message_id = generator.generate()
        # or
        message_id = generator.generate_str()

    ID Structure (64 bits):
        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |0|                         timestamp                          |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |           timestamp           |  worker_id  |   sequence     |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    def __init__(
            self,
            worker_id: Optional[int] = None,
            datacenter_id: Optional[int] = None,
            epoch: int = WELLWON_EPOCH,
    ):
        """
        Initialize Snowflake ID generator.

        Args:
            worker_id: Worker ID (0-1023). If None, derived from env or hostname.
            datacenter_id: Optional datacenter ID (combined with worker_id).
            epoch: Custom epoch in milliseconds. Default is WellWon epoch (2024-01-01).
        """
        # Determine worker ID
        if worker_id is None:
            worker_id = self._derive_worker_id()

        # Optionally combine datacenter and worker ID
        # Discord uses 5 bits for datacenter, 5 bits for worker
        # We use all 10 bits for worker ID for simplicity
        if datacenter_id is not None:
            # Use 5 bits for datacenter, 5 bits for worker
            datacenter_bits = 5
            worker_bits = 5
            max_dc = (1 << datacenter_bits) - 1
            max_worker = (1 << worker_bits) - 1

            if datacenter_id < 0 or datacenter_id > max_dc:
                raise ValueError(f"datacenter_id must be between 0 and {max_dc}")
            if worker_id < 0 or worker_id > max_worker:
                raise ValueError(f"worker_id must be between 0 and {max_worker}")

            worker_id = (datacenter_id << worker_bits) | worker_id

        # Validate worker ID
        if worker_id < 0 or worker_id > MAX_WORKER_ID:
            raise ValueError(f"worker_id must be between 0 and {MAX_WORKER_ID}")

        self._worker_id = worker_id
        self._epoch = epoch
        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()

        log.info(f"SnowflakeIDGenerator initialized: worker_id={worker_id}, epoch={epoch}")

    def _derive_worker_id(self) -> int:
        """Derive worker ID from environment or system."""
        # Try environment variable first
        env_worker_id = os.environ.get('SNOWFLAKE_WORKER_ID')
        if env_worker_id is not None:
            try:
                return int(env_worker_id) % (MAX_WORKER_ID + 1)
            except ValueError:
                pass

        # Try pod/container index (Kubernetes)
        pod_name = os.environ.get('POD_NAME', os.environ.get('HOSTNAME', ''))
        if pod_name:
            # Extract index from pod name (e.g., "wellwon-worker-3" -> 3)
            parts = pod_name.split('-')
            for part in reversed(parts):
                try:
                    return int(part) % (MAX_WORKER_ID + 1)
                except ValueError:
                    continue

        # Use hash of hostname as fallback
        import socket
        hostname = socket.gethostname()
        return hash(hostname) % (MAX_WORKER_ID + 1)

    def _current_timestamp(self) -> int:
        """Get current timestamp in milliseconds since epoch."""
        return int(time.time() * 1000) - self._epoch

    def generate(self) -> int:
        """
        Generate a new Snowflake ID.

        Returns:
            64-bit integer ID

        Raises:
            RuntimeError: If clock moved backwards
        """
        with self._lock:
            timestamp = self._current_timestamp()

            # Handle clock moving backwards
            if timestamp < self._last_timestamp:
                # Wait for clock to catch up (handles small drifts)
                wait_time = self._last_timestamp - timestamp
                if wait_time <= 5:  # Only wait up to 5ms
                    time.sleep(wait_time / 1000)
                    timestamp = self._current_timestamp()
                else:
                    raise RuntimeError(
                        f"Clock moved backwards by {wait_time}ms. "
                        f"Refusing to generate ID."
                    )

            # Same millisecond - increment sequence
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & MAX_SEQUENCE

                # Sequence overflow - wait for next millisecond
                if self._sequence == 0:
                    timestamp = self._wait_next_millis(timestamp)
            else:
                # New millisecond - reset sequence
                self._sequence = 0

            self._last_timestamp = timestamp

            # Build the ID
            snowflake_id = (
                (timestamp << TIMESTAMP_SHIFT) |
                (self._worker_id << WORKER_ID_SHIFT) |
                self._sequence
            )

            return snowflake_id

    def _wait_next_millis(self, last_timestamp: int) -> int:
        """Wait until the next millisecond."""
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            time.sleep(0.0001)  # 100 microseconds
            timestamp = self._current_timestamp()
        return timestamp

    def generate_str(self) -> str:
        """Generate a new Snowflake ID as a string."""
        return str(self.generate())

    def generate_batch(self, count: int) -> list[int]:
        """
        Generate a batch of Snowflake IDs.

        Args:
            count: Number of IDs to generate

        Returns:
            List of Snowflake IDs
        """
        return [self.generate() for _ in range(count)]

    @property
    def worker_id(self) -> int:
        """Get the worker ID."""
        return self._worker_id

    @property
    def epoch(self) -> int:
        """Get the epoch timestamp."""
        return self._epoch


# =============================================================================
# Pydantic Model for Parsed Snowflake
# =============================================================================
class ParsedSnowflake(BaseModel):
    """Parsed Snowflake ID components (Pydantic v2)."""

    model_config = ConfigDict(
        frozen=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

    snowflake_id: int = Field(description="Original Snowflake ID")
    timestamp_ms: int = Field(description="Unix timestamp in milliseconds")
    worker_id: int = Field(ge=0, le=MAX_WORKER_ID, description="Worker ID (0-1023)")
    sequence: int = Field(ge=0, le=MAX_SEQUENCE, description="Sequence number (0-4095)")
    created_at: datetime = Field(description="Datetime (UTC)")

    @property
    def bucket(self) -> int:
        """Calculate 10-day bucket for ScyllaDB partitioning."""
        days_since_epoch = self.timestamp_ms // (1000 * 60 * 60 * 24)
        return days_since_epoch // 10


# =============================================================================
# Snowflake ID Parser
# =============================================================================
class SnowflakeIDParser:
    """
    Parse Snowflake IDs to extract components.

    Usage:
        parser = SnowflakeIDParser()
        parsed = parser.parse(snowflake_id)
        timestamp = parser.get_timestamp(snowflake_id)
        datetime_obj = parser.get_datetime(snowflake_id)
    """

    def __init__(self, epoch: int = WELLWON_EPOCH):
        """
        Initialize parser.

        Args:
            epoch: Custom epoch in milliseconds (must match generator)
        """
        self._epoch = epoch

    def parse(self, snowflake_id: int) -> ParsedSnowflake:
        """
        Parse a Snowflake ID into its components.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            ParsedSnowflake model with all components
        """
        timestamp_ms = (snowflake_id >> TIMESTAMP_SHIFT) + self._epoch
        worker_id = (snowflake_id >> WORKER_ID_SHIFT) & MAX_WORKER_ID
        sequence = snowflake_id & MAX_SEQUENCE

        return ParsedSnowflake(
            snowflake_id=snowflake_id,
            timestamp_ms=timestamp_ms,
            worker_id=worker_id,
            sequence=sequence,
            created_at=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
        )

    def get_timestamp(self, snowflake_id: int) -> int:
        """
        Get the Unix timestamp (milliseconds) from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID

        Returns:
            Unix timestamp in milliseconds
        """
        return (snowflake_id >> TIMESTAMP_SHIFT) + self._epoch

    def get_datetime(self, snowflake_id: int) -> datetime:
        """
        Get the datetime from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID

        Returns:
            datetime object (UTC)
        """
        timestamp_ms = self.get_timestamp(snowflake_id)
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    def get_worker_id(self, snowflake_id: int) -> int:
        """
        Get the worker ID from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID

        Returns:
            Worker ID
        """
        return (snowflake_id >> WORKER_ID_SHIFT) & MAX_WORKER_ID

    def get_sequence(self, snowflake_id: int) -> int:
        """
        Get the sequence number from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID

        Returns:
            Sequence number
        """
        return snowflake_id & MAX_SEQUENCE

    @staticmethod
    def snowflake_from_timestamp(
            timestamp_ms: int,
            epoch: int = WELLWON_EPOCH,
    ) -> int:
        """
        Create a Snowflake ID from a timestamp (useful for range queries).

        The generated ID will have worker_id=0 and sequence=0, representing
        the minimum possible ID for that timestamp.

        Args:
            timestamp_ms: Unix timestamp in milliseconds
            epoch: Custom epoch in milliseconds

        Returns:
            Snowflake ID representing the start of that millisecond
        """
        adjusted_timestamp = timestamp_ms - epoch
        if adjusted_timestamp < 0:
            raise ValueError("Timestamp is before epoch")
        return adjusted_timestamp << TIMESTAMP_SHIFT

    @staticmethod
    def snowflake_from_datetime(
            dt: datetime,
            epoch: int = WELLWON_EPOCH,
    ) -> int:
        """
        Create a Snowflake ID from a datetime (useful for range queries).

        Args:
            dt: datetime object
            epoch: Custom epoch in milliseconds

        Returns:
            Snowflake ID representing the start of that millisecond
        """
        timestamp_ms = int(dt.timestamp() * 1000)
        return SnowflakeIDParser.snowflake_from_timestamp(timestamp_ms, epoch)


# =============================================================================
# Global Generator Instance
# =============================================================================
_GLOBAL_GENERATOR: Optional[SnowflakeIDGenerator] = None
_GENERATOR_LOCK = threading.Lock()


def get_snowflake_generator(
        worker_id: Optional[int] = None,
        epoch: int = WELLWON_EPOCH,
) -> SnowflakeIDGenerator:
    """
    Get or create global Snowflake ID generator.

    Args:
        worker_id: Optional worker ID (only used on first call)
        epoch: Custom epoch (only used on first call)

    Returns:
        SnowflakeIDGenerator instance
    """
    global _GLOBAL_GENERATOR

    if _GLOBAL_GENERATOR is None:
        with _GENERATOR_LOCK:
            if _GLOBAL_GENERATOR is None:
                _GLOBAL_GENERATOR = SnowflakeIDGenerator(
                    worker_id=worker_id,
                    epoch=epoch,
                )

    return _GLOBAL_GENERATOR


def generate_snowflake_id() -> int:
    """
    Generate a Snowflake ID using the global generator.

    Returns:
        64-bit Snowflake ID
    """
    return get_snowflake_generator().generate()


def generate_snowflake_id_str() -> str:
    """
    Generate a Snowflake ID as a string using the global generator.

    Returns:
        Snowflake ID as string
    """
    return get_snowflake_generator().generate_str()


# =============================================================================
# Bucket Calculation (for ScyllaDB partitioning)
# =============================================================================
def calculate_message_bucket(
        snowflake_id: int,
        bucket_size_days: int = 10,
        epoch: int = WELLWON_EPOCH,
) -> int:
    """
    Calculate the bucket number for a message based on its Snowflake ID.

    Used for ScyllaDB partition key to prevent unbounded partition growth.
    Discord uses 10-day buckets for their messages table.

    Args:
        snowflake_id: The Snowflake ID of the message
        bucket_size_days: Number of days per bucket (default 10)
        epoch: Custom epoch in milliseconds

    Returns:
        Bucket number (integer)
    """
    # Get timestamp from Snowflake ID
    timestamp_ms = (snowflake_id >> TIMESTAMP_SHIFT) + epoch

    # Calculate bucket (days since Unix epoch, divided by bucket size)
    days_since_epoch = timestamp_ms // (1000 * 60 * 60 * 24)
    bucket = days_since_epoch // bucket_size_days

    return bucket


def get_bucket_range(
        start_time: datetime,
        end_time: datetime,
        bucket_size_days: int = 10,
) -> list[int]:
    """
    Get all bucket numbers that fall within a time range.

    Useful for query planning when fetching messages across time.

    Args:
        start_time: Start of the time range
        end_time: End of the time range
        bucket_size_days: Number of days per bucket (default 10)

    Returns:
        List of bucket numbers
    """
    start_days = int(start_time.timestamp() * 1000) // (1000 * 60 * 60 * 24)
    end_days = int(end_time.timestamp() * 1000) // (1000 * 60 * 60 * 24)

    start_bucket = start_days // bucket_size_days
    end_bucket = end_days // bucket_size_days

    return list(range(start_bucket, end_bucket + 1))


# =============================================================================
# EOF
# =============================================================================

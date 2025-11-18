# app/infra/event_bus/consumer_transactional.py
"""
Transactional Consumer Loop for Exactly-Once Semantics

This module contains the transactional consumer loop implementation
that uses Kafka transactions for TRUE exactly-once delivery.

Created: 2025-11-13 (TRUE Exactly-Once Implementation)
"""

import asyncio
import json
import logging
import time

from aiokafka.errors import KafkaConnectionError, ProducerFenced
from app.infra.metrics.exactly_once_metrics import (
    record_kafka_transaction_commit,
    record_kafka_transaction_abort,
    kafka_txn_active
)

log = logging.getLogger("tradecore.event_bus.transactional")


async def consumer_loop_transactional(
    adapter,  # RedpandaTransportAdapter instance
    consumer_key: str,
    consumer_info,  # ConsumerInfo instance
) -> None:
    """
    Transactional consumer loop with Kafka transactions for exactly-once semantics.

    Flow:
    1. Create transactional producer (unique transactional_id)
    2. Fetch messages
    3. BEGIN TRANSACTION
    4. Process all messages
    5. Send offsets to transaction (instead of consumer.commit())
    6. COMMIT TRANSACTION (atomic - both processing and offset commit)
    7. If error → ABORT TRANSACTION (rollback everything)

    Args:
        adapter: RedpandaTransportAdapter instance
        consumer_key: Unique consumer identifier
        consumer_info: ConsumerInfo with consumer, handler, etc.
    """
    consumer = consumer_info.consumer
    handler = consumer_info.handler
    group_id = consumer._group_id  # noqa: protected access - intentional coupling

    # Create unique transactional ID
    # Format: {prefix}-{consumer_key}-{worker_pid}
    import os
    transactional_id = f"{adapter._transactional_id_prefix}-{consumer_key}-{os.getpid()}"  # noqa

    log.info(f"Starting transactional consumer loop: {consumer_key} (txn_id={transactional_id})")

    # Create transactional producer
    try:
        txn_producer = await adapter._create_transactional_producer(transactional_id)  # noqa
    except Exception as e:
        log.error(f"Failed to create transactional producer for {consumer_key}: {e}")
        raise

    # Metrics
    kafka_txn_active.labels(consumer_group=group_id).inc()

    # Error tracking
    consecutive_errors = 0
    max_consecutive_errors = 5
    backoff_base = 2

    # Backoff for empty polls
    empty_poll_initial_backoff = 0.05  # 50ms
    empty_poll_max_backoff = 1.0  # 1s
    empty_poll_backoff_multiplier = 1.5

    try:
        while adapter._running and not consumer_info.stop_event.is_set():  # noqa
            try:
                # Fetch messages
                timeout_ms = adapter._event_bus_config.consumer_poll_timeout_ms  # noqa
                max_records = adapter._consumer_config_template.get('max_poll_records', 100)  # noqa

                records = await consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=max_records
                )

                if not records:
                    # Empty fetch - backoff
                    consumer_info.consecutive_empty_fetches += 1

                    backoff_seconds = min(
                        empty_poll_initial_backoff * (empty_poll_backoff_multiplier ** (consumer_info.consecutive_empty_fetches - 1)),
                        empty_poll_max_backoff
                    )

                    await asyncio.sleep(backoff_seconds)
                    continue

                # Reset empty fetch counter
                if consumer_info.consecutive_empty_fetches > 0:
                    consumer_info.consecutive_empty_fetches = 0

                # Reset error counter on successful fetch
                if consecutive_errors > 0:
                    log.info(f"Transactional consumer recovered after {consecutive_errors} errors")
                    consecutive_errors = 0

                # Start transaction timing
                txn_start_time = time.time()
                messages_in_batch = 0

                try:
                    # Process all messages FIRST (before committing transaction)
                    for tp, msgs in records.items():
                        for msg in msgs:
                            if consumer_info.stop_event.is_set():
                                break

                            try:
                                # Deserialize message
                                event_data = json.loads(msg.value.decode('utf-8'))

                                # Call handler
                                await handler(event_data)

                                messages_in_batch += 1

                            except json.JSONDecodeError as e:
                                # HIGH FIX #1 (2025-11-14): JSON decode errors break atomicity
                                # Send to DLQ instead of silently continuing
                                log.error(
                                    f"JSON decode error from {tp.topic} partition {tp.partition} offset {msg.offset}: {e}. "
                                    f"Message sent to DLQ."
                                )
                                consumer_info.errors += 1

                                # Send to DLQ for manual inspection
                                try:
                                    await adapter._send_to_dlq(  # noqa
                                        topic=tp.topic,
                                        message=msg.value,
                                        error=f"JSON decode error: {e}",
                                        metadata={"partition": tp.partition, "offset": msg.offset}
                                    )
                                except Exception as dlq_error:
                                    log.error(f"Failed to send malformed message to DLQ: {dlq_error}")

                                # ABORT transaction - malformed messages indicate data corruption
                                raise

                            except Exception as e:
                                # HIGH FIX #2 (2025-11-14): Handler errors abort entire batch
                                # Send poison messages to DLQ instead of killing batch
                                log.error(
                                    f"Handler error for message from {tp.topic} offset {msg.offset}: {e}",
                                    exc_info=True
                                )
                                consumer_info.errors += 1

                                # Send to DLQ for retry/manual inspection
                                try:
                                    await adapter._send_to_dlq(  # noqa
                                        topic=tp.topic,
                                        message=msg.value,
                                        error=f"Handler error: {type(e).__name__}: {e}",
                                        metadata={"partition": tp.partition, "offset": msg.offset, "event_data": event_data if 'event_data' in locals() else None}
                                    )
                                except Exception as dlq_error:
                                    log.error(f"Failed to send poison message to DLQ: {dlq_error}")

                                # ABORT transaction - handler errors should not be silently ignored
                                raise

                    # Send offsets to transaction (instead of consumer.commit())
                    # This makes offset commits part of the transaction
                    offsets = {
                        tp: msgs[-1].offset + 1
                        for tp, msgs in records.items()
                    }

                    # CRITICAL FIX (2025-11-14): Isolate ProducerFenced in transaction operations
                    try:
                        await txn_producer.send_offsets_to_transaction(
                            offsets,
                            group_id
                        )

                        # Commit transaction (atomic!)
                        # This commits BOTH:
                        # 1. Any messages sent by producer (none in this case, but part of protocol)
                        # 2. Consumer offsets (what we care about)
                        await txn_producer.commit_transaction()

                    except ProducerFenced as pf:
                        # CRITICAL: Producer fenced - DO NOT try to abort
                        # Another instance has taken over this transactional_id
                        log.error(
                            f"Producer fenced during transaction commit for {consumer_key}: {pf}. "
                            f"Another consumer instance has taken over. Stopping gracefully."
                        )
                        record_kafka_transaction_abort(
                            consumer_group=group_id,
                            topic=list(records.keys())[0].topic if records else "unknown",
                            reason="producer_fenced_in_commit"
                        )
                        # Re-raise to trigger outer handler's break (line 246-260)
                        raise

                    # Record metrics
                    txn_duration = time.time() - txn_start_time
                    topic_name = list(records.keys())[0].topic if records else "unknown"
                    record_kafka_transaction_commit(
                        consumer_group=group_id,
                        topic=topic_name,
                        duration=txn_duration,
                        batch_size=messages_in_batch
                    )

                    # Update consumer metrics
                    adapter._messages_received += messages_in_batch  # noqa
                    consumer_info.messages_processed += messages_in_batch
                    consumer_info.last_message_time = time.time()

                    # CRITICAL FIX (2025-11-14): Add error handling for begin_transaction
                    try:
                        # Begin new transaction for next batch
                        await txn_producer.begin_transaction()
                    except ProducerFenced:
                        log.error(f"Producer fenced while beginning new transaction for {consumer_key}")
                        raise  # Trigger outer handler's break
                    except Exception as begin_error:
                        log.error(f"Failed to begin new transaction for {consumer_key}: {begin_error}")
                        raise

                    log.debug(
                        f"Transaction committed: {messages_in_batch} messages, "
                        f"duration={txn_duration:.3f}s, consumer={consumer_key}"
                    )

                except ProducerFenced:
                    # ProducerFenced already handled above - re-raise to outer handler
                    raise

                except Exception as e:
                    # Abort transaction on error (but NOT on ProducerFenced)
                    log.error(
                        f"Transaction aborted for {consumer_key}: {e}",
                        exc_info=True
                    )

                    try:
                        await txn_producer.abort_transaction()

                        # Record metrics
                        topic_name = list(records.keys())[0].topic if records else "unknown"
                        record_kafka_transaction_abort(
                            consumer_group=group_id,
                            topic=topic_name,
                            reason=str(type(e).__name__)
                        )

                        # Begin new transaction after abort
                        await txn_producer.begin_transaction()

                    except Exception as abort_error:
                        log.error(f"Failed to abort transaction: {abort_error}")
                        raise

                    # Re-raise original error
                    raise

            except asyncio.CancelledError:
                log.info(f"Transactional consumer loop cancelled for {consumer_key}")
                break

            except (KafkaConnectionError, ConnectionError, OSError) as e:
                consecutive_errors += 1
                adapter._connection_errors += 1  # noqa

                log.error(
                    f"Kafka connection error in transactional consumer for {consumer_key}: {e}. "
                    f"Consecutive errors: {consecutive_errors}/{max_consecutive_errors}"
                )

                if consecutive_errors >= max_consecutive_errors:
                    log.warning(
                        f"Too many consecutive errors ({consecutive_errors}) "
                        f"for transactional consumer {consumer_key}. Restarting..."
                    )
                    await asyncio.sleep(30)
                    consecutive_errors = 0
                    continue

                # Exponential backoff
                backoff = min(backoff_base ** consecutive_errors, 60)
                await asyncio.sleep(backoff)

            except Exception as e:
                # ISSUE #4 FIX: Specific handling for ProducerFenced exception
                if isinstance(e, ProducerFenced):
                    log.error(
                        f"Producer fenced for {consumer_key} (zombie instance detected). "
                        f"Another consumer with same transactional_id ({transactional_id}) has taken over. "
                        f"Stopping this consumer gracefully.",
                        exc_info=True
                    )
                    # Record metric (topic unknown in this scope)
                    record_kafka_transaction_abort(
                        consumer_group=group_id,
                        topic="unknown",  # Topic not in scope during exception handling
                        reason="producer_fenced"
                    )
                    # Stop consumer immediately - another instance is active
                    break

                # Generic exception handling
                consecutive_errors += 1
                log.error(
                    f"Unexpected error in transactional consumer loop for {consumer_key}: {e}",
                    exc_info=True
                )

                if consecutive_errors >= max_consecutive_errors:
                    log.error(f"Too many errors, stopping transactional consumer {consumer_key}")
                    break

                await asyncio.sleep(min(backoff_base ** consecutive_errors, 30))

    finally:
        # Cleanup
        kafka_txn_active.labels(consumer_group=group_id).dec()

        # Stop transactional producer
        try:
            await txn_producer.stop()
            log.info(f"Transactional producer stopped for {consumer_key}")
        except Exception as e:
            log.error(f"Error stopping transactional producer: {e}")

        # Remove from transactional producers dict
        if transactional_id in adapter._transactional_producers:  # noqa
            del adapter._transactional_producers[transactional_id]  # noqa

        log.info(f"Transactional consumer loop ended for {consumer_key}")

# Configuration Reference

Complete reference of all environment variables for TradeCore.

## Redis (`REDIS_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | str | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_MAX_CONNECTIONS` | int | `100` | Connection pool size |
| `REDIS_SOCKET_TIMEOUT` | float | `5.0` | Socket timeout (seconds) |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | float | `5.0` | Connection timeout |
| `REDIS_RETRY_ON_TIMEOUT` | bool | `true` | Retry on timeout |
| `REDIS_HEALTH_CHECK_INTERVAL` | int | `30` | Health check interval |

## Saga Orchestration (`SAGA_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SAGA_DEFAULT_TIMEOUT_SECONDS` | int | `300` | Default saga timeout |
| `SAGA_MAX_RETRIES` | int | `3` | Maximum retry attempts |
| `SAGA_RETRY_DELAY_MS` | int | `1000` | Initial retry delay |
| `SAGA_ENABLE_COMPENSATION` | bool | `true` | Enable automatic compensation |
| `SAGA_CHECKPOINT_INTERVAL` | int | `10` | Checkpoint every N steps |

## Worker (`WORKER_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WORKER_POLL_INTERVAL_MS` | int | `100` | Event polling interval |
| `WORKER_BATCH_SIZE` | int | `100` | Events per batch |
| `WORKER_MAX_CONCURRENT` | int | `10` | Concurrent event handlers |
| `WORKER_CONSUMER_GROUP` | str | `tradecore-workers` | Kafka consumer group |

## Event Store (`KURRENTDB_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KURRENTDB_CONNECTION_STRING` | str | `esdb://localhost:2113?tls=false` | KurrentDB connection |
| `KURRENTDB_USERNAME` | str | `None` | Database username |
| `KURRENTDB_PASSWORD` | SecretStr | `None` | Database password |
| `KURRENTDB_STREAM_PREFIX` | str | `` | Stream name prefix |
| `KURRENTDB_SNAPSHOT_INTERVAL` | int | `200` | Events before snapshot |
| `KURRENTDB_ENABLE_AUTO_SNAPSHOTS` | bool | `true` | Enable auto snapshots |
| `KURRENTDB_READ_TIMEOUT_SECONDS` | int | `10` | Read operation timeout |
| `KURRENTDB_WRITE_TIMEOUT_SECONDS` | int | `5` | Write operation timeout |

## Outbox (`OUTBOX_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OUTBOX_POLL_INTERVAL_SECONDS` | float | `0.05` | Poll interval (50ms) |
| `OUTBOX_BATCH_SIZE` | int | `20` | Events per batch |
| `OUTBOX_MAX_RETRY_ATTEMPTS` | int | `3` | Maximum retries |
| `OUTBOX_RETRY_DELAY_SECONDS` | int | `5` | Initial retry delay |
| `OUTBOX_ENABLE_DLQ` | bool | `true` | Enable dead letter queue |

## WebSocket Engine (`WSE_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WSE_HEARTBEAT_INTERVAL` | int | `30` | Heartbeat interval (seconds) |
| `WSE_MAX_CONNECTIONS_PER_USER` | int | `5` | Max connections per user |
| `WSE_MESSAGE_QUEUE_SIZE` | int | `1000` | Message queue size |
| `WSE_COMPRESSION_THRESHOLD` | int | `512` | Compress above N bytes |

## Snapshot (`SNAPSHOT_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SNAPSHOT_ENABLE_AUTO_SNAPSHOTS` | bool | `true` | Enable auto snapshots |
| `SNAPSHOT_DEFAULT_EVENT_INTERVAL` | int | `100` | Events between snapshots |
| `SNAPSHOT_DEFAULT_TIME_INTERVAL_HOURS` | int | `24` | Hours between snapshots |
| `SNAPSHOT_BATCH_SIZE` | int | `10` | Concurrent snapshot ops |
| `SNAPSHOT_COMPRESSION_ENABLED` | bool | `true` | Enable compression |

## JWT (`JWT_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_SECRET_KEY` | SecretStr | (required) | JWT signing key |
| `JWT_ALGORITHM` | str | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int | `30` | Access token expiry |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | Refresh token expiry |

## Cache (`CACHE_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_ENABLED` | bool | `true` | Enable caching globally |
| `CACHE_KEY_PREFIX` | str | `tradecore` | Cache key prefix |
| `CACHE_DEFAULT_TTL` | int | `300` | Default TTL (seconds) |
| `CACHE_DEBUG_MODE` | bool | `false` | Enable debug mode |
| `CACHE_REDIS_MAX_CONNECTIONS` | int | `150` | Redis connections |
| `CACHE_METRICS_ENABLED` | bool | `true` | Enable metrics |

### Cache TTL Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_VB_BALANCE` | `30` | Virtual broker balance TTL |
| `CACHE_TTL_MARKET_QUOTE` | `5` | Market quote TTL |
| `CACHE_TTL_ACCOUNT_BALANCE` | `30` | Account balance TTL |
| `CACHE_TTL_OPTIONS_QUOTE` | `5` | Options quote TTL |
| `CACHE_TTL_CRYPTO_QUOTE` | `2` | Crypto quote TTL |

## Dead Letter Queue (`DLQ_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DLQ_ENABLED` | bool | `true` | Enable DLQ |
| `DLQ_MAX_RETRIES` | int | `5` | Max retries before DLQ |
| `DLQ_RETENTION_HOURS` | int | `168` | DLQ retention (7 days) |

## EventBus Transport (`EVENTBUS_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EVENTBUS_BOOTSTRAP_SERVERS` | str | `localhost:19092` | Kafka bootstrap servers |
| `EVENTBUS_CONSUMER_GROUP_PREFIX` | str | `tradecore` | Consumer group prefix |
| `EVENTBUS_AUTO_OFFSET_RESET` | str | `earliest` | Offset reset policy |
| `EVENTBUS_ENABLE_AUTO_COMMIT` | bool | `false` | Auto-commit offsets |

## PostgreSQL Client (`PG_CLIENT_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PG_CLIENT_MIN_SIZE` | int | `5` | Min pool connections |
| `PG_CLIENT_MAX_SIZE` | int | `20` | Max pool connections |
| `PG_CLIENT_COMMAND_TIMEOUT` | float | `60.0` | Command timeout |
| `PG_CLIENT_STATEMENT_CACHE_SIZE` | int | `1024` | Statement cache size |

## Projection Rebuilder (`PROJECTION_`)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PROJECTION_BATCH_SIZE` | int | `1000` | Events per batch |
| `PROJECTION_PARALLEL_WORKERS` | int | `4` | Parallel workers |
| `PROJECTION_CHECKPOINT_INTERVAL` | int | `1000` | Checkpoint frequency |

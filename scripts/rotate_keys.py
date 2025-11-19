"""
WellWon Key Rotation Tool – v1.0.0
----------------------------------
• Re-encrypts Redis values using new FERNET_KEY
• Skips plaintext fields like roles
• Supports dry-run, backup mode, and error logging

Usage:
1. Set old key: FERNET_KEY_OLD=<current key>
2. Generate new: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
3. Set new key: FERNET_KEY=<new key>
4. Run: python scripts/rotate_keys.py
"""

import os
import asyncio
from typing import List
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

# ───────────────────────────────────────────────
# Environment + Clients
# ───────────────────────────────────────────────

OLD_KEY = os.getenv("FERNET_KEY_OLD")
NEW_KEY = os.getenv("FERNET_KEY")

assert OLD_KEY and NEW_KEY, "Both FERNET_KEY_OLD and FERNET_KEY must be set"

fernet_old = Fernet(OLD_KEY.encode())
fernet_new = Fernet(NEW_KEY.encode())

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
client = redis.from_url(REDIS_URL, decode_responses=True)

# ───────────────────────────────────────────────
# Config Flags
# ───────────────────────────────────────────────

BACKUP_KEYS = True       # Store under backup:{key}
DRY_RUN     = False      # No save if True
VERBOSE     = True       # Print each key rotated

# ───────────────────────────────────────────────
# Redis Keys to Rotate (encrypted fields only)
# ───────────────────────────────────────────────

ENCRYPTED_KEYS: List[str] = [
    # User sensitive data
    "user:*:password",
    "user:*:secret",
    # API keys and tokens
    "api_key:*",
    "telegram:*:token",
    # Session data
    "session:*:data",
]

# ───────────────────────────────────────────────
# Rotation Logic
# ───────────────────────────────────────────────

async def rotate_key(key: str) -> None:
    try:
        value = await client.get(key)
        if not value:
            return

        decrypted = fernet_old.decrypt(value.encode()).decode()
        re_encrypted = fernet_new.encrypt(decrypted.encode()).decode()

        if BACKUP_KEYS:
            await client.set(f"backup:{key}", value)

        if not DRY_RUN:
            await client.set(key, re_encrypted)

        if VERBOSE:
            print(f"[✓] Re-encrypted: {key}")

    except InvalidToken:
        print(f"[✗] Cannot decrypt: {key} (skipped)")
    except Exception as e:
        print(f"[!] Error on {key}: {e}")

async def rotate_all():
    total = 0
    for pattern in ENCRYPTED_KEYS:
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                await rotate_key(key)
                total += 1
            if cursor == 0:
                break

    print(f"\n✅ Key rotation complete. {total} keys scanned.")

if __name__ == "__main__":
    asyncio.run(rotate_all())
#!/usr/bin/env python3
"""
Generate Telegram Session String for MTProto (Telethon).

Run this script once to generate a session string, then add it to your .env file.
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("\n" + "=" * 60)
    print("Telegram Session String Generator")
    print("=" * 60)
    print("\nThis script will generate a session string for MTProto.")
    print("You need API credentials from https://my.telegram.org\n")

    api_id = int(input("Enter API ID: "))
    api_hash = input("Enter API HASH: ")
    phone = input("Enter phone number (format: +7...): ")

    print("\nConnecting to Telegram...")
    print("You will receive a code in Telegram app.\n")

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter the code you received: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "password" in str(e).lower() or "2fa" in str(e).lower() or "SessionPasswordNeeded" in str(type(e).__name__):
                password = input("Enter your 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise

    session_string = client.session.save()
    await client.disconnect()

    print("\n" + "=" * 60)
    print("SUCCESS! Session string generated.")
    print("=" * 60)
    print("\nAdd these lines to your .env file:\n")
    print(f"TELEGRAM_API_ID={api_id}")
    print(f"TELEGRAM_API_HASH={api_hash}")
    print(f"TELEGRAM_ADMIN_PHONE={phone}")
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    print("TELEGRAM_ENABLE_MTPROTO=true")
    print("\n" + "=" * 60)
    print("IMPORTANT: Keep the session string secret!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("Введите API ID: "))
api_hash = input("Введите API HASH: ")
phone = input("Введите номер телефона (в формате +7...): ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone=phone)
    print("\nSession string:")
    print(client.session.save())
    print("\nСкопируйте эту строку и храните в секрете!") 
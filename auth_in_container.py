from telethon.sync import TelegramClient
from core.config import API_ID, API_HASH, SESSION_NAME
import os

os.makedirs('sessions', exist_ok=True)

print('=== Telethon Authorization ===')
print(f'API_ID: {API_ID}')
print(f'SESSION_NAME: {SESSION_NAME}')

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
client.start()

if client.is_user_authorized():
    me = client.get_me()
    print(f'\n✅ SUCCESS! Logged in as: {me.first_name}')
else:
    print('\n❌ FAILED')

client.disconnect()

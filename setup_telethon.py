#!/usr/bin/env python3
"""
Telethon Session Setup Script
Run this ONCE to authorize Telethon and create session file
"""
import os
from telethon.sync import TelegramClient
from core.config import API_ID, API_HASH

# Use sessions directory
SESSION_NAME = "sessions/smm_bot"

# Create sessions directory if it doesn't exist
os.makedirs("sessions", exist_ok=True)

def main():
    print("=" * 50)
    print("Telethon Session Setup")
    print("=" * 50)
    print("\nThis script will create a Telethon session file.")
    print("You'll need to enter your phone number and verification code.\n")

    # Create client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print(f"Connecting to Telegram...")
    client.start()

    print("\n✅ Successfully authorized!")
    print(f"✅ Session file created: {SESSION_NAME}.session")
    print("\nYou can now use the bot. The session will be saved in ./sessions/ directory.")

    client.disconnect()

if __name__ == "__main__":
    main()

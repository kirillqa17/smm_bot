#!/usr/bin/env python3
"""
Pyrogram Session Setup Script
Run this ONCE to authorize Pyrogram and create session file
"""
import os
from pyrogram import Client
from core.config import API_ID, API_HASH, SESSION_NAME

# Create sessions directory if it doesn't exist
os.makedirs("sessions", exist_ok=True)

def main():
    print("=" * 50)
    print("Pyrogram Session Setup")
    print("=" * 50)
    print("\nThis script will create a Pyrogram session file.")
    print("You'll need to enter your phone number and verification code.\n")

    # Create client
    app = Client(SESSION_NAME, API_ID, API_HASH)

    print(f"Connecting to Telegram...")

    # Start the client - this will prompt for phone and code
    with app:
        me = app.get_me()
        print(f"\n✅ Successfully authorized as: {me.first_name}")
        if me.username:
            print(f"   Username: @{me.username}")
        print(f"   Phone: +{me.phone_number}")

    print(f"\n✅ Session file created: {SESSION_NAME}.session")
    print("\nYou can now use the bot. The session will be saved in ./sessions/ directory.")

if __name__ == "__main__":
    main()

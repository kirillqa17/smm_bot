#!/bin/bash

# SMM Bot Startup Script
# This script starts all required services

echo "🤖 Starting SMM Bot..."
echo "====================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and fill in your API keys"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running!"
    echo "Please start Redis: sudo systemctl start redis"
    echo "Or install it: sudo apt-get install redis-server"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL is not running or not accessible"
    echo "Please start PostgreSQL: sudo systemctl start postgresql"
fi

echo "✅ All dependencies OK"
echo ""

# Override Docker hostnames for local development
export REDIS_HOST=localhost
export DB_HOST=localhost

echo "📝 Using local configuration:"
echo "   Redis: $REDIS_HOST"
echo "   PostgreSQL: $DB_HOST"
echo ""

# Kill any existing Celery workers
echo "🧹 Cleaning up old processes..."
pkill -f "celery.*tasks.celery_app" 2>/dev/null && echo "   Stopped old Celery workers" || echo "   No old workers found"
sleep 1

# Start Celery worker in background
echo "🔧 Starting Celery worker..."
celery -A tasks.celery_app worker --loglevel=info --logfile=celery.log &
CELERY_PID=$!
echo "✅ Celery started (PID: $CELERY_PID)"

# Wait a bit for Celery to start
sleep 2

# Start bot
echo "🤖 Starting Telegram bot..."
python bot.py

# Cleanup on exit
echo ""
echo "Stopping services..."
kill $CELERY_PID
echo "👋 Goodbye!"

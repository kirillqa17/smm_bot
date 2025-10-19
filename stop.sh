#!/bin/bash

# SMM Bot Stop Script
# Stops all bot processes

echo "🛑 Stopping SMM Bot..."
echo "====================="

# Kill Celery workers
if pkill -f "celery.*tasks.celery_app" 2>/dev/null; then
    echo "✅ Stopped Celery workers"
else
    echo "⚠️  No Celery workers found"
fi

# Kill bot process
if pkill -f "python.*bot.py" 2>/dev/null; then
    echo "✅ Stopped bot process"
else
    echo "⚠️  No bot process found"
fi

echo ""
echo "👋 All services stopped"

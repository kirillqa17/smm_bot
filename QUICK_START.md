# Quick Start

## Local Development

```bash
# Start the bot
./start.sh

# Stop the bot
./stop.sh
```

## Docker

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f bot
```

## What Was Fixed

### Issue: "Connection closed by server" (Redis)

**Root Cause**:
- `.env` file has Docker hostnames (`redis`, `postgres`)
- Celery tried connecting to `redis:6379` instead of `localhost:6379`

**Solution**:
- `start.sh` now exports `REDIS_HOST=localhost` and `DB_HOST=localhost`
- Added Redis connection pooling with auto-retry
- Added cleanup of old processes

### Changes Made:
1. ✅ **core/state_manager.py** - Added connection pool + retry logic
2. ✅ **start.sh** - Override Docker hostnames for local dev
3. ✅ **stop.sh** - Clean process termination script

## Verify Everything Works

```bash
# 1. Check Redis
redis-cli ping
# Should return: PONG

# 2. Check PostgreSQL
pg_isready
# Should return: accepting connections

# 3. Start bot
./start.sh

# 4. Send /start to your bot in Telegram
```

## Logs

```bash
# Real-time Celery logs
tail -f celery.log

# Bot logs
# (shown in console where you ran ./start.sh)
```

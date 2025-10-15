# 🤖 SMM Bot - AI-Powered SMM Multi-Tool

Production-ready Telegram bot for SMM specialists with AI-powered content generation, image creation/editing, and news integration.

## ✨ Features

- 📊 **Channel Analysis** - Deep analysis of Telegram channel style, tone, and metrics
- ✍️ **Post Generation** - Create posts matching any channel's style
- 📰 **News Integration** - Auto-generate posts from latest news (Tech, Crypto, Marketing, Business)
- 🎨 **Image Generation** - Create unique images with DALL-E 3
- ✏️ **AI Image Editing** - Edit images using natural language (Nano Banana AI)
- 💧 **Watermark Tools** - Add or remove watermarks
- 📈 **Statistics** - Track usage and history

## 🏗 Architecture

- **Bot**: pyTelegramBotAPI (telebot)
- **Task Queue**: Celery + Redis (async processing)
- **Database**: PostgreSQL
- **AI Services**: Google Gemini, OpenAI DALL-E 3, Replicate Nano Banana
- **News**: RSS feeds + News API
- **Deployment**: Docker Compose ready

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone and navigate
cd smm_bot

# 2. Copy and configure environment
cp .env.example .env
nano .env  # Fill in your API keys

# 3. Authorize Telethon (one-time setup)
# Run this BEFORE starting Docker
python3 setup_telethon.py
# Enter your phone number and verification code when prompted

# 4. Start everything with Docker
docker-compose up -d

# 5. Check logs
docker-compose logs -f bot
```

**⚠️ Important**: You MUST run `setup_telethon.py` before starting Docker for the first time to authorize Telethon session.

### Option 2: Manual Installation

```bash
# 1. Install dependencies
sudo apt-get update
sudo apt-get install python3.11 python3-pip python3-venv
sudo apt-get install postgresql redis-server

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Setup database
sudo -u postgres psql < init_db.sql

# 5. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 6. Authorize Telethon (one-time)
python -c "from telethon.sync import TelegramClient; from core.config import API_ID, API_HASH, SESSION_NAME; TelegramClient(SESSION_NAME, API_ID, API_HASH).start()"

# 7. Start bot
./start.sh
```

## 🔑 Required API Keys

### Mandatory (Bot won't work without these)

1. **Telegram Bot Token**
   - Get from: [@BotFather](https://t.me/BotFather)
   - Command: `/newbot`
   - Example: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

2. **Telegram API ID & Hash**
   - Get from: https://my.telegram.org
   - Go to "API Development Tools"
   - Create application

3. **Google Gemini API Key**
   - Get from: https://makersuite.google.com/app/apikey
   - Free tier available
   - Used for: Text generation and analysis

4. **Database Password**
   - Set any secure password for PostgreSQL

### Optional (For advanced features)

5. **OpenAI API Key** (for DALL-E 3 image generation)
   - Get from: https://platform.openai.com/api-keys
   - Paid service: ~$0.04 per image

6. **Replicate API Key** (for Nano Banana image editing)
   - Get from: https://replicate.com/account/api-tokens
   - Pay-as-you-go: ~$0.01 per edit

7. **News API Key** (for news aggregation)
   - Get from: https://newsapi.org/
   - Free tier: 100 requests/day

## ⚙️ Configuration

Edit `.env` file:

```env
# Telegram (REQUIRED)
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=smm_bot

# Database (REQUIRED)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=smm_bot

# Redis (REQUIRED)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# AI Services (REQUIRED: Gemini, OPTIONAL: others)
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key  # Optional
REPLICATE_API_KEY=your_replicate_key  # Optional

# News (OPTIONAL)
NEWS_API_KEY=your_news_api_key

# App Settings
MAX_POSTS_TO_ANALYZE=50
TASK_TIMEOUT=300
```

## 📖 Usage

### 1. Analyze Channel

```
User: Click "📊 Analyze Channel"
Bot: Send channel username in format: @channel_name
User: @durov
Bot: ⏳ Analyzing... (30-60 seconds)
Bot: ✅ Analysis complete!
```

### 2. Generate Post

```
User: Click "✍️ Generate Post"
Bot: What topic?
User: "AI trends in 2025"
Bot: ⏳ Generating 3 variants...
Bot: [Shows 3 post options]
User: Select favorite
```

### 3. News to Post

```
User: Click "📰 News to Post"
Bot: [Shows categories: Tech, Crypto, Marketing, Business]
User: Select "Tech"
Bot: [Shows 5 latest tech news]
User: Select news #2
Bot: ⏳ Generating posts...
Bot: [Shows 3 variants based on news]
```

### 4. Create Image

```
User: Click "🎨 Create Image"
Bot: Describe the image
User: "Modern tech workspace with AI theme"
Bot: Choose model: DALL-E 3 or Stable Diffusion
User: Select DALL-E 3
Bot: ⏳ Generating... (1-2 minutes)
Bot: [Sends generated image]
```

### 5. Edit Image

```
User: Click "✏️ Edit Image"
Bot: Send image
User: [Sends image]
Bot: What to change?
User: "Add red text 'SALE' at top"
Bot: ⏳ Editing with AI...
Bot: [Sends edited image]
```

### 6. Watermark

```
User: Click "💧 Watermark"
Bot: Add or Remove?
User: Add
Bot: Send image
User: [Sends image]
Bot: Enter watermark text
User: "© MyBrand 2025"
Bot: [Sends watermarked image]
```

## 🏃 Running in Production

### Systemd Service (Linux)

Create `/etc/systemd/system/smm-bot.service`:

```ini
[Unit]
Description=SMM Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/smm_bot
ExecStart=/path/to/smm_bot/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable smm-bot
sudo systemctl start smm-bot
sudo systemctl status smm-bot
```

### Docker Compose (Recommended)

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Stop
docker-compose down

# Update and restart
git pull
docker-compose build
docker-compose up -d
```

## 📊 Monitoring

### Logs

```bash
# Bot logs
docker-compose logs -f bot

# Celery logs
docker-compose logs -f celery

# All logs
docker-compose logs -f
```

### Health Checks

```bash
# Check Redis
redis-cli ping

# Check PostgreSQL
psql -U postgres -d smm_bot -c "SELECT COUNT(*) FROM users;"

# Check Celery
celery -A tasks.celery_app inspect active
```

## 🔧 Maintenance

### Database Backup

```bash
# Backup
pg_dump -U postgres smm_bot > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres smm_bot < backup_20250115.sql
```

### Clear Redis Cache

```bash
redis-cli FLUSHDB
```

### Update Bot

```bash
git pull
docker-compose build
docker-compose up -d
```

## 💰 Cost Estimation

### For 100 users/day:

**Free tier:**
- Channel analysis: $0 (Gemini)
- Post generation: $0 (Gemini)
- News aggregation: $0 (RSS + 100/day News API)
- **Total: $0/month**

**With images (DALL-E 3):**
- 100 images: $4
- Image editing (Nano Banana): ~$1
- **Total: ~$5/month**

## 🐛 Troubleshooting

### Bot doesn't start

```bash
# Check configuration
python -c "from core.config import validate_config; validate_config()"

# Check dependencies
pip install -r requirements.txt

# Check services
redis-cli ping
pg_isready
```

### Telethon not authorized

```bash
# Re-authorize
rm smm_bot.session
python -c "from telethon.sync import TelegramClient; from core.config import API_ID, API_HASH, SESSION_NAME; TelegramClient(SESSION_NAME, API_ID, API_HASH).start()"
```

### Celery tasks not executing

```bash
# Check Celery worker
celery -A tasks.celery_app inspect active

# Restart worker
pkill -f "celery worker"
celery -A tasks.celery_app worker --loglevel=info
```

### Database connection errors

```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Check connection
psql -U postgres -d smm_bot -c "SELECT 1;"

# Reset database
sudo -u postgres psql < init_db.sql
```

## 📁 Project Structure

```
smm_bot/
├── bot.py                 # Main bot file (850 lines)
├── start.sh               # Startup script
├── docker-compose.yml     # Docker setup
├── Dockerfile             # Docker image
├── init_db.sql            # Database initialization
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
│
├── core/                 # Core modules
│   ├── config.py        # Configuration
│   └── state_manager.py # Redis state management
│
├── db/                  # Database
│   └── database.py     # Database operations
│
└── tasks/              # Celery tasks
    ├── celery_app.py  # Celery configuration
    └── tasks.py       # All async tasks (500+ lines)
```

## 🤝 Contributing

This is a production-ready bot. Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📄 License

MIT License

## 🆘 Support

For issues, check:
1. This README
2. Logs: `docker-compose logs -f`
3. Configuration: `python -c "from core.config import validate_config; validate_config()"`

---

**Made with ❤️ for SMM specialists**

**Ready to use! Just add your API keys and run!** 🚀

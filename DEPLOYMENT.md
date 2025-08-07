# Feedmaster Deployment Guide

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/femavibes/feedmaster.git
   cd feedmaster
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Configure feeds:**
   ```bash
   # Edit config/feeds.json to add your Contrails feed URLs
   ```

4. **Start the application:**
   ```bash
   docker compose up --build
   ```

5. **Run database migrations:**
   ```bash
   docker compose exec api alembic upgrade head
   ```

## Required Configuration Files

### `.env` (copy from `.env.example`)
- Database credentials
- JWT secret key (generate a strong random string)
- Cloudflare tunnel token (if using)

### `config/feeds.json`
- Already configured with example feeds
- Add your own Contrails WebSocket URLs

## Data Storage

- **Database data**: Stored in Docker volume `pgdata` (not in git)
- **Generated images**: Cached in `/tmp/achievement_cards/` (not in git)
- **Logs**: Generated at runtime (not in git)

## Production Deployment

1. Use a strong `SECRET_KEY` in production
2. Set up proper database backups
3. Configure Cloudflare tunnel for public access
4. Monitor logs and performance

## Troubleshooting

- Check `docker compose logs` for errors
- Ensure all environment variables are set
- Verify feed URLs are accessible
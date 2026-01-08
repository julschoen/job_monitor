# Job Monitor 🔔

A flexible Python script that monitors company job pages and sends Telegram notifications when new positions are posted.

## Features

- **Flexible Scraping**: Works with many different website structures (Lever, Greenhouse, Workday, custom career pages)
- **Keyword Filtering**: Include/exclude jobs based on keywords in titles
- **Telegram Notifications**: Instant alerts when new jobs appear
- **Persistence**: Remembers seen jobs across restarts
- **Rate Limiting**: Respectful to target websites

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Start a chat with your new bot (search for it and click "Start")
5. Get your **chat ID**:
   - Send any message to your bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find the `"chat":{"id":` value in the response (your chat ID)

### 3. Configure

Copy the example config and edit it:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "telegram_bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "telegram_chat_id": "987654321",
  "check_interval_minutes": 60,
  "sources": [
    {
      "name": "Company Name",
      "url": "https://company.com/careers",
      "keywords": ["python", "backend", "engineer"],
      "exclude_keywords": ["senior", "manager", "director"]
    }
  ]
}
```

**Configuration Options:**

| Field | Description |
|-------|-------------|
| `telegram_bot_token` | Your Telegram bot token from BotFather |
| `telegram_chat_id` | Your chat ID (or group ID for group notifications) |
| `check_interval_minutes` | How often to check for new jobs |
| `sources[].name` | Friendly name for the company |
| `sources[].url` | URL of the careers/jobs page |
| `sources[].keywords` | Only notify if title contains ANY of these (empty = all jobs) |
| `sources[].exclude_keywords` | Skip jobs with these keywords in title |

### 4. Run

```bash
# Run once (good for testing)
python job_monitor.py --once

# Run continuously
python job_monitor.py
```

## Environment Variables

You can also configure via environment variables (useful for cloud deployment):

```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export CHECK_INTERVAL="60"
```

---

## Free Hosting Options

### Option 1: GitHub Actions (Recommended) ⭐

**Best for**: Scheduled checks every 15-60 minutes. Free and reliable.

1. Create a GitHub repository and push the code
2. Go to Settings → Secrets → Actions
3. Add secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `JOB_SOURCES` (your sources array as JSON)
4. Create `.github/workflows/job_monitor.yml`:

```yaml
name: Job Monitor

on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:  # Manual trigger

jobs:
  check-jobs:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Restore seen jobs cache
        uses: actions/cache@v4
        with:
          path: data/
          key: seen-jobs-${{ github.run_id }}
          restore-keys: seen-jobs-
      
      - name: Create config
        run: |
          cat > config.json << 'EOF'
          {
            "telegram_bot_token": "${{ secrets.TELEGRAM_BOT_TOKEN }}",
            "telegram_chat_id": "${{ secrets.TELEGRAM_CHAT_ID }}",
            "sources": ${{ secrets.JOB_SOURCES }}
          }
          EOF
      
      - name: Run job monitor
        run: python job_monitor.py --once
```

### Option 2: Railway.app

**Best for**: Continuous running. Free tier available.

1. Create account at [railway.app](https://railway.app)
2. Connect your GitHub repo
3. Add environment variables in Railway dashboard
4. Deploy!

Create a `Procfile`:
```
worker: python job_monitor.py
```

### Option 3: Render.com (Background Worker)

**Best for**: Continuous running with free tier.

1. Create account at [render.com](https://render.com)
2. New → Background Worker
3. Connect your repo
4. Set environment variables
5. Start Command: `python job_monitor.py`

### Option 4: PythonAnywhere (Free Tier)

**Best for**: Scheduled tasks. Free tier includes scheduled tasks.

1. Create account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload your files
3. Go to Tasks → Scheduled Tasks
4. Add a task to run hourly: `python3 /home/yourusername/job_monitor/job_monitor.py --once`

### Option 5: Fly.io

**Best for**: Always-on with generous free tier.

1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Create `fly.toml`:

```toml
app = "job-monitor"
primary_region = "iad"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  CHECK_INTERVAL = "60"

[[services]]
  internal_port = 8080
  protocol = "tcp"
```

3. Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "job_monitor.py"]
```

4. Deploy:
```bash
fly launch
fly secrets set TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx
fly deploy
```

### Option 6: Google Cloud Run (with Cloud Scheduler)

**Best for**: Pay-per-use, essentially free for low usage.

1. Containerize with Docker
2. Deploy to Cloud Run
3. Set up Cloud Scheduler to call it periodically

---

## Tips for Adding Job Sources

### Finding the Right URL

- Go to the company's careers page
- Look for job listings (not individual job pages)
- Copy the URL that shows the list of open positions

### Common Career Page Platforms

The script handles these automatically:

| Platform | Example URL Pattern |
|----------|---------------------|
| Lever | `jobs.lever.co/company` |
| Greenhouse | `boards.greenhouse.io/company` |
| Workday | `company.wd5.myworkdayjobs.com` |
| Ashby | `jobs.ashbyhq.com/company` |
| Custom | `company.com/careers`, `company.com/jobs` |

### Troubleshooting

**No jobs found?**
- Check if the page loads jobs via JavaScript (the script can't handle heavy JS)
- Try the direct job listing URL
- Some sites block scrapers - try adding a delay

**Too many notifications?**
- Add more specific keywords
- Use exclude_keywords for unwanted positions

**Missing jobs?**
- The scraper uses heuristics; some edge cases may be missed
- Check the logs for errors

## Project Structure

```
job_monitor/
├── job_monitor.py      # Main script
├── requirements.txt    # Python dependencies
├── config.json         # Your configuration (create from example)
├── config.example.json # Example configuration
├── data/
│   └── seen_jobs.json  # Tracks seen jobs (auto-created)
└── .github/
    └── workflows/
        └── job_monitor.yml  # GitHub Actions workflow
```

## License

MIT - Use freely!

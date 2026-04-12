# Environment Setup Guide

This guide covers secrets management with Doppler, environment setup with Flox, and all required API keys.

## Quick Start

```bash
# 1. Install Doppler CLI (if not already)
curl -Ls https://cli.doppler.com/install.sh | sh

# 2. Login and setup
doppler login
doppler setup  # Select: contentflow / dev

# 3. Run with secrets injected
doppler run -- python main.py
```

---

## Secrets Management with Doppler

### Why Doppler?

| Feature | .env files | Doppler |
|---------|------------|---------|
| Team sharing | Manual | Automatic |
| Multi-environment | No | dev/staging/prod |
| Audit logs | No | Yes |
| Encryption | No | Yes |
| Versioning | No | Yes |
| Dashboard | No | Yes |

### Setup Options

**Option 1: Doppler (Recommended)**
```bash
./setup.sh
# Choose option 1: Create new project
# Or option 2: Use existing project
```

**Option 2: Fallback with .env**
```bash
# Local development only - never commit!
cp .env.example .env
# Edit .env with your keys
```

### Daily Usage

```bash
# Development - with Doppler (recommended)
doppler run -- python main.py
doppler run -- uvicorn api.main:app --reload

# Development - with .env fallback
./run_seo_tools.sh python main.py

# Production - always use Doppler
doppler run -- uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Required API Keys

### Essential Keys (Core Functionality)

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `OPENROUTER_API_KEY` | LLM access (recommended) | https://openrouter.ai/keys |
| `GROQ_API_KEY` | Free LLM fallback | https://console.groq.com |

### SEO & Research Keys

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `YDC_API_KEY` | STORM research (You.com) | https://you.com/api |
| `EXA_API_KEY` | Newsletter research | https://exa.ai |
| `SERP_API_KEY` | SERP analysis | https://serpapi.com |
| `FIRECRAWL_API_KEY` | Web crawling | https://firecrawl.dev |

### Newsletter Robot Keys

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `NEWSLETTER_EMAIL_BACKEND` | Backend: `imap` (free) or `composio` | Config choice |
| `NEWSLETTER_IMAP_EMAIL` | Gmail address for IMAP | Your Gmail account |
| `NEWSLETTER_IMAP_PASSWORD` | Gmail App Password | Gmail Security settings |
| `NEWSLETTER_IMAP_HOST` | IMAP server (default: imap.gmail.com) | Optional |
| `NEWSLETTER_IMAP_FOLDER` | Folder to read (default: Newsletters) | Optional |
| `NEWSLETTER_IMAP_ARCHIVE` | Archive folder (default: CONTENTFLOW_DONE) | Optional |
| `COMPOSIO_API_KEY` | Composio API (if using composio backend) | https://composio.dev |

### Optional Keys

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `OPENAI_API_KEY` | Direct OpenAI access | https://platform.openai.com |
| `ANTHROPIC_API_KEY` | Direct Claude access | https://console.anthropic.com |
| `SENDGRID_API_KEY` | Email delivery | https://sendgrid.com |

### Adding Keys to Doppler

```bash
# Add individual key
doppler secrets set OPENROUTER_API_KEY="sk-or-v1-..."

# Add multiple keys
doppler secrets set \
  GROQ_API_KEY="gsk_..." \
  YDC_API_KEY="..." \
  EXA_API_KEY="..."

# Newsletter Robot IMAP config
doppler secrets set \
  NEWSLETTER_EMAIL_BACKEND="imap" \
  NEWSLETTER_IMAP_EMAIL="your-newsletters@gmail.com" \
  NEWSLETTER_IMAP_PASSWORD="xxxx-xxxx-xxxx-xxxx"

# Upload from existing .env
doppler secrets upload .env

# Verify keys
doppler secrets
```

---

## Flox Environment

Flox provides system dependencies (Python, gcc, system libs) in a reproducible way.

### Usage

```bash
# Activate environment
flox activate

# Run with Doppler + Flox
doppler run -- ./run_seo_tools.sh python script.py
```

### Library Path Issues

If you get numpy/pandas library errors:

```bash
# Use the wrapper script
./run_seo_tools.sh python test_advertools.py
```

---

## Environment-Specific Configs

### Development
```bash
doppler setup --project contentflow --config dev
# Use FREE APIs (Groq, You.com free tier)
# Lower rate limits acceptable
```

### Staging
```bash
doppler setup --project contentflow --config staging
# Paid APIs with higher limits
# Test production volume
```

### Production
```bash
doppler setup --project contentflow --config prod
# Premium APIs (OpenAI, paid You.com)
# Maximum rate limits
# Monitoring enabled
```

---

## Useful Commands

```bash
# View all secrets (masked)
doppler secrets

# View specific secret (shows value)
doppler secrets get GROQ_API_KEY

# Set/update secret
doppler secrets set KEY=value

# Delete secret
doppler secrets delete KEY

# Download as JSON
doppler secrets download --no-file --format json

# Check current config
doppler configure get project.name
doppler configure get config.name

# Switch configs
doppler setup --config staging
```

---

## PM2 Deployment with Doppler

### Using Service Token

```bash
# Generate token
doppler configs tokens create pm2-token --config dev

# Use in PM2
pm2 start --name "contentflow" \
  --interpreter bash -- -c \
  "export DOPPLER_TOKEN='dp.st.xxx' && cd /root/contentflow && doppler run -- python main.py"
```

---

## Security Best Practices

### DO:
- Store ALL API keys in Doppler
- Use `doppler run --` to inject secrets
- Use `os.getenv('KEY')` in code
- Rotate keys regularly
- Use different keys per environment

### DON'T:
- Hardcode API keys in code
- Commit `.env` files to git
- Share keys via chat/email
- Use same keys across environments
- Store keys in plaintext files

---

## Troubleshooting

### "API key not found"
```bash
# Must run with doppler
doppler run -- python script.py

# Check if key exists
doppler secrets get KEY_NAME
```

### "Wrong project/config"
```bash
# Verify configuration
doppler configure get project.name  # Should be: contentflow
doppler configure get config.name   # Should be: dev

# Reconfigure if wrong
doppler setup --project contentflow --config dev
```

### Doppler not installed
```bash
curl -Ls https://cli.doppler.com/install.sh | sh
doppler login
```

---

## Cost-Free Setup

For testing with zero cost:

```
Groq API:     $0/month (14,400 req/day limit)
You.com API:  $0/month (100 searches/day)
Total:        $0/month
```

Good for learning, testing, and 2-3 articles/week.

---

## Next Steps

- See `docs/LLM_PROVIDER_SETUP.md` for LLM configuration details
- See `AGENTS.md` for agent-specific settings
- See `docs/RENDER_MCP_GUIDE.md` for deployment

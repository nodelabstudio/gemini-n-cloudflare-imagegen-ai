# AI Image Generator

A web UI and CLI for generating images with **Cloudflare Workers AI** and **Google Gemini**. Built with FastAPI, styled with Tailwind CSS, and deployable to Railway in one click.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- Web UI with model selection, prompt input, image preview, and download
- 11 Cloudflare models (6 free, 5 paid) + 2 Gemini models
- CLI scripts for quick one-off generation
- Black image / content filter detection
- PostgreSQL-backed image gallery with lightbox viewer and delete
- SQLite fallback for local development (zero config)
- User authentication (bcrypt-hashed passwords, session cookies)
- CSRF protection on all mutations
- Rate limiting (5 image generations per minute per user)
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- One-click Railway deployment

## Quick Start

```bash
git clone https://github.com/nodelabstudio/gemini-n-cloudflare-imagegen-ai.git
cd gemini-n-cloudflare-imagegen-ai
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
# Cloudflare (free)
CF_ACCOUNT_ID=your-account-id
CF_API_TOKEN=your-api-token

# Gemini (optional)
GEMINI_API_KEY=your-gemini-key
```

Run the web UI:

```bash
uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.com](https://railway.com) and create a new project from your repo
3. Click **+ New** > **Database** > **PostgreSQL** to add a database
4. Railway auto-injects `DATABASE_URL` into your app
5. Add your environment variables in the Railway dashboard under **Variables**:
   - `CF_ACCOUNT_ID`, `CF_API_TOKEN` (Cloudflare)
   - `GEMINI_API_KEY` (Google, optional)
   - `SESSION_SECRET` (generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`)

6. Railway auto-detects the `Procfile` and deploys

The database table is created automatically on first startup. Locally it uses SQLite (`images.db`) so you don't need PostgreSQL for development.

## Available Models

### Cloudflare Workers AI

| Key | Model | Tier |
|-----|-------|------|
| `flux-schnell` | FLUX.1 Schnell (default) | Free |
| `sdxl` | Stable Diffusion XL | Free |
| `dreamshaper` | DreamShaper 8 LCM | Free |
| `sd-lightning` | SDXL Lightning | Free |
| `sd-img2img` | SD v1.5 Img2Img | Free |
| `sd-inpaint` | SD v1.5 Inpainting | Free |
| `flux-2-dev` | FLUX.2 Dev (best quality) | Paid |
| `flux-2-klein-4b` | FLUX.2 Klein 4B | Paid |
| `flux-2-klein-9b` | FLUX.2 Klein 9B | Paid |
| `phoenix` | Leonardo Phoenix | Paid |
| `lucid` | Leonardo Lucid Origin | Paid |

### Google Gemini

| Key | Model |
|-----|-------|
| `gemini-2.5-flash` | Gemini 2.5 Flash |
| `gemini-3.1-flash` | Gemini 3.1 Flash (Preview) |

## CLI Usage

You can also generate images from the command line:

```bash
# Cloudflare
python3 cloudflare_image_gen.py "A lighthouse at sunset, digital art"
python3 cloudflare_image_gen.py --model=dreamshaper "your prompt"
python3 cloudflare_image_gen.py --models

# Gemini
python3 gemini_image_gen.py "your prompt"
python3 gemini_image_gen.py --diagnose
```

## API Keys Setup

### Cloudflare (free, ~2 min)

1. Sign up at [dash.cloudflare.com](https://dash.cloudflare.com) (no credit card)
2. Copy your **Account ID** from the dashboard sidebar
3. Create an API token at [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) using the "Workers AI" template

### Gemini

1. Get an API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. For image generation, you may need to [link a billing account](https://console.cloud.google.com/billing) (no minimum spend)

## Security

- **Authentication:** Username/password with bcrypt-hashed passwords stored in PostgreSQL
- **Sessions:** Signed cookies (7-day expiry, SameSite=Lax, Secure flag in production)
- **CSRF:** Token-based protection on all POST/DELETE endpoints
- **Rate Limiting:** 5 image generations per minute per user (slowapi/limits)
- **Headers:** CSP, X-Frame-Options DENY, X-Content-Type-Options, HSTS (in production), Referrer-Policy, Permissions-Policy

### Cloudflare Reverse Proxy (recommended for production)

1. Add a custom domain to your Railway app (Settings > Networking > Custom Domain)
2. In Cloudflare DNS, add a CNAME record pointing to your Railway domain
3. Enable the orange cloud (Proxy) for DDoS protection, WAF, and SSL termination
4. Under Security > WAF, enable managed rulesets for additional protection

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **Frontend:** Tailwind CSS (CDN)
- **Auth:** passlib + bcrypt, Starlette sessions
- **Database:** PostgreSQL (Railway) / SQLite (local dev)
- **Providers:** Cloudflare Workers AI, Google Gemini
- **Deployment:** Railway

## TODO

- [ ] Neobrutalist UI redesign

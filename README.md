# Image Generation Prototype

Two scripts, two providers. Pick the one that works for your situation.
This app generates images for free, although it can't be used for branding since it's not consistent, but it works.

## Option A: Cloudflare Workers AI (free, works now)

Uses Stable Diffusion XL. 100,000 free calls/day. No credit card.

### Setup (~2 min)

1. Sign up at https://dash.cloudflare.com (free account)
2. Copy your Account ID from the dashboard right sidebar
3. Create an API token at https://dash.cloudflare.com/profile/api-tokens
   - Use the "Workers AI" template, or create a custom token with
     Account > Workers AI > Read permission
4. Set env vars:

```bash
export CF_ACCOUNT_ID="your-account-id"
export CF_API_TOKEN="your-api-token"
```

### Usage

```bash
pip install requests

python3 cloudflare_image_gen.py "A lighthouse at sunset, digital art"

python3 cloudflare_image_gen.py --model=dreamshaper "your prompt"

python3 cloudflare_image_gen.py --models
```

### Available models

- sdxl (default) -- Stable Diffusion XL Base 1.0
- dreamshaper -- DreamShaper 8 LCM (faster, stylized)
- sd -- SDXL Lightning by ByteDance (fastest)

---

## Option B: Gemini (requires billing linked)

Higher quality than SDXL but the free API tier for image generation
is currently showing limit: 0 for most new projects.

### To unlock it

1. Go to https://console.cloud.google.com/billing
2. Link a billing account to your GCP project
3. Generate a NEW API key at https://aistudio.google.com/apikey
4. No minimum spend -- you only pay past the free quota

### Usage

```bash
pip install google-genai Pillow

export GEMINI_API_KEY="your-new-key"

python gemini_image_gen.py --diagnose

python gemini_image_gen.py "your prompt"
```

### Gemini pricing (if you go past free)

- gemini-2.5-flash-image: $0.039/image
- gemini-3.1-flash-image-preview: $0.045/image
- imagen-4.0-fast-generate-001: $0.02/image (cheapest)

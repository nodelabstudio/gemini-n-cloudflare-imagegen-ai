import os
import sys
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

MODELS = {
    # --- Free models ---
    "flux-schnell": "@cf/black-forest-labs/flux-1-schnell",
    "sdxl": "@cf/stabilityai/stable-diffusion-xl-base-1.0",
    "dreamshaper": "@cf/lykon/dreamshaper-8-lcm",
    "sd-lightning": "@cf/bytedance/stable-diffusion-xl-lightning",
    "sd-img2img": "@cf/runwayml/stable-diffusion-v1-5-img2img",
    "sd-inpaint": "@cf/runwayml/stable-diffusion-v1-5-inpainting",
    # --- Paid models ---
    "flux-2-dev": "@cf/black-forest-labs/flux-2-dev",
    "flux-2-klein-4b": "@cf/black-forest-labs/flux-2-klein-4b",
    "flux-2-klein-9b": "@cf/black-forest-labs/flux-2-klein-9b",
    "phoenix": "@cf/leonardo/phoenix-1.0",
    "lucid": "@cf/leonardo/lucid-origin",
}
DEFAULT_MODEL = "flux-schnell"


def generate_image(
    prompt: str,
    output_dir: str = "./output",
    model_key: str = DEFAULT_MODEL,
) -> list[str]:
    account_id = os.environ.get("CF_ACCOUNT_ID")
    api_token = os.environ.get("CF_API_TOKEN")

    if not account_id or not api_token:
        print("Error: Set CF_ACCOUNT_ID and CF_API_TOKEN environment variables.")
        print()
        print("Setup (free, ~2 minutes):")
        print("  1. Sign up at dash.cloudflare.com (no credit card)")
        print("  2. Copy Account ID from the dashboard sidebar")
        print("  3. Create an API token at dash.cloudflare.com/profile/api-tokens")
        print('     -> Use "Workers AI" template, or custom with Workers AI Read')
        print()
        print("  export CF_ACCOUNT_ID='your-account-id'")
        print("  export CF_API_TOKEN='your-api-token'")
        sys.exit(1)

    model = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    print(f"Model: {model_key} ({model})")
    print(f"Generating...")

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_token}"},
        json={"prompt": prompt},
    )

    if response.status_code != 200:
        try:
            error = response.json()
            errors = error.get("errors", [])
            msg = errors[0].get("message", str(error)) if errors else str(error)
        except Exception:
            msg = response.text[:200]
        print(f"Error ({response.status_code}): {msg}")
        return []

    # Some models return raw image bytes, others return JSON with base64 data
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        if not data.get("success", True):
            errors = data.get("errors", [])
            msg = errors[0].get("message", str(data)) if errors else str(data)
            print(f"API error: {msg}")
            return []
        # Extract base64 image from JSON response
        result = data.get("result", {})
        if isinstance(result, dict) and "image" in result:
            import base64
            image_data = base64.b64decode(result["image"])
        else:
            print(f"Unexpected JSON response: {str(data)[:200]}")
            return []
    else:
        image_data = response.content

    # Check for black/empty image (content filter triggered)
    if len(image_data) < 1000 or all(b == 0 for b in image_data[:512]):
        print("Warning: Got an empty or near-empty image.")
        print("This usually means Cloudflare's content filter blocked the prompt.")
        print("Try simplifying your prompt — remove detailed descriptions of people,")
        print("specific physical features, or mood/emotion keywords.")
        return []

    # Quick black-image check via pixel sampling
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        pixels = list(img.getdata())
        nonblack = sum(1 for r, g, b in pixels if r > 5 or g > 5 or b > 5)
        if nonblack / len(pixels) < 0.01:
            print("Warning: Generated image is entirely (or nearly) black.")
            print(
                "This typically means Cloudflare's content filter silently blocked the prompt."
            )
            print("\nTips to fix:")
            print("  - Remove detailed descriptions of people/faces/bodies")
            print("  - Use simpler, more abstract prompts")
            print("  - Try a different model: --model=dreamshaper or --model=sd")
            # Still save it so user can inspect
    except ImportError:
        pass  # Pillow not installed, skip pixel check

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/cf_{timestamp}.png"

    with open(filename, "wb") as f:
        f.write(image_data)

    print(f"Saved: {filename}")
    return [filename]


if __name__ == "__main__":
    model_key = DEFAULT_MODEL
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    for flag in flags:
        if flag.startswith("--model="):
            model_key = flag.split("=", 1)[1]

    if "--models" in flags:
        print("Available models:")
        for key, model_id in MODELS.items():
            default = " (default)" if key == DEFAULT_MODEL else ""
            print(f"  --model={key}  ->  {model_id}{default}")
        sys.exit(0)

    prompt = args[0] if args else "A cozy coffee shop on a rainy day, watercolor style"
    print(f"Prompt: {prompt}\n")
    files = generate_image(prompt, model_key=model_key)
    print(f"\nDone. Generated {len(files)} image(s).")

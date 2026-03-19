import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
]


def get_client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Set GEMINI_API_KEY environment variable first.")
        print("Get one free at: https://aistudio.google.com/apikey")
        sys.exit(1)

    return genai.Client(api_key=api_key)


def diagnose(client):
    from google.genai import errors

    print("=== Diagnostic: Testing model availability ===\n")
    for model_id in MODELS:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents="Generate a simple red circle on a white background",
                config={"response_modalities": ["TEXT", "IMAGE"]},
            )
            has_image = any(
                p.inline_data is not None for p in response.candidates[0].content.parts
            )
            status = "IMAGE OK" if has_image else "TEXT ONLY (no image returned)"
            print(f"  {model_id}: {status}")
        except errors.ClientError as e:
            print(f"  {model_id}: FAILED ({_short_error(e)})")
        except Exception as e:
            print(f"  {model_id}: ERROR ({type(e).__name__}: {e})")

    print("\n=== Diagnostic complete ===")
    print("\nIf all models show FAILED:")
    print("  1. Link billing at console.cloud.google.com/billing")
    print("  2. Create a NEW API key after linking billing")
    print("  3. Or use cloudflare_image_gen.py as a free fallback\n")


def _short_error(e):
    msg = str(e)
    if "RESOURCE_EXHAUSTED" in msg:
        return "quota exhausted / limit: 0"
    if "NOT_FOUND" in msg:
        return "model ID not found"
    if len(msg) > 120:
        return msg[:120] + "..."
    return msg


def generate_image(
    prompt: str,
    output_dir: str = "./output",
    model: str | None = None,
) -> list[str]:
    from google.genai import errors

    client = get_client()
    models_to_try = [model] if model else MODELS
    last_error = None

    for model_id in models_to_try:
        print(f"Trying model: {model_id}")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config={"response_modalities": ["TEXT", "IMAGE"]},
            )
            print(f"  -> Success with {model_id}")
            break
        except errors.ClientError as e:
            last_error = e
            print(f"  -> Failed: {_short_error(e)}")
            continue
    else:
        print(f"\nAll models failed. Last error: {_short_error(last_error)}")
        print("Run with --diagnose for details, or see README.md")
        return []

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i, part in enumerate(response.candidates[0].content.parts):
        if part.text is not None:
            print(f"Model said: {part.text}")
        elif part.inline_data is not None:
            ext = part.inline_data.mime_type.split("/")[-1]
            filename = f"{output_dir}/gen_{timestamp}_{i}.{ext}"
            with open(filename, "wb") as f:
                f.write(part.inline_data.data)
            saved_files.append(filename)
            print(f"Saved: {filename}")

    return saved_files


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        diagnose(get_client())
        sys.exit(0)

    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "A cozy coffee shop on a rainy day, watercolor style"
    )
    print(f"Prompt: {prompt}\n")
    files = generate_image(prompt)
    print(f"\nDone. Generated {len(files)} image(s).")

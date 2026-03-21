import os
import base64
import uuid
import secrets
import contextvars
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Depends, Query
from fastapi.responses import HTMLResponse, Response, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
import requests as http_requests

from database import init_db, get_db, engine
from migrations import apply_migrations
from models import GeneratedImage, ImageTag, User
from auth import hash_password, verify_password, get_csrf_token, validate_csrf_token

load_dotenv()

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-only-change-me-in-production")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")

_is_admin_request = contextvars.ContextVar("_is_admin_request", default=False)


def _check_admin_exempt() -> bool:
    return _is_admin_request.get(False)


def get_user_key(request: Request) -> str:
    return request.session.get("user_id", request.client.host)


app = FastAPI(title="Cloudfire Image Generator")
limiter = Limiter(key_func=get_user_key)
app.state.limiter = limiter
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

CLOUDFLARE_MODELS = {
    "flux-schnell": {"id": "@cf/black-forest-labs/flux-1-schnell", "name": "FLUX.1 Schnell", "tier": "free"},
    "sdxl": {"id": "@cf/stabilityai/stable-diffusion-xl-base-1.0", "name": "Stable Diffusion XL", "tier": "free"},
    "dreamshaper": {"id": "@cf/lykon/dreamshaper-8-lcm", "name": "DreamShaper 8 LCM", "tier": "free"},
    "sd-lightning": {"id": "@cf/bytedance/stable-diffusion-xl-lightning", "name": "SDXL Lightning", "tier": "free"},
    "sd-img2img": {"id": "@cf/runwayml/stable-diffusion-v1-5-img2img", "name": "SD v1.5 Img2Img", "tier": "free"},
    "sd-inpaint": {"id": "@cf/runwayml/stable-diffusion-v1-5-inpainting", "name": "SD v1.5 Inpainting", "tier": "free"},
    "flux-2-dev": {"id": "@cf/black-forest-labs/flux-2-dev", "name": "FLUX.2 Dev", "tier": "paid"},
    "flux-2-klein-4b": {"id": "@cf/black-forest-labs/flux-2-klein-4b", "name": "FLUX.2 Klein 4B", "tier": "paid"},
    "flux-2-klein-9b": {"id": "@cf/black-forest-labs/flux-2-klein-9b", "name": "FLUX.2 Klein 9B", "tier": "paid"},
    "phoenix": {"id": "@cf/leonardo/phoenix-1.0", "name": "Leonardo Phoenix", "tier": "paid"},
    "lucid": {"id": "@cf/leonardo/lucid-origin", "name": "Leonardo Lucid Origin", "tier": "paid"},
}

GEMINI_MODELS = {
    "gemini-2.5-flash": {"id": "gemini-2.5-flash-image", "name": "Gemini 2.5 Flash"},
    "gemini-3.1-flash": {"id": "gemini-3.1-flash-image-preview", "name": "Gemini 3.1 Flash (Preview)"},
}

ALL_MODELS = {**CLOUDFLARE_MODELS, **GEMINI_MODELS}

PUBLIC_PATHS = {"/login", "/register"}


# --------------- Middleware ---------------

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path

    # Auth gate (skip static files, public pages, and share links)
    if path not in PUBLIC_PATHS and not path.startswith("/static") and not path.startswith("/s/"):
        if not request.session.get("user_id"):
            return RedirectResponse("/login", status_code=302)

    _is_admin_request.set(request.session.get("is_admin", False))

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=86400 * 7,
    same_site="lax",
    https_only=os.environ.get("RAILWAY_ENVIRONMENT") is not None,
)


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        {"error": "Rate limit exceeded. Maximum 5 images per minute. Please wait and try again."},
        status_code=429,
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@app.on_event("startup")
def startup():
    init_db()
    apply_migrations(engine)


# --------------- Auth routes ---------------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "error": None,
    })


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = {"request": request, "csrf_token": get_csrf_token(request)}

    if not validate_csrf_token(request, csrf_token):
        ctx["error"] = "Invalid request. Please try again."
        return templates.TemplateResponse("login.html", ctx)

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        ctx["error"] = "Invalid username or password."
        return templates.TemplateResponse("login.html", ctx)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    return RedirectResponse("/", status_code=302)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "error": None,
    })


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx = {"request": request, "csrf_token": get_csrf_token(request)}

    if not validate_csrf_token(request, csrf_token):
        ctx["error"] = "Invalid request. Please try again."
        return templates.TemplateResponse("register.html", ctx)

    if len(username) < 3:
        ctx["error"] = "Username must be at least 3 characters."
        return templates.TemplateResponse("register.html", ctx)

    if len(password) < 8:
        ctx["error"] = "Password must be at least 8 characters."
        return templates.TemplateResponse("register.html", ctx)

    if password != confirm_password:
        ctx["error"] = "Passwords do not match."
        return templates.TemplateResponse("register.html", ctx)

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        ctx["error"] = "Username already taken."
        return templates.TemplateResponse("register.html", ctx)

    is_admin = bool(ADMIN_USERNAME and username == ADMIN_USERNAME)

    user = User(
        id=uuid.uuid4().hex,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    return RedirectResponse("/", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# --------------- Page routes ---------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": request.session.get("username", ""),
        "csrf_token": get_csrf_token(request),
        "is_admin": request.session.get("is_admin", False),
    })


@app.get("/gallery", response_class=HTMLResponse)
def gallery(
    request: Request,
    favorite: str = Query(None),
    tag: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(GeneratedImage).order_by(GeneratedImage.created_at.desc())

    if favorite == "1":
        query = query.filter(GeneratedImage.is_favorite == True)

    if tag:
        tag_image_ids = [t.image_id for t in db.query(ImageTag.image_id).filter(ImageTag.tag == tag).all()]
        query = query.filter(GeneratedImage.id.in_(tag_image_ids))

    images = query.limit(100).all()

    # Get all tags for filter bar
    all_tags = (
        db.query(ImageTag.tag)
        .distinct()
        .order_by(ImageTag.tag)
        .all()
    )
    all_tags = [t[0] for t in all_tags]

    # Get tags per image for display
    image_ids = [img.id for img in images]
    image_tags = {}
    if image_ids:
        tags_rows = db.query(ImageTag).filter(ImageTag.image_id.in_(image_ids)).all()
        for t in tags_rows:
            image_tags.setdefault(t.image_id, []).append(t.tag)

    return templates.TemplateResponse("gallery.html", {
        "request": request,
        "username": request.session.get("username", ""),
        "csrf_token": get_csrf_token(request),
        "images": images,
        "image_tags": image_tags,
        "all_tags": all_tags,
        "active_tag": tag,
        "active_favorite": favorite == "1",
    })


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")

    total = db.query(func.count(GeneratedImage.id)).filter(GeneratedImage.user_id == uid).scalar() or 0

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    today_count = (
        db.query(func.count(GeneratedImage.id))
        .filter(GeneratedImage.user_id == uid)
        .filter(func.substr(GeneratedImage.created_at, 1, 10) == today_str)
        .scalar() or 0
    )

    # Generations per day (last 14 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    day_expr = func.substr(GeneratedImage.created_at, 1, 10)
    daily_stats = (
        db.query(
            day_expr.label("day"),
            func.count(GeneratedImage.id).label("count"),
        )
        .filter(GeneratedImage.user_id == uid)
        .filter(GeneratedImage.created_at >= cutoff)
        .group_by(day_expr)
        .order_by(day_expr)
        .all()
    )
    daily_data = [{"day": row.day, "count": row.count} for row in daily_stats]
    max_daily = max((d["count"] for d in daily_data), default=1)

    # Model usage
    model_stats = (
        db.query(
            GeneratedImage.model_key,
            GeneratedImage.model_name,
            GeneratedImage.provider,
            func.count(GeneratedImage.id).label("count"),
        )
        .filter(GeneratedImage.user_id == uid)
        .group_by(GeneratedImage.model_key, GeneratedImage.model_name, GeneratedImage.provider)
        .order_by(func.count(GeneratedImage.id).desc())
        .all()
    )
    model_data = [{"key": r.model_key, "name": r.model_name, "provider": r.provider, "count": r.count} for r in model_stats]

    # Provider split
    provider_stats = (
        db.query(GeneratedImage.provider, func.count(GeneratedImage.id).label("count"))
        .filter(GeneratedImage.user_id == uid)
        .group_by(GeneratedImage.provider)
        .all()
    )
    provider_data = {r.provider: r.count for r in provider_stats}

    top_model = model_data[0]["name"] if model_data else "None yet"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": request.session.get("username", ""),
        "csrf_token": get_csrf_token(request),
        "total": total,
        "today_count": today_count,
        "top_model": top_model,
        "provider_data": provider_data,
        "daily_data": daily_data,
        "max_daily": max_daily,
        "model_data": model_data,
    })


# --------------- Share routes (public) ---------------

@app.get("/s/{share_token}", response_class=HTMLResponse)
def shared_image(share_token: str, request: Request, db: Session = Depends(get_db)):
    record = db.query(GeneratedImage).filter(
        GeneratedImage.share_token == share_token,
        GeneratedImage.is_public == True,
    ).first()
    if not record:
        return HTMLResponse("<h1>Image not found</h1>", status_code=404)
    return templates.TemplateResponse("share.html", {
        "request": request,
        "image": record,
    })


@app.get("/s/{share_token}/image")
def shared_image_file(share_token: str, db: Session = Depends(get_db)):
    record = db.query(GeneratedImage).filter(
        GeneratedImage.share_token == share_token,
        GeneratedImage.is_public == True,
    ).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    return Response(content=record.image_data, media_type="image/png")


# --------------- API routes ---------------

@app.post("/generate")
@limiter.limit("5/minute", exempt_when=_check_admin_exempt)
def generate(
    request: Request,
    prompt: str = Form(...),
    provider: str = Form(...),
    model_key: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(request, csrf_token):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    try:
        if provider == "gemini" and not request.session.get("is_admin"):
            return JSONResponse({"error": "Gemini models are restricted to admins only."}, status_code=403)

        if provider == "cloudflare":
            image_data = generate_cloudflare(prompt, model_key)
        elif provider == "gemini":
            image_data = generate_gemini(prompt, model_key)
        else:
            return JSONResponse({"error": f"Unknown provider: {provider}"}, status_code=400)

        if not image_data:
            return JSONResponse(
                {"error": "No image was generated. The prompt may have been filtered by the provider's content safety system. Try simplifying the prompt."},
                status_code=422,
            )

        model_info = ALL_MODELS.get(model_key, {})
        model_name = model_info.get("name", model_key)

        image_record = GeneratedImage(
            id=uuid.uuid4().hex,
            prompt=prompt,
            provider=provider,
            model_key=model_key,
            model_name=model_name,
            image_data=image_data,
            user_id=request.session.get("user_id"),
        )
        db.add(image_record)
        db.commit()

        return JSONResponse({
            "image_url": f"/image/{image_record.id}",
            "image_id": image_record.id,
        })

    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/generate/compare")
@limiter.limit("2/minute", exempt_when=_check_admin_exempt)
def generate_compare(
    request: Request,
    prompt: str = Form(...),
    model_keys: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(request, csrf_token):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    keys = [k.strip() for k in model_keys.split(",") if k.strip()]
    if len(keys) < 2 or len(keys) > 4:
        return JSONResponse({"error": "Select 2-4 models to compare."}, status_code=400)

    results = []
    for mk in keys:
        model_info = ALL_MODELS.get(mk)
        if not model_info:
            results.append({"model_key": mk, "model_name": mk, "error": "Unknown model"})
            continue

        provider = "gemini" if mk in GEMINI_MODELS else "cloudflare"
        if provider == "gemini" and not request.session.get("is_admin"):
            results.append({"model_key": mk, "model_name": model_info["name"], "error": "Admins only"})
            continue

        try:
            if provider == "cloudflare":
                image_data = generate_cloudflare(prompt, mk)
            else:
                image_data = generate_gemini(prompt, mk)

            if not image_data:
                results.append({"model_key": mk, "model_name": model_info["name"], "error": "Content filtered"})
                continue

            record = GeneratedImage(
                id=uuid.uuid4().hex,
                prompt=prompt,
                provider=provider,
                model_key=mk,
                model_name=model_info["name"],
                image_data=image_data,
                user_id=request.session.get("user_id"),
            )
            db.add(record)
            db.commit()

            results.append({
                "model_key": mk,
                "model_name": model_info["name"],
                "image_url": f"/image/{record.id}",
                "image_id": record.id,
            })
        except Exception as e:
            results.append({"model_key": mk, "model_name": model_info["name"], "error": str(e)[:100]})

    return JSONResponse({"results": results})


@app.get("/image/{image_id}")
def serve_image(image_id: str, db: Session = Depends(get_db)):
    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    return Response(content=record.image_data, media_type="image/png")


@app.get("/download/{image_id}")
def download(image_id: str, db: Session = Depends(get_db)):
    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    filename = f"gen_{record.created_at.strftime('%Y%m%d_%H%M%S')}_{image_id[:6]}.png"
    return Response(
        content=record.image_data,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/image/{image_id}")
def delete_image(request: Request, image_id: str, db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    db.query(ImageTag).filter(ImageTag.image_id == image_id).delete()
    db.delete(record)
    db.commit()
    return JSONResponse({"ok": True})


# --- Prompt history ---

@app.get("/api/prompts/recent")
def recent_prompts(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    rows = (
        db.query(GeneratedImage.prompt, func.max(GeneratedImage.created_at).label("latest"))
        .filter(GeneratedImage.user_id == uid)
        .group_by(GeneratedImage.prompt)
        .order_by(func.max(GeneratedImage.created_at).desc())
        .limit(20)
        .all()
    )
    return JSONResponse({"prompts": [r.prompt for r in rows]})


# --- Favorites ---

@app.post("/api/image/{image_id}/favorite")
def toggle_favorite(request: Request, image_id: str, db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    record.is_favorite = not record.is_favorite
    db.commit()
    return JSONResponse({"is_favorite": record.is_favorite})


# --- Tags ---

@app.post("/api/image/{image_id}/tags")
def add_tag(request: Request, image_id: str, tag: str = Form(...), db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    tag = tag.strip().lower()[:100]
    if not tag:
        return JSONResponse({"error": "Tag cannot be empty"}, status_code=400)

    existing = db.query(ImageTag).filter(ImageTag.image_id == image_id, ImageTag.tag == tag).first()
    if existing:
        return JSONResponse({"error": "Tag already exists"}, status_code=400)

    db.add(ImageTag(id=uuid.uuid4().hex, image_id=image_id, tag=tag))
    db.commit()
    return JSONResponse({"ok": True, "tag": tag})


@app.delete("/api/image/{image_id}/tags/{tag}")
def remove_tag(request: Request, image_id: str, tag: str, db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    row = db.query(ImageTag).filter(ImageTag.image_id == image_id, ImageTag.tag == tag).first()
    if row:
        db.delete(row)
        db.commit()
    return JSONResponse({"ok": True})


# --- Share ---

@app.post("/api/image/{image_id}/share")
def share_image(request: Request, image_id: str, db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)

    if not record.share_token:
        record.share_token = secrets.token_hex(16)
    record.is_public = True
    db.commit()
    return JSONResponse({"share_url": f"/s/{record.share_token}"})


@app.delete("/api/image/{image_id}/share")
def unshare_image(request: Request, image_id: str, db: Session = Depends(get_db)):
    csrf = request.headers.get("x-csrf-token", "")
    if not validate_csrf_token(request, csrf):
        return JSONResponse({"error": "Invalid CSRF token"}, status_code=403)

    record = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not record:
        return JSONResponse({"error": "Image not found"}, status_code=404)
    record.is_public = False
    db.commit()
    return JSONResponse({"ok": True})


# --------------- Provider functions ---------------

def generate_cloudflare(prompt: str, model_key: str) -> bytes | None:
    account_id = os.environ.get("CF_ACCOUNT_ID")
    api_token = os.environ.get("CF_API_TOKEN")

    if not account_id or not api_token:
        raise ValueError("CF_ACCOUNT_ID and CF_API_TOKEN environment variables are not set.")

    model_info = CLOUDFLARE_MODELS.get(model_key)
    if not model_info:
        raise ValueError(f"Unknown Cloudflare model: {model_key}")

    model_id = model_info["id"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_id}"

    response = http_requests.post(
        url,
        headers={"Authorization": f"Bearer {api_token}"},
        json={"prompt": prompt},
        timeout=120,
    )

    if response.status_code != 200:
        try:
            error = response.json()
            errors = error.get("errors", [])
            msg = errors[0].get("message", str(error)) if errors else str(error)
        except Exception:
            msg = response.text[:200]
        raise ValueError(f"Cloudflare API error ({response.status_code}): {msg}")

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        if not data.get("success", True):
            errors = data.get("errors", [])
            msg = errors[0].get("message", str(data)) if errors else str(data)
            raise ValueError(f"Cloudflare API error: {msg}")
        result = data.get("result", {})
        if isinstance(result, dict) and "image" in result:
            return base64.b64decode(result["image"])
        raise ValueError("Unexpected JSON response format from Cloudflare")

    image_data = response.content

    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        pixels = list(img.getdata())
        nonblack = sum(1 for r, g, b in pixels if r > 5 or g > 5 or b > 5)
        if nonblack / len(pixels) < 0.01:
            return None
    except ImportError:
        pass

    return image_data


def generate_gemini(prompt: str, model_key: str) -> bytes | None:
    from google import genai
    from google.genai import errors

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    model_info = GEMINI_MODELS.get(model_key)
    if not model_info:
        raise ValueError(f"Unknown Gemini model: {model_key}")

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_info["id"],
            contents=prompt,
            config={"response_modalities": ["TEXT", "IMAGE"]},
        )
    except errors.ClientError as e:
        raise ValueError(f"Gemini API error: {e}")

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    return None

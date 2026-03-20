import secrets

import bcrypt
from starlette.requests import Request


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def get_csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]


def validate_csrf_token(request: Request, token: str) -> bool:
    expected = request.session.get("csrf_token", "")
    if not expected or not token:
        return False
    return secrets.compare_digest(token, expected)

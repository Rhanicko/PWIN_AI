"""
Lightweight auth utilities for the admin layer (RBAC).

Implemented with the Python standard library only (PBKDF2 password hashing +
HMAC-signed tokens) so the platform has no hard auth dependency to boot. For a
hardened production deployment, swap in passlib[bcrypt] + python-jose (already
listed in requirements.txt).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings

_PBKDF_ROUNDS = 120_000


# --- Password hashing ------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:  # noqa: BLE001
        return False


# --- Token (HMAC-signed, JWT-like) -----------------------------------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(subject: str, role: str = "viewer") -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60,
    }
    body = _b64(json.dumps(payload).encode())
    sig = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def verify_token(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        expected = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(sig), expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None

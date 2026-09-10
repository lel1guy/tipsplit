"""Owner PIN gate — stdlib only, same shape as BarSpec's (proven there).

- PIN: pbkdf2_hmac(sha256, 260k iters, per-PIN salt); no bcrypt install needed.
- Session: HMAC-signed cookie (expiry + signature), secret generated on first
  setup and kept in settings.
- Everything except the login routes, the page itself and /static is gated once
  a PIN exists — including /print (payslips carry money).
"""
import hashlib
import hmac
import os
import secrets
import time

import db

_ITER = 260_000
COOKIE = "tipsplit_sesh"
_MAX_AGE = 60 * 60 * 24 * 14        # 14 days, then re-enter the PIN

PIN_KEY = "auth.pin_hash"
SECRET_KEY = "auth.secret"

_fails: dict[str, list[float]] = {}   # ip -> failed-attempt timestamps


def _derive(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _ITER)


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    return f"pbkdf2${_ITER}${salt.hex()}${_derive(pin, salt).hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        salt, expect = bytes.fromhex(salt_hex), bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, int(iters))
    return hmac.compare_digest(got, expect)


def pin_is_set() -> bool:
    return bool(db.get_setting(PIN_KEY))


def set_pin(pin: str) -> None:
    db.set_setting(PIN_KEY, hash_pin(pin))


def check_pin(pin: str) -> bool:
    stored = db.get_setting(PIN_KEY)
    return bool(stored) and verify_pin(pin, stored)


def _secret() -> str:
    s = db.get_setting(SECRET_KEY)
    if not s:
        s = secrets.token_hex(32)
        db.set_setting(SECRET_KEY, s)
    return s


def cookie_valid(value: str | None) -> bool:
    """Kept for callers that only care whether a session exists."""
    return session_from_token(value) is not None


def session_from_token(value: str | None):
    """('owner', None) | ('staff', staff_id) | None (expired, forged, malformed).

    Token = role.staff_id.exp.signature — the role and the person are signed, so a
    staff cookie can never be edited into an owner one.
    """
    if not value:
        return None
    parts = value.split(".")
    if len(parts) != 4:
        return None
    role, sid, exp, sig = parts
    if role not in ("owner", "staff"):
        return None
    expect = hmac.new(_secret().encode(), f"{role}.{sid}.{exp}".encode(),
                      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        if int(exp) <= time.time():
            return None
        return ("owner", None) if role == "owner" else ("staff", int(sid))
    except ValueError:
        return None


def make_cookie(role: str = "owner", staff_id: int | None = None) -> str:
    exp = str(int(time.time()) + _MAX_AGE)
    payload = f"{role}.{staff_id or ''}.{exp}"
    sig = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return (f"{COOKIE}={payload}.{sig}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={_MAX_AGE}")


def clear_cookie() -> str:
    return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


# ---------- brute-force brake ----------

MAX_FAILS = 5
WINDOW = 300          # seconds


def too_many_attempts(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _fails.get(ip, []) if now - t < WINDOW]
    _fails[ip] = hits
    return len(hits) >= MAX_FAILS


def note_failure(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def clear_failures(ip: str) -> None:
    _fails.pop(ip, None)

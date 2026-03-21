"""
Auth router — registration, login, email verification, 2FA, OAuth SSO (Google + GitHub).
"""
import hashlib
import json
import os
import secrets
import time
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import pyotp

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.core.auth import (
    hash_password, verify_password, create_access_token, decode_token,
)
from app.core.deps import get_current_user
from app.core.security import (
    limiter, validate_password, log_auth_failure, log_auth_success,
    MAX_PROJECT_NAME, clamp_str,
)
from app.core.email import send_verification_email
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── OAuth state store (CSRF protection) ──────────────────────────────────────
# Maps state token → (provider, timestamp). Single-process safe; for
# multi-worker deployments move this to Redis via settings.REDIS_URL.
_oauth_states: dict[str, tuple[str, float]] = {}

def _clean_oauth_states() -> None:
    """Purge states older than 10 minutes."""
    cutoff = time.time() - 600
    expired = [k for k, (_, ts) in _oauth_states.items() if ts < cutoff]
    for k in expired:
        del _oauth_states[k]

def _oauth_redirect_base() -> str:
    """
    Base URL used to build the callback URI that OAuth providers redirect to.
    On Digital Ocean (single domain, Nginx proxies /api → backend) this is the
    same as FRONTEND_URL.  Override with OAUTH_REDIRECT_BASE if your setup
    differs (e.g. standalone backend on a different port in local dev).
    """
    return settings.OAUTH_REDIRECT_BASE or settings.FRONTEND_URL


# ── OAuth token exchange helpers ──────────────────────────────────────────────

async def _exchange_google(code: str, redirect_uri: str) -> dict:
    """Exchange Google auth code for user info. Returns dict with email/id/name/avatar."""
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        data = userinfo_resp.json()

    if not data.get("email_verified"):
        raise ValueError("Google account email is not verified")

    return {
        "email":  data["email"],
        "id":     data["sub"],
        "name":   data.get("name", ""),
        "avatar": data.get("picture"),
    }


async def _exchange_github(code: str, redirect_uri: str) -> dict:
    """Exchange GitHub auth code for user info. Returns dict with email/id/name/avatar."""
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "code": code,
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        if "error" in token_data:
            raise ValueError(f"GitHub token error: {token_data.get('error_description', token_data['error'])}")
        access_token = token_data["access_token"]

        gh_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        user_resp = await client.get("https://api.github.com/user", headers=gh_headers)
        user_resp.raise_for_status()
        user_data = user_resp.json()

        # GitHub may hide email — fetch from the emails endpoint
        email = user_data.get("email")
        if not email:
            emails_resp = await client.get("https://api.github.com/user/emails", headers=gh_headers)
            emails_resp.raise_for_status()
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if not primary:
                raise ValueError("No verified primary email found in GitHub account")
            email = primary["email"]

    return {
        "email":  email,
        "id":     str(user_data["id"]),
        "name":   user_data.get("name") or user_data.get("login", ""),
        "avatar": user_data.get("avatar_url"),
    }


# ── Pydantic request bodies ───────────────────────────────────────────────────

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class TFAEnableBody(BaseModel):
    secret: str
    code: str

class TFACodeBody(BaseModel):
    code: str

class TFAVerifyBody(BaseModel):
    temp_token: str
    code: str

class ResendBody(BaseModel):
    email: EmailStr


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_temp_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "scope": "2fa_pending"},
        expires_delta=timedelta(minutes=5),
    )

def _verify_temp_token(token: str) -> int:
    payload = decode_token(token)
    if not payload or payload.get("scope") != "2fa_pending":
        raise HTTPException(status_code=401, detail="Invalid or expired 2FA challenge token")
    return int(payload["sub"])

def _check_recovery_code(code: str, hashed_codes: list) -> int | None:
    for i, hashed in enumerate(hashed_codes):
        if verify_password(code, hashed):
            return i
    return None

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def _issue_verification_token(user: User, db: Session) -> str:
    raw = secrets.token_urlsafe(32)
    user.email_verification_token_hash = _hash_token(raw)
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db.commit()
    return raw

def _do_login(request: Request, email_raw: str, password: str, db: Session):
    ip = request.client.host if request.client else "unknown"
    email = email_raw.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        log_auth_failure(ip, email, "user_not_found")
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    if user.hashed_password is None:
        log_auth_failure(ip, email, "oauth_only_account")
        raise HTTPException(status_code=400, detail="This account was created via OAuth. Please sign in with Google or GitHub.")
    if not verify_password(password, user.hashed_password):
        log_auth_failure(ip, email, "bad_password")
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        log_auth_failure(ip, email, "inactive")
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Block login until email verified (only if verification is enabled)
    if settings.EMAIL_VERIFICATION_ENABLED and not user.email_verified:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")

    if user.totp_enabled:
        return {"requires_2fa": True, "temp_token": _make_temp_token(user.id)}

    log_auth_success(ip, user.id, email)
    return {"access_token": create_access_token({"sub": str(user.id)}), "token_type": "bearer"}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    email = user_in.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")

    err = validate_password(user_in.password)
    if err:
        raise HTTPException(status_code=422, detail=err)

    full_name = clamp_str(user_in.full_name.strip(), MAX_PROJECT_NAME)
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(user_in.password),
        is_active=True,
        email_verified=not settings.EMAIL_VERIFICATION_ENABLED,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if settings.EMAIL_VERIFICATION_ENABLED:
        raw_token = _issue_verification_token(user, db)
        try:
            await send_verification_email(user.email, user.full_name, raw_token)
        except Exception:
            pass  # Don't block registration if email fails

    return user


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    if not token or len(token) > 128:
        raise HTTPException(status_code=400, detail="Invalid token")
    token_hash = _hash_token(token)
    user = db.query(User).filter(
        User.email_verification_token_hash == token_hash
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or already used verification link")
    now = datetime.now(timezone.utc)
    expires = user.email_verification_expires_at
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            raise HTTPException(status_code=400, detail="Verification link expired. Request a new one from the login page.")
    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.commit()
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(request: Request, body: ResendBody, db: Session = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified and user.hashed_password:
        raw_token = _issue_verification_token(user, db)
        try:
            await send_verification_email(user.email, user.full_name, raw_token)
            logger.info("Verification email sent to %s", email)
        except Exception as exc:
            logger.error("Failed to send verification email to %s: %s", email, exc)
            raise HTTPException(status_code=500, detail="EMAIL_SEND_FAILED")
    return {"message": "If that email is registered and unverified, a new link has been sent."}


@router.post("/test-email")
async def test_email(request: Request, body: ResendBody, current_user: "User" = Depends(get_current_user)):
    """Send a test email to verify SMTP configuration. Requires authentication."""
    import logging
    from app.config import settings as s
    logger = logging.getLogger(__name__)
    logger.info(
        "SMTP config: host=%s port=%s tls=%s from=%s frontend_url=%s",
        s.SMTP_HOST, s.SMTP_PORT, s.SMTP_TLS, s.SMTP_FROM, s.FRONTEND_URL,
    )
    if not s.SMTP_HOST:
        raise HTTPException(status_code=503, detail="SMTP_NOT_CONFIGURED")
    try:
        await send_verification_email(body.email, current_user.full_name, "test-token-not-valid")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"EMAIL_SEND_FAILED: {exc}")
    return {"message": f"Test email sent to {body.email}"}


@router.post("/login", response_model=None)
@limiter.limit("20/minute")
def login_json(request: Request, body: LoginBody, db: Session = Depends(get_db)):
    return _do_login(request, body.email, body.password, db)


@router.post("/login/form", response_model=None, include_in_schema=False)
@limiter.limit("20/minute")
def login_form(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _do_login(request, form_data.username, form_data.password, db)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ── OAuth SSO — Google & GitHub ───────────────────────────────────────────────

@router.get("/oauth/{provider}", include_in_schema=False)
def oauth_init(provider: str):
    """
    Step 1 — redirect the browser to the provider's authorization page.
    The frontend navigates to this URL directly (window.location.href).
    """
    if provider not in ("google", "github"):
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider")

    if provider == "google" and not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured on this server")
    if provider == "github" and not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured on this server")

    state = secrets.token_urlsafe(32)
    _clean_oauth_states()
    _oauth_states[state] = (provider, time.time())

    base = _oauth_redirect_base()
    callback_uri = f"{base}/api/auth/oauth/{provider}/callback"

    if provider == "google":
        params = urlencode({
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "redirect_uri":  callback_uri,
            "response_type": "code",
            "scope":         "openid email profile",
            "state":         state,
            "access_type":   "offline",
            "prompt":        "select_account",
        })
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    else:  # github
        params = urlencode({
            "client_id":    settings.GITHUB_CLIENT_ID,
            "redirect_uri": callback_uri,
            "scope":        "read:user user:email",
            "state":        state,
        })
        auth_url = f"https://github.com/login/oauth/authorize?{params}"

    return RedirectResponse(auth_url, status_code=302)


@router.get("/oauth/{provider}/callback", include_in_schema=False)
async def oauth_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    code: str = None,
    state: str = None,
    error: str = None,
):
    """
    Step 2 — OAuth provider redirects here with ?code=&state=.
    We exchange the code for user info, create/find the user, issue a JWT,
    then redirect the browser to the frontend with #token=<jwt> in the hash
    (never in the query string, to keep it out of server logs).
    """
    frontend = settings.FRONTEND_URL
    error_redirect = f"{frontend}/login?oauth_error="

    if error or not code or not state:
        logger.warning("OAuth %s init error: %s", provider, error)
        return RedirectResponse(f"{error_redirect}access_denied", status_code=302)

    if provider not in ("google", "github"):
        return RedirectResponse(f"{error_redirect}unsupported_provider", status_code=302)

    if state not in _oauth_states:
        logger.warning("OAuth %s: invalid or expired state", provider)
        return RedirectResponse(f"{error_redirect}invalid_state", status_code=302)

    stored_provider, ts = _oauth_states.pop(state)
    if stored_provider != provider or time.time() - ts > 600:
        logger.warning("OAuth %s: state mismatch or expired", provider)
        return RedirectResponse(f"{error_redirect}invalid_state", status_code=302)

    base = _oauth_redirect_base()
    callback_uri = f"{base}/api/auth/oauth/{provider}/callback"

    try:
        if provider == "google":
            user_info = await _exchange_google(code, callback_uri)
        else:
            user_info = await _exchange_github(code, callback_uri)
    except Exception as exc:
        logger.error("OAuth %s exchange failed: %s", provider, exc)
        return RedirectResponse(f"{error_redirect}exchange_failed", status_code=302)

    email  = user_info["email"].lower().strip()
    name   = clamp_str((user_info.get("name") or email.split("@")[0]).strip(), MAX_PROJECT_NAME)
    avatar = user_info.get("avatar")

    # Find existing user or create one
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Link OAuth provider if account was email-only
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = str(user_info["id"])
        # OAuth login auto-verifies the email
        if not user.email_verified:
            user.email_verified = True
        if avatar and not user.avatar_url:
            user.avatar_url = avatar
        db.commit()
    else:
        user = User(
            email=email,
            full_name=name,
            hashed_password=None,          # OAuth-only account
            is_active=True,
            email_verified=True,           # Provider already verified
            oauth_provider=provider,
            oauth_id=str(user_info["id"]),
            avatar_url=avatar,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        logger.warning("OAuth login attempt for inactive user %s", email)
        return RedirectResponse(f"{error_redirect}account_inactive", status_code=302)

    jwt_token = create_access_token({"sub": str(user.id)})
    logger.info("OAuth %s login success for user %s (id=%s)", provider, email, user.id)

    # Redirect to frontend OAuth callback route with token in hash fragment
    return RedirectResponse(
        f"{frontend}/oauth/{provider}/callback#token={jwt_token}",
        status_code=302,
    )


# ── Two-Factor Authentication ─────────────────────────────────────────────────

@router.post("/2fa/setup")
def tfa_setup(current_user: User = Depends(get_current_user)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name="Axelo")
    return {"secret": secret, "uri": uri}


@router.post("/2fa/enable")
@limiter.limit("10/minute")
def tfa_enable(request: Request, body: TFAEnableBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    if not pyotp.TOTP(body.secret).verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    raw_codes = [secrets.token_hex(8).upper() for _ in range(10)]
    hashed_codes = [hash_password(c) for c in raw_codes]
    current_user.totp_secret = body.secret
    current_user.totp_enabled = True
    current_user.totp_recovery_codes = json.dumps(hashed_codes)
    db.commit()
    return {"recovery_codes": raw_codes, "message": "2FA enabled. Save these recovery codes."}


@router.post("/2fa/verify", response_model=None)
@limiter.limit("5/minute")
def tfa_verify(request: Request, body: TFAVerifyBody, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    user_id = _verify_temp_token(body.temp_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled for this account")
    if pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        log_auth_success(ip, user.id, user.email)
        return {"access_token": create_access_token({"sub": str(user.id)}), "token_type": "bearer"}
    stored = json.loads(user.totp_recovery_codes or "[]")
    idx = _check_recovery_code(body.code.upper(), stored)
    if idx is not None:
        stored.pop(idx)
        user.totp_recovery_codes = json.dumps(stored)
        db.commit()
        log_auth_success(ip, user.id, user.email)
        return {"access_token": create_access_token({"sub": str(user.id)}), "token_type": "bearer"}
    log_auth_failure(ip, user.email, "invalid_totp")
    raise HTTPException(status_code=401, detail="Invalid 2FA code")


@router.post("/2fa/disable")
@limiter.limit("5/minute")
def tfa_disable(request: Request, body: TFACodeBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not pyotp.TOTP(current_user.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    current_user.totp_recovery_codes = None
    db.commit()
    return {"message": "2FA disabled"}


@router.get("/2fa/status")
def tfa_status(current_user: User = Depends(get_current_user)):
    return {"enabled": current_user.totp_enabled}


@router.post("/reseed")
def reseed_demo_data():
    """Manually trigger demo seed. Safe to call multiple times — skips if data exists."""
    from app.seed import seed as run_seed
    try:
        run_seed()
        return {"status": "ok", "message": "Seed completed (or skipped if data already exists)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")

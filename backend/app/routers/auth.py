"""
Auth router — registration, login, email verification, 2FA.
OAuth (Google/GitHub) and CAPTCHA removed — not configured on this deployment.
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

import pyotp

from fastapi import APIRouter, Depends, HTTPException, status, Request
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

router = APIRouter(prefix="/api/auth", tags=["auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


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
    # Registration is currently closed. Remove this block to re-enable.
    raise HTTPException(
        status_code=503,
        detail="REGISTRATION_CLOSED"
    )


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
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified and user.hashed_password:
        raw_token = _issue_verification_token(user, db)
        try:
            await send_verification_email(user.email, user.full_name, raw_token)
        except Exception:
            pass
    return {"message": "If that email is registered and unverified, a new link has been sent."}


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

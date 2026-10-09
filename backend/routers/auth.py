"""
Email-OTP (şifresiz) kimlik doğrulama.

Akış: POST /request-pin {email} -> kullanıcıya 6 haneli kod ("gönderilir")
      -> POST /verify-pin {email, code} -> JWT access_token + kullanıcının mağazaları
      -> GET /me (Authorization: Bearer <token>) -> profil + mağaza listesi

Not: Bu projede henüz bir email gönderim servisi entegre değil. DEBUG=True iken
(env.example varsayılanı) /request-pin yanıtına kod dev-only olarak eklenir ki
frontend/QA gerçek email olmadan test edebilsin. Production'a alınırken bu davranış
kaldırılmalı / gerçek bir email sağlayıcısına (SMTP, Resend, SES vb.) bağlanmalıdır.
"""
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import OTPCode, Store, User
from security import (
    OTP_MAX_ATTEMPTS,
    OTP_TTL_MINUTES,
    create_access_token,
    generate_otp_code,
    get_current_user,
    hash_otp_code,
    verify_otp_hash,
)

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _debug_enabled() -> bool:
    # Not: main.py routers'ı import ettikten SONRA load_dotenv() çağırıyor, bu yüzden
    # DEBUG'ı modül import anında değil, her istek anında (lazy) okumak gerekiyor —
    # aksi halde .env'deki DEBUG=True henüz os.environ'a yüklenmeden önce yanlış
    # (varsayılan False) değer cache'lenmiş olurdu.
    return os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")


class RequestPinBody(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Geçerli bir email adresi girin")
        return v


class VerifyPinBody(BaseModel):
    email: str
    code: str


def _store_summary(stores: list[Store]) -> list[dict]:
    return [{"id": s.id, "store_name": s.store_name, "is_active": s.is_active} for s in stores]


@router.post("/request-pin")
async def request_pin(body: RequestPinBody, db: Session = Depends(get_db)):
    """Email'e 6 haneli giriş kodu gönderir (kod 5 dakika geçerli)."""
    now = datetime.now(timezone.utc)

    # Basit spam koruması: son 60 saniye içinde bu email için hâlâ geçerli/tüketilmemiş
    # bir kod üretildiyse yeni kod ÜRETME, aynı bekleme mesajını dön.
    recent = (
        db.query(OTPCode)
        .filter(OTPCode.email == body.email, OTPCode.consumed_at.is_(None))
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if recent and recent.created_at and (now.replace(tzinfo=None) - recent.created_at) < timedelta(seconds=60):
        return {"sent": True, "message": "Kod zaten gönderildi, birkaç saniye sonra tekrar deneyin"}

    code = generate_otp_code()
    otp = OTPCode(
        email=body.email,
        code_hash=hash_otp_code(body.email, code),
        purpose="login",
        attempts=0,
        expires_at=now.replace(tzinfo=None) + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(otp)
    db.commit()

    # TODO(Phase2/entegrasyon): gerçek email gönderimi (SMTP/SES/Resend) buraya bağlanacak.
    print(f"[Auth] OTP kodu ({body.email}): {code} — {OTP_TTL_MINUTES} dk geçerli")

    response = {"sent": True, "message": f"Kod email'inize gönderildi ({OTP_TTL_MINUTES} dk geçerli)"}
    if _debug_enabled():
        response["debug_code"] = code  # SADECE DEBUG=True iken — dev/QA kolaylığı, prod'da kapatılmalı
    return response


@router.post("/verify-pin")
async def verify_pin(body: VerifyPinBody, db: Session = Depends(get_db)):
    """Kodu doğrular, kullanıcıyı (yoksa) oluşturur ve JWT access_token döner."""
    email = body.email.strip().lower()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    otp = (
        db.query(OTPCode)
        .filter(OTPCode.email == email, OTPCode.consumed_at.is_(None))
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu email için aktif bir kod yok, önce kod isteyin")
    if otp.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kodun süresi doldu, yeni kod isteyin")
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Çok fazla hatalı deneme, yeni kod isteyin")

    if not verify_otp_hash(email, body.code.strip(), otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kod hatalı")

    otp.consumed_at = now
    db.commit()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, is_active=True, last_login_at=now)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login_at = now
        db.commit()

    stores = db.query(Store).filter(Store.user_id == user.id, Store.is_active == True).all()  # noqa: E712
    default_store_id = stores[0].id if len(stores) == 1 else None

    token = create_access_token(user_id=user.id, store_id=default_store_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
        "stores": _store_summary(stores),
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stores = db.query(Store).filter(Store.user_id == user.id).all()
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "stores": _store_summary(stores),
    }


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """JWT stateless olduğu için sunucu tarafında iptal edilmez; frontend token'ı atar.
    Endpoint sadece API tutarlılığı/gelecekteki blok-listesi için burada."""
    return {"message": "Çıkış yapıldı, client token'ı silmeli"}

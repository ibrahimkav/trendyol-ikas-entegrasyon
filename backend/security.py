"""
Auth/Güvenlik yardımcıları: JWT oturum token'ları, email-OTP hash/doğrulama,
mağaza API kimlik bilgilerini şifreleme (Fernet) ve FastAPI dependency'leri
(get_current_user / get_current_store).

Wave 1 kapsamı: bu modül YENİ auth + store-connect endpoint'leri için kullanılır.
Mevcut ~135 iş endpoint'i bu wave'de retrofit edilmiyor (bkz. hive raporu) — o yüzden
mevcut router'lar bu dependency'leri henüz import etmiyor.
"""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Store, User

# ---------------------------------------------------------------------------
# JWT (oturum token'ı)
# ---------------------------------------------------------------------------
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30


def _jwt_secret() -> str:
    # NOT: main.py, routers'ı (dolayısıyla bu modülü) import ettikten SONRA load_dotenv()
    # çağırıyor — bu yüzden .env değerleri modül import anında değil, her çağrıda (lazy)
    # okunmalı; aksi halde henüz os.environ'a yüklenmemiş değerler yerine sabit fallback
    # cache'lenir (codebase'teki utils/trendyol_api.py'deki lazy-getenv kalıbıyla tutarlı).
    return os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "dev-insecure-secret-change-me"


def create_access_token(user_id: int, store_id: Optional[int] = None) -> str:
    payload = {
        "sub": str(user_id),
        "store_id": store_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum süresi doldu, tekrar giriş yapın")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz oturum token'ı")


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization: Bearer <token> gerekli")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı veya pasif")
    return user


def get_current_store(
    x_store_id: Optional[int] = Header(None, alias="X-Store-Id"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Store:
    """
    Aktif mağazayı belirler (öncelik sırasıyla):
    1. X-Store-Id header'ı (kullanıcı birden çok mağazaya sahipse frontend seçtirir)
    2. JWT'deki store_id claim'i (tek mağazalı kullanıcı için login sırasında set edilir)
    3. Fallback: kullanıcının TEK aktif mağazası varsa onu kullan. Bu, login'den SONRA
       mağaza oluşturulduğunda JWT'nin eski/null store_id taşımasını tolere eder
       (Oscar 2026-09-12'de bu sharp-edge'i bildirdi: token login anında dondurulduğu
       için sonradan eklenen mağaza claim'e yansımıyordu). Böylece tek mağazalı akış
       X-Store-Id header'ı GÖNDERİLMESE de çalışır; çoklu mağazada hâlâ header şart.
    Her durumda mağazanın gerçekten bu kullanıcıya ait olduğu doğrulanır
    (başka kullanıcının store_id'sini header'a yazıp veri sızdırmayı engeller).
    """
    store_id = x_store_id
    if store_id is None:
        payload = decode_access_token(authorization.split(" ", 1)[1].strip())
        store_id = payload.get("store_id")

    if store_id is None:
        # Fallback: kullanıcının tek aktif mağazası varsa onu seç.
        active_stores = db.query(Store).filter(Store.user_id == user.id, Store.is_active == True).all()  # noqa: E712
        if len(active_stores) == 1:
            return active_stores[0]
        if len(active_stores) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Henüz bir mağaza bağlamadınız — önce bir mağaza oluşturun/bağlayın",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Birden çok mağazanız var — hangisi olduğunu X-Store-Id header'ı ile belirtin",
        )

    store = db.query(Store).filter(Store.id == store_id, Store.user_id == user.id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu mağaza size ait değil")
    return store


# ---------------------------------------------------------------------------
# Email-OTP
# ---------------------------------------------------------------------------
OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5


def generate_otp_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def hash_otp_code(email: str, code: str) -> str:
    pepper = os.getenv("OTP_PEPPER") or _jwt_secret()  # hash'e ek tuz (secret'tan türetilir)
    raw = f"{email.lower().strip()}:{code}:{pepper}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_otp_hash(email: str, code: str, code_hash: str) -> bool:
    return secrets.compare_digest(hash_otp_code(email, code), code_hash)


# ---------------------------------------------------------------------------
# Mağaza API kimlik bilgisi şifreleme (Fernet — simetrik, at-rest encryption)
# ---------------------------------------------------------------------------
def _get_fernet() -> Fernet:
    raw_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if raw_key:
        key = raw_key.encode("utf-8")
    else:
        # .env'de ayrı bir anahtar yoksa SECRET_KEY'den deterministik türet (dev fallback).
        # ÜRETİMDE: CREDENTIAL_ENCRYPTION_KEY mutlaka ayrı, rastgele üretilmiş bir Fernet
        # anahtarı olarak .env'e eklenmeli (Fernet.generate_key() ile), buraya hardcode edilmez.
        digest = hashlib.sha256(f"credential-key:{_jwt_secret()}".encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def mask_secret(plaintext: str) -> str:
    """Frontend'e göstermek için: sadece son 4 karakteri açık, gerisi maskeli."""
    if len(plaintext) <= 4:
        return "*" * len(plaintext)
    return "*" * (len(plaintext) - 4) + plaintext[-4:]

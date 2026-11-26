import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretNotConfigured(RuntimeError):
    pass


def _fernet() -> Fernet:
    secret = get_settings().app_secret
    if len(secret) < 32:
        raise SecretNotConfigured("APP_SECRET ausente ou curto demais (mínimo 32 caracteres) no .env")
    key = base64.urlsafe_b64encode(hashlib.sha256(b"kavria-fernet:" + secret.encode()).digest())
    return Fernet(key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretNotConfigured(
            "Não foi possível descriptografar os tokens: o APP_SECRET mudou. Reautorize o Mercado Livre."
        ) from exc


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_secret() -> str:
    return secrets.token_urlsafe(48)


def pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge S256)"""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    return verifier, challenge.decode()

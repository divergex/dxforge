import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from dxforge.config import settings
from dxforge.db.models import Tenant


def generate_key() -> str:
    return secrets.token_urlsafe(32)


def hash_key(plaintext: str) -> str:
    """deterministic salted hash so lookups can use equality predicate."""
    return hashlib.sha256(
        settings.api_key_pepper.encode() + plaintext.encode()
    ).hexdigest()


def verify_key(plaintext: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_key(plaintext), stored_hash)


def rotate_api_key(tenant: Tenant, session: Session) -> str:
    new_key = generate_key()
    tenant.api_key_hash = hash_key(new_key)
    session.commit()
    return new_key

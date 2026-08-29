import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dxforge.crypto.wipe import SecretBytes

NONCE_LEN = 12
KEY_LEN = 32


def encrypt_bytes(dek: bytes | SecretBytes, plaintext: bytes) -> bytes:
    key = _key_bytes(dek)
    nonce = os.urandom(NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_bytes(dek: bytes | SecretBytes, ciphertext: bytes) -> bytes:
    key = _key_bytes(dek)
    nonce, payload = ciphertext[:NONCE_LEN], ciphertext[NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, payload, None)


def _key_bytes(dek: bytes | SecretBytes) -> bytes:
    return dek.as_bytes() if isinstance(dek, SecretBytes) else dek

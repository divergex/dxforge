import os

import pytest

from dxforge.crypto.envelope import NONCE_LEN, decrypt_bytes, encrypt_bytes
from dxforge.crypto.wipe import SecretBytes


def test_roundtrip() -> None:
    dek = os.urandom(32)
    plaintext = b"tenant code artifact"
    ciphertext = encrypt_bytes(dek, plaintext)
    assert ciphertext != plaintext
    assert decrypt_bytes(dek, ciphertext) == plaintext


def test_nonce_is_prepended() -> None:
    dek = os.urandom(32)
    ciphertext = encrypt_bytes(dek, b"x")
    assert len(ciphertext) == NONCE_LEN + 16 + 1


def test_wrong_key_fails() -> None:
    ciphertext = encrypt_bytes(os.urandom(32), b"data")
    with pytest.raises(Exception):
        decrypt_bytes(os.urandom(32), ciphertext)


def test_tampered_ciphertext_fails() -> None:
    ciphertext = bytearray(encrypt_bytes(os.urandom(32), b"data"))
    ciphertext[-1] ^= 0x01
    with pytest.raises(Exception):
        decrypt_bytes(os.urandom(32), bytes(ciphertext))


def test_accepts_secret_bytes_key() -> None:
    with SecretBytes(os.urandom(32)) as dek:
        ciphertext = encrypt_bytes(dek, b"payload")
        assert decrypt_bytes(dek, ciphertext) == b"payload"


def test_secret_bytes_wipe_zeroes_in_place() -> None:
    dek = SecretBytes(b"0123456789")
    assert len(dek) == 10
    dek.wipe()
    assert dek.as_bytes() == b"\x00" * 10


def test_secret_bytes_context_manager_wipes() -> None:
    with SecretBytes(b"0123456789") as dek:
        assert dek.as_bytes() == b"0123456789"
    assert dek.as_bytes() == b"\x00" * 10

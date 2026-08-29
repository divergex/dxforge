from dxforge.auth.api_keys import generate_key, hash_key, verify_key


def test_generate_key_is_unique_and_high_entropy() -> None:
    keys = {generate_key() for _ in range(100)}
    assert len(keys) == 100
    assert all(len(k) >= 40 for k in keys)


def test_hash_verify_roundtrip() -> None:
    key = generate_key()
    assert verify_key(key, hash_key(key))


def test_wrong_key_rejected() -> None:
    assert not verify_key(generate_key(), hash_key(generate_key()))


def test_hash_is_deterministic() -> None:
    key = generate_key()
    assert hash_key(key) == hash_key(key)


def test_plaintext_not_recoverable_from_hash() -> None:
    key = generate_key()
    digest = hash_key(key)
    assert key not in digest
    assert len(digest) == 64

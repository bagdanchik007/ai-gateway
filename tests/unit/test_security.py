"""Tests für app/core/security.py."""

from app.core.security import API_KEY_PREFIX, generate_api_key, hash_api_key


def test_generated_key_has_expected_prefix() -> None:
    plain_key, _, key_prefix = generate_api_key()
    assert plain_key.startswith(API_KEY_PREFIX)
    assert key_prefix == plain_key[:12]


def test_hash_is_deterministic_and_matches_stored_hash() -> None:
    plain_key, key_hash, _ = generate_api_key()
    assert hash_api_key(plain_key) == key_hash


def test_two_generated_keys_are_never_equal() -> None:
    """Reine Kollisionswahrscheinlichkeit ist bei 256 Bit Zufall vernachlässigbar,

    der Test prüft trotzdem, dass wir nicht versehentlich einen konstanten
    Wert zurückgeben (z. B. durch einen kaputten Zufallsgenerator-Mock).
    """
    key_a, hash_a, _ = generate_api_key()
    key_b, hash_b, _ = generate_api_key()
    assert key_a != key_b
    assert hash_a != hash_b


def test_hash_does_not_reveal_plaintext() -> None:
    plain_key, key_hash, _ = generate_api_key()
    assert plain_key not in key_hash
    assert len(key_hash) == 64  # sha256 hexdigest

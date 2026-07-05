import pytest

from app.security.crypto import TokenCryptoError, decrypt_token, encrypt_token


def test_round_trip():
    blob, version = encrypt_token("secret-token-value")
    assert version == 1
    assert "secret-token-value" not in blob
    assert decrypt_token(blob, version) == "secret-token-value"


def test_tampered_ciphertext_fails():
    blob, version = encrypt_token("abc")
    tampered = blob[:-4] + ("AAAA" if not blob.endswith("AAAA") else "BBBB")
    with pytest.raises(TokenCryptoError):
        decrypt_token(tampered, version)


def test_unknown_key_version_fails():
    blob, _ = encrypt_token("abc")
    with pytest.raises(TokenCryptoError):
        decrypt_token(blob, 99)

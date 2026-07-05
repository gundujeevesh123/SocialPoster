"""AES-256-GCM token encryption (envelope-encryption-ready).

Dev: key from TOKEN_ENC_KEY_B64 env (base64, 32 bytes). Production upgrade path:
wrap this data key with cloud KMS and bump key_version — decrypt() already
dispatches on version, so rotation is additive.
"""
import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

_NONCE_LEN = 12


class TokenCryptoError(Exception):
    pass


def _load_key(version: int) -> bytes:
    s = get_settings()
    if version != s.token_enc_key_version:
        raise TokenCryptoError(f"no key for version {version}")
    raw = s.token_enc_key_b64
    if not raw:
        raise TokenCryptoError(
            "TOKEN_ENC_KEY_B64 is not set. Generate one:  python -c \"import os,base64;print(base64.b64encode(os.urandom(32)).decode())\""
        )
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise TokenCryptoError("TOKEN_ENC_KEY_B64 must decode to exactly 32 bytes")
    return key


def encrypt_token(plaintext: str) -> tuple[str, int]:
    """Returns (base64(nonce||ciphertext), key_version)."""
    s = get_settings()
    key = _load_key(s.token_enc_key_version)
    nonce = os.urandom(_NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii"), s.token_enc_key_version


def decrypt_token(blob_b64: str, key_version: int) -> str:
    key = _load_key(key_version)
    blob = base64.b64decode(blob_b64)
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    try:
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:  # wrong key / tampered ciphertext
        raise TokenCryptoError("token decryption failed") from e


def new_state() -> str:
    """CSRF state for OAuth flows."""
    return secrets.token_urlsafe(32)

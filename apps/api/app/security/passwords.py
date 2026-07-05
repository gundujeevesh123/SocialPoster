from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()  # argon2id defaults (memory-hard)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _ph.verify(password_hash, candidate)
    except VerifyMismatchError:
        return False
    except Exception:
        return False

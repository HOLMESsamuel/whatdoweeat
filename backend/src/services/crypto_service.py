"""Symmetric encryption for sensitive values stored in Mongo (Dropbox
refresh tokens, OAuth state).

Uses Fernet — authenticated AES-128 with a 32-byte key encoded as
url-safe base64. The key lives in the DROPBOX_TOKEN_ENC_KEY env var;
generate one once with `scripts/generate_enc_key.py` and stash it in
prod/.env.

Rotating keys: not handled here (it would require re-encrypting every
stored token). For our scale we just rotate by asking users to
re-connect their Dropbox.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryption:
    def __init__(self, key: bytes | str | None = None):
        key = key or os.getenv("DROPBOX_TOKEN_ENC_KEY")
        if not key:
            raise RuntimeError(
                "DROPBOX_TOKEN_ENC_KEY is not set. Generate one with "
                "`python scripts/generate_enc_key.py` and add it to your "
                "environment."
            )
        if isinstance(key, str):
            key = key.encode()
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "DROPBOX_TOKEN_ENC_KEY must be a 32-byte url-safe base64 "
                "string. Generate one with scripts/generate_enc_key.py."
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            # Most common cause: the encryption key changed. The user
            # needs to re-connect their Dropbox; we shouldn't silently
            # swallow this.
            raise RuntimeError(
                "Could not decrypt stored token. The encryption key may "
                "have rotated; the affected user needs to re-connect "
                "their Dropbox."
            ) from exc


# Module-level singleton, lazily constructed so importing this file
# doesn't require the env var to be set (e.g. during tests that don't
# touch encryption).
_singleton: TokenEncryption | None = None


def get_token_encryption() -> TokenEncryption:
    global _singleton
    if _singleton is None:
        _singleton = TokenEncryption()
    return _singleton

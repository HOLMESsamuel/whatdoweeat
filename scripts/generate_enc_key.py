"""Generate a fresh 32-byte symmetric encryption key for whatdoweeat.

Run once locally; copy the output into prod/.env as DROPBOX_TOKEN_ENC_KEY.
The same key encrypts/decrypts every user's stored Dropbox refresh token.

If you ever rotate the key, every user has to re-connect their Dropbox
(the old encrypted tokens become unreadable). For our scale that's an
acceptable trade-off versus building a key-rotation pipeline.
"""

from cryptography.fernet import Fernet


def main() -> None:
    print(Fernet.generate_key().decode())


if __name__ == "__main__":
    main()

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DropboxCredential(BaseModel):
    """Per-user Dropbox connection.

    `encrypted_refresh_token` is opaque ciphertext (Fernet); decrypting
    it requires the server's DROPBOX_TOKEN_ENC_KEY. We never log or
    return the decrypted form anywhere outside the recipe-fetch path.
    """

    user_id: str
    encrypted_refresh_token: str
    recipes_path: str = "/ideaverse/Recettes/recette-templated"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DropboxStatus(BaseModel):
    """Public-facing connection status. Never contains the token."""

    connected: bool
    recipes_path: Optional[str] = None
    connected_at: Optional[datetime] = None

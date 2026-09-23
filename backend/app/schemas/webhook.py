from pydantic import BaseModel
from typing import Any, Optional

class WebhookPayload(BaseModel):
    """Evolution API webhook payload structure."""
    event: str
    instance: str
    # data can be dict (messages.upsert) or list (contacts.update)
    data: Any = None
    destination: Optional[str] = None
    date_time: Optional[str] = None
    sender: Optional[str] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None
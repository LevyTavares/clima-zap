from pydantic import BaseModel
from typing import Dict, Any

class WebhookPayload(BaseModel):
    event: str
    instance: str
    data: Dict[str, Any] = {} 
     
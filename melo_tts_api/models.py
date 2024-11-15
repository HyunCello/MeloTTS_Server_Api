from pydantic import BaseModel
from typing import Optional

class TTSRequest(BaseModel):
    """Model for incoming TTS generation requests."""
    text: str
    voice_id: str
    sr: int = 22050  # Default sample rate, customizable
    sdp_ratio: Optional[float] = 0.2
    noise_scale: Optional[float] = 0.6
    noise_scale_w: Optional[float] = 0.8
    speed: Optional[float] = 1.0

class TTSResponse(BaseModel):
    """Model for TTS generation responses."""
    audio: str  # Base64 encoded audio
    sample_rate: int
    generation_time: float

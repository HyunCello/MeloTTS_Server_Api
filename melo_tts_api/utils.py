import io
from functools import lru_cache
import torch
import torchaudio
import torchaudio.transforms as T

# Cache for resamplers to avoid recreating them
resampler_cache = {}

def get_resampler(original_sr: int, target_sr: int):
    """
    Retrieve or create a resampler for the given sample rate conversion.
    
    Args:
        original_sr (int): Original sample rate.
        target_sr (int): Target sample rate.
        
    Returns:
        torchaudio.transforms.Resample: Resampler object.
    """
    key = (original_sr, target_sr)
    if key not in resampler_cache:
        resampler_cache[key] = T.Resample(orig_freq=original_sr, new_freq=target_sr, dtype=torch.float32)
    return resampler_cache[key]

@lru_cache(maxsize=2048)
def cache_synthesize(text: str, voice_id: str, sdp_ratio: float, noise_scale: float, noise_scale_w: float, speed: float):
    """
    Cache-enabled synthesis function to avoid redundant computations for identical requests.
    
    Args:
        text (str): Text to synthesize.
        voice_id (str): Speaker identifier.
        sdp_ratio (float): SDP ratio parameter.
        noise_scale (float): Noise scale parameter.
        noise_scale_w (float): Noise scale W parameter.
        speed (float): Speed of speech.
        
    Returns:
        Tuple[numpy.ndarray, int]: Synthesized audio and its sample rate.
    """
    from tts_manager import tts_model  # Avoid circular import
    audio, sr = tts_model.synthesize(
        text,
        voice_id,
        sdp_ratio,
        noise_scale,
        noise_scale_w,
        speed
    )

    print(f"DEBUG: tts_model.synthesize returned {audio, sr}")  # Log the actual return values
    return audio, sr

def audio_to_bytes(audio: torch.Tensor, sr: int) -> bytes:
    """
    Convert audio tensor to WAV bytes.
    
    Args:
        audio (torch.Tensor): Audio tensor.
        sr (int): Sample rate.
        
    Returns:
        bytes: WAV audio bytes.
    """
    buffer = io.BytesIO()
    torchaudio.save(buffer, audio.unsqueeze(0), sr, format="wav")
    return buffer.getvalue()

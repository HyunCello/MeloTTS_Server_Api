import os
from dotenv import load_dotenv
import numpy as np
import torchaudio
from melo.api import TTS
import tempfile
from typing import Tuple

# Load environment variables
load_dotenv()
DEFAULT_SPEED = float(os.getenv("DEFAULT_SPEED", 1.0))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "EN")
DEFAULT_SPEAKER_ID = os.getenv("DEFAULT_SPEAKER_ID", "default")
DEVICE = "auto"  # Automatically use GPU if available


class TTSModel:
    """Singleton class to manage the TTS model and speaker IDs."""
    _instance = None

    def __new__(cls, language: str, device: str):
        if cls._instance is None:
            cls._instance = super(TTSModel, cls).__new__(cls)
            cls._instance.language = language
            cls._instance.device = device
            cls._instance.model = TTS(language=language, device=device)
            cls._instance.speaker_ids = cls._instance.model.hps.data.spk2id
        return cls._instance

    def synthesize(self, text: str, voice_id: str, sdp_ratio: float, noise_scale: float, noise_scale_w: float, speed: float) -> Tuple[np.ndarray, int]:
        """Generate audio from text, returning audio as a 1D or 2D numpy array and sample rate."""
        # Validate the speaker ID
        if voice_id not in self.speaker_ids:
            raise ValueError(f"Invalid speaker ID: {voice_id}")

        # Create a temporary file to save the audio output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            output_path = tmp.name
            # Generate the audio file
            self.model.tts_to_file(
                text,  # Text to synthesize
                self.speaker_ids[voice_id],  # Speaker ID
                output_path,  # Output file path (positional argument)
                speed=speed,
                sdp_ratio=sdp_ratio,
                noise_scale=noise_scale,
                noise_scale_w=noise_scale_w
            )

        # Load the audio data as a tensor and sample rate using torchaudio
        waveform, sample_rate = torchaudio.load(output_path)

        # Squeeze extra dimensions to ensure correct shape
        waveform = waveform.squeeze()  # Remove dimensions with size 1, if any

        # Convert the waveform to a numpy array
        audio_np = waveform.numpy()

        # Return audio as a 1D or 2D numpy array and the actual sample rate
        return audio_np, sample_rate


# Initialize the TTS model
tts_model = TTSModel(language=DEFAULT_LANGUAGE, device=DEVICE)

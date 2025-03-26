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
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "KR")
DEFAULT_SPEAKER_ID = os.getenv("DEFAULT_SPEAKER_ID", "KR")
DEVICE = "auto"  # Automatically use GPU if available

# Check and display GPU usage information
import torch
if torch.cuda.is_available():
    gpu_name = torch.cuda.get_device_name(0)
    gpu_memory_allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)  # Convert to GB
    gpu_memory_reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)  # Convert to GB
    print(f"\n[GPU INFO] Using GPU: {gpu_name}")
    print(f"[GPU INFO] Memory Allocated: {gpu_memory_allocated:.2f} GB")
    print(f"[GPU INFO] Memory Reserved: {gpu_memory_reserved:.2f} GB")
    print(f"[GPU INFO] Device: {DEVICE}\n")
else:
    print("\n[GPU INFO] No GPU available, using CPU for inference\n")

# Available languages:
# - EN: English
# - ES: Spanish
# - FR: French
# - ZH: Chinese (supports mixed Chinese and English)
# - JP: Japanese
# - KR: Korean

class TTSModel:
    """Singleton class to manage the TTS model and speaker IDs."""
    _instance = None
    _models = {}
    _current_language = None

    def __new__(cls, language: str, device: str):
        if cls._instance is None:
            cls._instance = super(TTSModel, cls).__new__(cls)
            cls._instance.device = device
            # Initialize with the requested language
            cls._instance._load_model(language)
        elif language != cls._current_language:
            # If language changed, load the new model
            cls._instance._load_model(language)
        return cls._instance

    def _load_model(self, language: str):
        """Load a specific language model, with memory management."""
        # Update current language
        self.__class__._current_language = language
        
        # If model is already loaded, just set it as current
        if language in self.__class__._models:
            self.language = language
            self.model = self.__class__._models[language]
            self.speaker_ids = self.model.hps.data.spk2id
            return
        
        # Clear memory before loading a new model if we already have models loaded
        if self.__class__._models and hasattr(self, 'model'):
            # Remove reference to current model to help garbage collection
            del self.model
            import gc
            import torch
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # Load the new model
        from melo.api import TTS
        print(f"Loading {language} language model...")
        
        # Check device being used
        import torch
        actual_device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[MODEL INFO] Using device: {actual_device} for {language} model")
        if actual_device == "cuda":
            memory_before = torch.cuda.memory_allocated(0) / (1024 ** 3)
            print(f"[MODEL INFO] GPU Memory before loading: {memory_before:.2f} GB")
        
        model = TTS(language=language, device=self.device)
        
        # Check GPU memory after loading
        if actual_device == "cuda":
            memory_after = torch.cuda.memory_allocated(0) / (1024 ** 3)
            memory_increase = memory_after - memory_before
            print(f"[MODEL INFO] GPU Memory after loading: {memory_after:.2f} GB")
            print(f"[MODEL INFO] GPU Memory increase: {memory_increase:.2f} GB")
        
        # Store the model
        self.__class__._models[language] = model
        self.language = language
        self.model = model
        self.speaker_ids = model.hps.data.spk2id
        print(f"Loaded {language} language model with {len(self.speaker_ids)} speakers")

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

        # Clean up the temporary file
        try:
            os.unlink(output_path)
        except:
            pass

        # Return audio as a 1D or 2D numpy array and the actual sample rate
        return audio_np, sample_rate
        
    def close(self):
        """Clean up resources and free memory when shutting down."""
        try:
            # Remove references to all models
            for lang, model in self.__class__._models.items():
                print(f"Cleaning up {lang} language model...")
                del model
            
            # Clear the models dictionary
            self.__class__._models.clear()
            
            # Force garbage collection
            import gc
            import torch
            gc.collect()
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Ensure all CUDA operations are completed
                print("CUDA memory cache cleared")
                
            print("All TTS models have been unloaded and memory has been freed")
        except Exception as e:
            print(f"Error during cleanup: {e}")


# Initialize the TTS model
tts_model = TTSModel(language=DEFAULT_LANGUAGE, device=DEVICE)

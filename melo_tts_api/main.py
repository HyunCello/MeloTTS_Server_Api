import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import torch
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from tts_manager import tts_model, TTSModel
from models import TTSRequest
from utils import cache_synthesize, get_resampler, audio_to_bytes

# Load environment variables
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
WORKERS = int(os.getenv("WORKERS", 1))  # Reduce default workers to 1 to prevent memory issues
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", 2048))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "KR")

# Initialize FastAPI app
app = FastAPI(
    title="MeloTTS API",
    description="API for text-to-speech synthesis using MeloTTS",
    version="1.0.0",
)

# Initialize ThreadPoolExecutor for async operations
executor = ThreadPoolExecutor(max_workers=WORKERS)

# Startup event to preload the model and check GPU usage
@app.on_event("startup")
def startup_event():
    """Handle startup events to preload models and check GPU usage."""
    print("\nStarting MeloTTS API server...")
    print(f"Default language: {DEFAULT_LANGUAGE}")
    
    # Check GPU status
    import torch
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"\n[STARTUP] Using GPU: {gpu_name}")
        print(f"[STARTUP] CUDA Version: {torch.version.cuda}")
        print(f"[STARTUP] PyTorch CUDA: {torch.cuda.is_available()}")
        
        # Get initial memory usage
        init_memory = torch.cuda.memory_allocated(0) / (1024 ** 3)  # Convert to GB
        print(f"[STARTUP] Initial GPU Memory: {init_memory:.2f} GB")
    else:
        print("\n[STARTUP] No GPU available, using CPU for inference")
    
    # Preload the model to ensure it's ready before the first request
    print("\n[STARTUP] Preloading TTS model...")
    try:
        # Force model loading by accessing the model and performing a small synthesis
        # This ensures the model is fully loaded and ready for use
        speakers = tts_model.speaker_ids
        print(f"[STARTUP] Model initialized with {len(speakers)} speakers")
        
        # Perform a small synthesis to ensure the model is fully loaded
        print("[STARTUP] Performing test synthesis to ensure model is fully loaded...")
        test_text = "안녕하세요"  # Simple Korean greeting
        test_speaker = list(speakers.keys())[0]  # Get the first available speaker
        
        # Synthesize a short text to ensure the model is fully loaded
        _ = tts_model.synthesize(
            text=test_text,
            voice_id=test_speaker,
            sdp_ratio=0.2,
            noise_scale=0.6,
            noise_scale_w=0.8,
            speed=1.0
        )
        
        print(f"[STARTUP] Model fully preloaded and ready for use with {len(speakers)} speakers")
        
        # Check memory usage after model loading
        if torch.cuda.is_available():
            post_memory = torch.cuda.memory_allocated(0) / (1024 ** 3)  # Convert to GB
            memory_increase = post_memory - init_memory
            print(f"[STARTUP] GPU Memory after model loading: {post_memory:.2f} GB")
            print(f"[STARTUP] GPU Memory increase: {memory_increase:.2f} GB\n")
    except Exception as e:
        print(f"[STARTUP] Error preloading model: {e}\n")
        import traceback
        traceback.print_exc()

@app.get("/speakers")
async def get_speaker_ids():
    return {"available_speakers": list(tts_model.speaker_ids.keys())}

@app.post("/language/switch")
async def switch_language(language_request: dict):
    """Switch the TTS model to a different language.
    
    Args:
        language_request (dict): Request with language field
        
    Returns:
        dict: Status message and available speakers for the new language
    """
    # Extract language from request
    if not isinstance(language_request, dict) or "language" not in language_request:
        language = language_request  # Try to use the raw input if it's a string
    else:
        language = language_request["language"]
    
    # Validate language
    valid_languages = ["EN", "ES", "FR", "ZH", "JP", "KR"]
    if language not in valid_languages:
        raise HTTPException(status_code=400, detail=f"Invalid language. Must be one of {valid_languages}")
    
    # Initialize new TTS model with the selected language
    global tts_model
    tts_model = TTSModel(language=language, device=DEVICE)
    
    return {
        "status": f"Switched to {language} language model",
        "available_speakers": list(tts_model.speaker_ids.keys())
    }

@app.post("/tts/generate", response_description="Generate and stream TTS audio")
async def generate_tts_audio(request: TTSRequest):
    """
    Generate TTS audio based on the provided request parameters and stream it to the client.
    
    Args:
        request (TTSRequest): The TTS generation request.
        
    Returns:
        StreamingResponse: Streamed WAV audio data.
    """
    # Validate speaker ID
    if request.voice_id not in tts_model.speaker_ids:
        raise HTTPException(status_code=400, detail="Invalid speaker ID")

    start_time = time.time()
    try:
        # Asynchronously perform synthesis to prevent blocking the event loop
        audio, sr = await asyncio.get_event_loop().run_in_executor(
            executor,
            cache_synthesize,
            request.text,
            request.voice_id,
            request.sdp_ratio,
            request.noise_scale,
            request.noise_scale_w,
            request.speed
        )

        # Resample if necessary
        if sr != request.sr:
            resampler = get_resampler(sr, request.sr)
            audio_tensor = torch.from_numpy(audio)
            audio_tensor = resampler(audio_tensor)
            audio = audio_tensor.cpu().numpy()
            sr = request.sr

        # Convert audio to bytes
        audio_bytes = audio_to_bytes(torch.from_numpy(audio), sr)

        generation_time = time.time() - start_time

        async def audio_generator():
            """Generator to stream audio in chunks."""
            chunk_size = 1024  # 1KB chunks
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i:i+chunk_size]
                await asyncio.sleep(0)  # Yield control to event loop

        headers = {"generation_time_seconds": f"{generation_time:.3f}"}
        return StreamingResponse(audio_generator(), media_type="audio/wav", headers=headers)

    except Exception as e:
        # Handle any unexpected errors gracefully
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@app.on_event("shutdown")
def shutdown_event():
    """Handle shutdown events to clean up resources."""
    print("\nShutting down server and cleaning up resources...")
    try:
        # Try to close the TTS model if the close method exists
        if hasattr(tts_model, 'close'):
            tts_model.close()  # Clean up TTS model resources
        else:
            print("Warning: tts_model does not have a close method. Using manual cleanup.")
            # Manual cleanup as fallback
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("CUDA memory cache cleared manually")
    except Exception as e:
        print(f"Error during TTS model cleanup: {e}")
    
    # Always shut down the executor
    try:
        executor.shutdown()
        print("Executor shutdown complete")
    except Exception as e:
        print(f"Error during executor shutdown: {e}")
        
    print("Server shutdown complete\n")

if __name__ == "__main__":
    # Run the Uvicorn server with optimized settings
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        workers=WORKERS,
        reload=False,  # Disable reload for production
        timeout_keep_alive=300,
        log_level="info",
        limit_concurrency=5,  # Limit concurrent requests
        timeout_graceful_shutdown=30  # Give more time for graceful shutdown
    )

# **MeloTTS API Server**

MeloTTS API Server provides an interface to generate high-quality text-to-speech (TTS) audio using the MeloTTS model. The server exposes a RESTful API, allowing users to convert text into speech with support for all base configurations such as speaker voice, speed, and sampling rate.

---

## **Features**

- Streamlined REST API for TTS conversion.
- Support for multiple speakers and languages.
- Adjustable parameters for speech speed, noise, and sampling rate.
- Real-time processing for fast and efficient audio generation.
- Easy integration with client applications.

---

## **Installation**

### **Requirements**
- Python 3.9 or higher
- Required libraries (managed via `requirements.txt`)
- Dependencies for audio processing:
  - `libsndfile1` (Linux/Unix)
  - FFmpeg (if using `pydub` for audio manipulation)
- Docker (optional, for containerized deployment)

### **Steps**
1. Clone the repository:
   ```bash
   git clone https://github.com/nyedr/MeloTTS_Server_Api.git
   cd melotts-api-server
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download necessary linguistic resources and pre-trained models:
   ```bash
   python -m unidic download
   python melo/init_downloads.py
   ```

4. Run the server:
   ```bash
   python main.py
   ```

5. The server will start on `http://127.0.0.1:8000` by default.

---

## **Usage**

### **Endpoints**

#### 1. `/tts/generate` (POST)

Generates a speech audio file from the given text.

- **URL**: `http://127.0.0.1:8000/tts/generate`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "text": "Your text to convert to speech.",
    "voice_id": "EN-US",  // Available speaker ID
    "sr": 22050,          // Sampling rate (default: 22050)
    "speed": 1.0          // Speech speed (default: 1.0)
  }
  ```
- **Response**: Streams the audio file in WAV format.

#### 2. `/speakers` (GET)

Fetches the list of available speaker IDs.

- **URL**: `http://127.0.0.1:8000/speakers`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "available_speakers": ["EN-US", "EN-BR", "EN-AU", "EN-INDIA", "EN-Default"]
  }
  ```

---

## **Examples**

### **Generating Speech**
#### **Using `curl`**
```bash
curl -X POST "http://127.0.0.1:8000/tts/generate" \
    -H "Content-Type: application/json" \
    -d '{
          "text": "Hello, this is a test of the MeloTTS API.",
          "voice_id": "EN-US",
          "sr": 22050,
          "speed": 1.0
        }' --output output.wav
```

#### **Using Python**
```python
import requests

url = "http://127.0.0.1:8000/tts/generate"
data = {
    "text": "Hello, this is a test of the MeloTTS API.",
    "voice_id": "EN-US",
    "sr": 22050,
    "speed": 1.0
}
response = requests.post(url, json=data, stream=True)

with open("output.wav", "wb") as f:
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            f.write(chunk)
```

---

## **Docker Deployment**

### **Building the Image**
```bash
docker build -t melotts-api-server .
```

### **Running the Container**
```bash
docker run -p 8000:8000 melotts-api-server
```

---

## **Configuration**

### **Environment Variables**
You can configure the server behavior using the following environment variables:

| Variable          | Default Value  | Description                         |
|--------------------|----------------|-------------------------------------|
| `HOST`            | `0.0.0.0`      | Server host address.                |
| `PORT`            | `8000`         | Server port.                        |
| `DEFAULT_SPEED`   | `1.0`          | Default speech speed.               |
| `DEFAULT_LANGUAGE`| `EN`           | Default language for the TTS model. |
| `DEFAULT_SPEAKER_ID` | `EN-US`      | Default speaker voice ID.           |

---

## **Contributing**

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

1. Clone the repository:
   ```bash
   git clone https://github.com/nyedr/MeloTTS_Server_Api.git
   ```

2. Create a feature branch:
   ```bash
   git checkout -b feature-name
   ```

3. Commit your changes and push:
   ```bash
   git add .
   git commit -m "Add new feature"
   git push origin feature-name
   ```

4. Open a pull request on GitHub.

---

Fork of [MeloTTS](https://github.com/myshell-ai/MeloTTS)

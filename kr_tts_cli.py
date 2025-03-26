#!/usr/bin/env python3

import requests
import io
import sys
import os
import time

# 오디오 재생을 위한 라이브러리 - 설치 필요: pip install sounddevice soundfile
try:
    import sounddevice as sd
    import soundfile as sf
    CAN_PLAY_AUDIO = True
except ImportError:
    print("오디오 재생을 위해 sounddevice와 soundfile 패키지를 설치하세요:")
    print("pip install sounddevice soundfile")
    CAN_PLAY_AUDIO = False

# API 서버 URL
BASE_URL = "http://localhost:8000"

# 저장 디렉토리 생성
OUTPUT_DIR = "tts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_timestamp():
    """고유한 파일명을 위한 타임스탬프 생성"""
    return time.strftime("%Y%m%d_%H%M%S")

def get_speakers():
    """사용 가능한 화자 ID 목록 가져오기"""
    try:
        response = requests.get(f"{BASE_URL}/speakers")
        if response.status_code == 200:
            return response.json()["available_speakers"]
        else:
            print(f"화자 목록을 가져오는 중 오류 발생: {response.status_code}")
            return ["KR"]  # 기본값 반환
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return ["KR"]  # 기본값 반환

def generate_and_play_tts(text, voice_id="KR", speed=1.0):
    """TTS 생성 및 재생"""
    if not text.strip():
        print("텍스트가 비어있습니다. 다시 시도하세요.")
        return
    
    print(f"\n'{text}' 음성 생성 중...")
    
    try:
        # TTS 요청 보내기
        payload = {
            "text": text,
            "voice_id": voice_id,
            "speed": speed
        }
        
        response = requests.post(f"{BASE_URL}/tts/generate", json=payload)
        
        if response.status_code == 200:
            # 파일명 생성 및 저장
            filename = f"{OUTPUT_DIR}/kr_tts_{get_timestamp()}.wav"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"오디오가 {filename}에 저장되었습니다.")
            
            # 오디오 재생
            if CAN_PLAY_AUDIO:
                print("재생 중...")
                data, samplerate = sf.read(io.BytesIO(response.content))
                sd.play(data, samplerate)
                sd.wait()  # 재생이 끝날 때까지 대기
                print("재생 완료")
            else:
                print("오디오 재생을 위해 sounddevice와 soundfile 패키지를 설치하세요.")
        else:
            print(f"TTS 생성 중 오류 발생: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")

def interactive_mode():
    """대화형 모드: 사용자가 계속해서 텍스트 입력 가능"""
    print("\n한국어 TTS 대화형 모드 시작 (종료하려면 'exit' 또는 'quit' 입력)")
    print("--------------------------------------------------------------")
    
    # 사용 가능한 화자 확인
    speakers = get_speakers()
    print(f"사용 가능한 화자: {', '.join(speakers)}")
    
    # 기본 화자 설정
    voice_id = "KR" if "KR" in speakers else speakers[0]
    
    while True:
        # 사용자 입력 받기
        text = input("\n한국어 텍스트 입력 (종료: exit/quit): ")
        
        # 종료 조건 확인
        if text.lower() in ["exit", "quit"]:
            print("프로그램을 종료합니다.")
            break
        
        # TTS 생성 및 재생
        generate_and_play_tts(text, voice_id)

def main():
    # 명령줄 인수 확인
    if len(sys.argv) > 1:
        # 명령줄에서 직접 텍스트 입력 시
        text = " ".join(sys.argv[1:])
        generate_and_play_tts(text)
    else:
        # 대화형 모드 실행
        interactive_mode()

if __name__ == "__main__":
    main()

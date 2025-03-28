#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import time
import base64
import requests
import streamlit as st
import numpy as np
from collections import deque

# 오디오 재생을 위한 라이브러리
try:
    import soundfile as sf
    import sounddevice as sd
    CAN_PROCESS_AUDIO = True
except ImportError:
    CAN_PROCESS_AUDIO = False

# API 서버 URL
BASE_URL = "http://192.168.10.4:8000"

# 저장 디렉토리 생성
OUTPUT_DIR = "tts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 오디오 장치 목록 가져오기 함수
def get_audio_devices():
    if not CAN_PROCESS_AUDIO:
        return []
    try:
        devices = sd.query_devices()
        output_devices = []
        for i, device in enumerate(devices):
            # 출력 채널이 있는 장치만 선택
            if device['max_output_channels'] > 0:
                name = f"{i}: {device['name']}"
                output_devices.append((i, name))
        return output_devices
    except Exception as e:
        st.warning(f"오디오 장치 목록을 가져오는 중 오류 발생: {e}")
        return []

# 페이지 설정
st.set_page_config(
    page_title="한국어 TTS 생성기",
    page_icon="🎤",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 제목
st.markdown("""
<style>
    .stAudio > audio {
        width: 100%;
    }
    .stAudio {
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .stForm [data-testid="stForm"] {
        border: none;
        padding-top: 0;
    }
    .stTextArea textarea {
        font-size: 16px;
    }
</style>
""", unsafe_allow_html=True)

st.title("한국어 TTS 생성기 🎤")
st.markdown("""
텍스트를 입력하고 음성을 생성해보세요. 한글 입력이 자유롭게 되는 웹 기반 인터페이스입니다.
엔터 키를 누르면 바로 음성이 생성됩니다.
""")

# 세션 초기화
if 'generated_audio' not in st.session_state:
    st.session_state.generated_audio = None
    st.session_state.audio_file_path = None

# 이전 기록을 위한 세션 상태 초기화
if 'history' not in st.session_state:
    st.session_state.history = deque(maxlen=5)  # 최대 5개 기록 유지

# 자동 재생을 위한 세션 상태 초기화
if 'auto_play' not in st.session_state:
    st.session_state.auto_play = False

# 서버측 재생을 위한 세션 상태 초기화
if 'server_side_playback' not in st.session_state:
    st.session_state.server_side_playback = True

# 화자 목록 가져오기
def fetch_speakers():
    try:
        response = requests.get(f"{BASE_URL}/speakers")
        if response.status_code == 200:
            return response.json()["available_speakers"]
        else:
            st.warning(f"화자 목록을 가져오는 중 오류 발생: {response.status_code}")
            return ["KR"]
    except Exception as e:
        st.warning(f"화자 목록을 가져오는 중 오류 발생: {e}")
        return ["KR"]

# 서버측에서 오디오 재생 함수
def play_audio_on_server(audio_data):
    if not CAN_PROCESS_AUDIO:
        st.warning("서버에 오디오 재생 라이브러리가 설치되어 있지 않습니다. soundfile과 sounddevice를 설치해주세요.")
        return False
    
    try:
        with io.BytesIO(audio_data) as audio_io:
            data, samplerate = sf.read(audio_io)
            # 선택된 오디오 장치로 재생
            device_idx = st.session_state.get('selected_audio_device', None)
            sd.play(data, samplerate, device=device_idx)
            # 재생 완료 대기
            sd.wait()
        return True
    except Exception as e:
        st.warning(f"서버측 오디오 재생 중 오류 발생: {e}")
        return False

# TTS 생성 함수
def generate_tts(text, voice_id, speed):
    if not text or text == "여기에 한국어 텍스트를 입력하세요...":
        st.warning("텍스트를 입력해주세요.")
        return None, None

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
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_path = f"{OUTPUT_DIR}/kr_tts_{timestamp}.wav"

            with open(file_path, "wb") as f:
                f.write(response.content)

            # 기록에 추가
            st.session_state.history.appendleft({
                "text": text,
                "voice_id": voice_id,
                "speed": speed,
                "timestamp": timestamp,
                "file_path": file_path,
                "audio_data": response.content
            })

            # 서버측 재생이 활성화되어 있고 자동 재생이 활성화된 경우 서버에서 재생
            if st.session_state.server_side_playback:
                play_audio_on_server(response.content)

            return response.content, file_path
        else:
            st.error(f"TTS 생성 중 오류 발생: {response.status_code}\n{response.text}")
            return None, None
    except Exception as e:
        st.error(f"API 요청 중 오류 발생: {e}")
        return None, None

# 화자 목록
speakers = fetch_speakers()
default_speaker = "KR" if "KR" in speakers else (speakers[0] if speakers else "KR")

# 사이드바
with st.sidebar:
    st.header("설정")
    selected_speaker = st.selectbox("화자 선택:", speakers, index=speakers.index(default_speaker) if default_speaker in speakers else 0)
    speed = st.slider("속도:", 0.5, 1.5, 1.0, 0.1)
    
    # 서버측 재생 옵션
    st.session_state.server_side_playback = st.checkbox("서버측 오디오 재생", value=st.session_state.server_side_playback, 
                                                      help="체크하면 웹브라우저가 아닌 서버에서 오디오가 재생됩니다.")
    
    # 서버측 재생이 활성화된 경우 오디오 장치 선택 옵션 표시
    if st.session_state.server_side_playback and CAN_PROCESS_AUDIO:
        st.subheader("오디오 장치 설정")
        # 오디오 장치 목록 가져오기
        audio_devices = get_audio_devices()
        
        if audio_devices:
            # 장치 ID와 이름을 분리하여 selectbox에 표시
            device_names = [name for _, name in audio_devices]
            device_indices = [idx for idx, _ in audio_devices]
            
            # 기본 장치 인덱스 (세션 상태에 저장된 값 또는 기본값)
            default_device_idx = 0
            if 'selected_audio_device' in st.session_state:
                try:
                    default_device_idx = device_indices.index(st.session_state.selected_audio_device)
                except ValueError:
                    default_device_idx = 0
            
            # 장치 선택 드롭다운
            selected_device_name = st.selectbox(
                "오디오 출력 장치:", 
                device_names,
                index=default_device_idx,
                help="오디오를 재생할 출력 장치를 선택하세요."
            )
            
            # 선택된 장치의 인덱스를 세션 상태에 저장
            selected_idx = device_indices[device_names.index(selected_device_name)]
            st.session_state.selected_audio_device = selected_idx
            
            # 현재 선택된 장치 정보 표시
            st.info(f"선택된 장치: {selected_device_name}")
            
            # 테스트 재생 버튼
            if st.button("테스트 소리 재생"):
                try:
                    # 간단한 테스트 소리 생성 (1초 길이의 440Hz 사인파)
                    sample_rate = 44100
                    t = np.linspace(0, 1, sample_rate, False)
                    test_tone = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440Hz 사인파, 볼륨 0.3
                    sd.play(test_tone, sample_rate, device=selected_idx)
                    st.success("테스트 소리를 재생 중입니다...")
                except Exception as e:
                    st.error(f"테스트 소리 재생 중 오류 발생: {e}")
        else:
            st.warning("사용 가능한 오디오 출력 장치가 없습니다.")
    
    # 서버측 재생이 활성화된 경우 라이브러리 설치 여부 확인
    if st.session_state.server_side_playback and not CAN_PROCESS_AUDIO:
        st.warning("서버에 오디오 재생 라이브러리가 설치되어 있지 않습니다.\n`pip install soundfile sounddevice`를 실행하여 설치해주세요.")

# 텍스트 입력 영역 (엔터 키 처리를 위한 form 사용)
with st.form(key="tts_form", clear_on_submit=False):
    text_input = st.text_area("텍스트 입력:", "여기에 한국어 텍스트를 입력하세요...", height=150)
    submit_button = st.form_submit_button(label="음성 생성", type="primary")

# 폼 제출 처리
if submit_button:
    with st.spinner("음성 생성 중..."):
        audio_data, file_path = generate_tts(text_input, selected_speaker, speed)

        if audio_data:
            # 오디오 데이터 저장
            st.session_state.generated_audio = audio_data
            st.session_state.audio_file_path = file_path

            # 성공 메시지 표시
            st.success(f"음성 생성 완료: {file_path}")
            
            # 서버측 재생이 비활성화된 경우에만 브라우저에서 오디오 컴포넌트 표시
            if not st.session_state.server_side_playback:
                st.audio(audio_data, format="audio/wav", start_time=0)
                
                # JavaScript를 사용하여 자동 재생 (서버측 재생이 비활성화된 경우에만)
                st.markdown(
                    """
                    <script>
                        document.addEventListener('DOMContentLoaded', (event) => {
                            const audioElements = document.getElementsByTagName('audio');
                            if (audioElements.length > 0) {
                                audioElements[0].play();
                            }
                        });
                    </script>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # 서버측 재생이 활성화된 경우 재생 버튼 제공
                if st.button("서버에서 다시 재생"):
                    play_audio_on_server(audio_data)

            # 다운로드 버튼 제공
            with open(file_path, "rb") as file:
                st.download_button(
                    label="음성 파일 다운로드",
                    data=file,
                    file_name=os.path.basename(file_path),
                    mime="audio/wav"
                )

# 이전 기록 표시
if st.session_state.history:
    st.subheader("최근 생성 기록")
    
    for i, item in enumerate(st.session_state.history):
        with st.expander(f"{item['timestamp']}: {item['text'][:30]}..."):
            st.write(f"**텍스트:** {item['text']}")
            st.write(f"**화자:** {item['voice_id']}, **속도:** {item['speed']}")
            
            col1, col2 = st.columns(2)
            
            # 서버측 재생이 활성화된 경우 서버에서 재생
            if st.session_state.server_side_playback:
                if col1.button(f"서버에서 재생 #{i}"):
                    play_audio_on_server(item['audio_data'])
            else:
                # 브라우저에서 재생
                st.audio(item['audio_data'], format="audio/wav")
            
            # 다운로드 버튼
            if os.path.exists(item['file_path']):
                with open(item['file_path'], "rb") as file:
                    col2.download_button(
                        label=f"다운로드 #{i}",
                        data=file,
                        file_name=os.path.basename(item['file_path']),
                        mime="audio/wav"
                    )

# 라이브러리 설치 안내
if not CAN_PROCESS_AUDIO and st.session_state.server_side_playback:
    st.warning("""
    서버측 오디오 재생을 위해 다음 라이브러리를 설치해주세요:
    ```
    pip install soundfile sounddevice
    ```
    설치 후 애플리케이션을 재시작해주세요.
    """)

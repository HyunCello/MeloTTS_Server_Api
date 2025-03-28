#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import io
import time
import requests
import shutil
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

# 오디오 재생을 위한 라이브러리
try:
    import sounddevice as sd
    import soundfile as sf
    CAN_PLAY_AUDIO = True
except ImportError:
    CAN_PLAY_AUDIO = False

# API 서버 URL
BASE_URL = "http://192.168.10.4:8000"

# 저장 디렉토리 생성
OUTPUT_DIR = "tts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class TTSWorker(threading.Thread):
    """백그라운드에서 TTS 요청을 처리하는 워커 스레드"""
    
    def __init__(self, text, voice_id, speed, callback, progress_callback):
        super().__init__()
        self.text = text
        self.voice_id = voice_id
        self.speed = speed
        self.callback = callback
        self.progress_callback = progress_callback
        self.filename = None
        self.audio_data = None
        self.sample_rate = None
        self.daemon = True  # 메인 스레드가 종료되면 같이 종료
    
    def run(self):
        try:
            self.progress_callback(10)
            
            # TTS 요청 보내기
            payload = {
                "text": self.text,
                "voice_id": self.voice_id,
                "speed": self.speed
            }
            
            self.progress_callback(30)
            response = requests.post(f"{BASE_URL}/tts/generate", json=payload)
            
            self.progress_callback(70)
            
            if response.status_code == 200:
                # 파일명 생성 및 저장
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                self.filename = f"{OUTPUT_DIR}/kr_tts_{timestamp}.wav"
                
                with open(self.filename, "wb") as f:
                    f.write(response.content)
                
                # 오디오 데이터 로드 (재생용)
                if CAN_PLAY_AUDIO:
                    self.audio_data, self.sample_rate = sf.read(io.BytesIO(response.content))
                
                self.progress_callback(100)
                self.callback(True, self.filename, self.audio_data, self.sample_rate)
            else:
                error_msg = f"TTS 생성 중 오류 발생: {response.status_code}\n{response.text}"
                self.callback(False, error_msg, None, None)
        except Exception as e:
            self.callback(False, f"API 요청 중 오류 발생: {e}", None, None)


class KoreanTTSApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 테마 설정
        ctk.set_appearance_mode("System")  # 시스템 테마 사용
        ctk.set_default_color_theme("blue")
        
        self.title('한국어 TTS 생성기')
        self.geometry('650x500')
        
        self.speakers = []
        self.current_audio = None
        self.current_sample_rate = None
        self.worker = None
        
        self.create_widgets()
        
        # 시작 시 화자 목록 가져오기
        self.fetch_speakers()
    
    def create_widgets(self):
        # 메인 프레임
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 제목 레이블
        title_label = ctk.CTkLabel(
            self.main_frame, 
            text='한국어 TTS 생성기', 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=10)
        
        # 텍스트 입력 영역
        text_label = ctk.CTkLabel(self.main_frame, text='텍스트 입력:')
        text_label.pack(anchor=tk.W, pady=(10, 5))
        
        self.text_edit = ctk.CTkTextbox(self.main_frame, height=150, font=ctk.CTkFont(size=12))
        self.text_edit.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.text_edit.insert("1.0", "여기에 한국어 텍스트를 입력하세요...")
        
        # 설정 프레임
        settings_frame = ctk.CTkFrame(self.main_frame)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # 화자 선택
        speaker_label = ctk.CTkLabel(settings_frame, text='화자:')
        speaker_label.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        
        self.speaker_var = tk.StringVar()
        self.speaker_combo = ctk.CTkOptionMenu(
            settings_frame, 
            variable=self.speaker_var,
            values=[]
        )
        self.speaker_combo.grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)
        
        # 속도 조절
        speed_label = ctk.CTkLabel(settings_frame, text='속도:')
        speed_label.grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        
        speed_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        speed_frame.grid(row=1, column=1, padx=10, pady=10, sticky=tk.W)
        
        self.speed_slider = ctk.CTkSlider(
            speed_frame, 
            from_=50, 
            to=150, 
            number_of_steps=100,
            command=self.update_speed_label
        )
        self.speed_slider.pack(side=tk.LEFT, padx=(0, 10))
        self.speed_slider.set(100)
        
        self.speed_value_label = ctk.CTkLabel(speed_frame, text='1.0')
        self.speed_value_label.pack(side=tk.LEFT)
        
        # 진행 상태 표시줄
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.pack(fill=tk.X, pady=10)
        self.progress_bar.set(0)
        
        # 버튼 프레임
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill=tk.X, pady=10)
        
        # 버튼들
        self.generate_button = ctk.CTkButton(
            button_frame, 
            text='음성 생성', 
            command=self.generate_tts
        )
        self.generate_button.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
        
        self.play_button = ctk.CTkButton(
            button_frame, 
            text='재생', 
            command=self.play_audio,
            state=tk.DISABLED
        )
        self.play_button.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
        
        self.save_button = ctk.CTkButton(
            button_frame, 
            text='다른 이름으로 저장', 
            command=self.save_audio,
            state=tk.DISABLED
        )
        self.save_button.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
        
        # 상태 표시줄
        self.status_label = ctk.CTkLabel(self.main_frame, text='준비됨')
        self.status_label.pack(anchor=tk.W, pady=10)
        
        # 오디오 재생 불가능한 경우 알림
        if not CAN_PLAY_AUDIO:
            messagebox.showwarning(
                '경고', 
                '오디오 재생을 위한 라이브러리가 설치되지 않았습니다.\n'
                '오디오 재생 기능을 사용하려면 다음 패키지를 설치하세요:\n'
                'pip install sounddevice soundfile'
            )
    
    def update_speed_label(self, value):
        speed_value = float(value) / 100.0
        self.speed_value_label.configure(text=f'{speed_value:.1f}')
    
    def fetch_speakers(self):
        """사용 가능한 화자 목록 가져오기"""
        try:
            response = requests.get(f"{BASE_URL}/speakers")
            if response.status_code == 200:
                self.speakers = response.json()["available_speakers"]
                self.speaker_combo.configure(values=self.speakers)
                
                # KR 화자가 있으면 기본 선택
                if "KR" in self.speakers:
                    self.speaker_var.set("KR")
                elif self.speakers:
                    self.speaker_var.set(self.speakers[0])
                
                self.status_label.configure(text=f"화자 목록을 가져왔습니다. {len(self.speakers)}개의 화자가 있습니다.")
            else:
                self.status_label.configure(text=f"화자 목록을 가져오는 중 오류 발생: {response.status_code}")
                # 기본값 설정
                self.speakers = ["KR"]
                self.speaker_combo.configure(values=self.speakers)
                self.speaker_var.set("KR")
        except Exception as e:
            self.status_label.configure(text=f"화자 목록을 가져오는 중 오류 발생: {e}")
            # 기본값 설정
            self.speakers = ["KR"]
            self.speaker_combo.configure(values=self.speakers)
            self.speaker_var.set("KR")
    
    def generate_tts(self):
        """TTS 생성 요청 보내기"""
        # 텍스트 가져오기
        text = self.text_edit.get("1.0", tk.END).strip()
        if not text or text == "여기에 한국어 텍스트를 입력하세요...":
            messagebox.showwarning("경고", "텍스트를 입력해주세요.")
            return
        
        # 화자 및 속도 설정
        voice_id = self.speaker_var.get()
        speed = self.speed_slider.get() / 100.0
        
        # UI 상태 업데이트
        self.generate_button.configure(state=tk.DISABLED)
        self.play_button.configure(state=tk.DISABLED)
        self.save_button.configure(state=tk.DISABLED)
        self.status_label.configure(text="TTS 생성 중...")
        
        # 워커 스레드 시작
        self.worker = TTSWorker(
            text, 
            voice_id, 
            speed, 
            self.on_tts_complete, 
            self.update_progress
        )
        self.worker.start()
    
    def update_progress(self, value):
        """진행 상태 업데이트"""
        self.progress_bar.set(value / 100.0)
        self.update_idletasks()
    
    def on_tts_complete(self, success, result, audio_data=None, sample_rate=None):
        """TTS 생성 완료 콜백"""
        if success:
            self.current_audio = audio_data
            self.current_sample_rate = sample_rate
            self.status_label.configure(text=f"TTS 생성 완료: {result}")
            self.generate_button.configure(state=tk.NORMAL)
            
            # 오디오 재생 및 저장 버튼 활성화
            if CAN_PLAY_AUDIO and audio_data is not None:
                self.play_button.configure(state=tk.NORMAL)
            
            self.save_button.configure(state=tk.NORMAL)
        else:
            self.status_label.configure(text=result)
            self.generate_button.configure(state=tk.NORMAL)
    
    def play_audio(self):
        """생성된 오디오 재생"""
        if CAN_PLAY_AUDIO and self.current_audio is not None:
            self.status_label.configure(text="오디오 재생 중...")
            sd.play(self.current_audio, self.current_sample_rate)
            
            # 재생이 끝나면 상태 업데이트
            def on_playback_done():
                sd.wait()  # 재생이 끝날 때까지 대기
                self.status_label.configure(text="재생 완료")
            
            threading.Thread(target=on_playback_done, daemon=True).start()
    
    def save_audio(self):
        """오디오 파일 다른 이름으로 저장"""
        if self.worker and self.worker.filename:
            file_path = filedialog.asksaveasfilename(
                title='다른 이름으로 저장',
                defaultextension='.wav',
                filetypes=[('WAV 파일', '*.wav'), ('모든 파일', '*.*')]
            )
            
            if file_path:
                # 원본 파일을 새 위치로 복사
                shutil.copy2(self.worker.filename, file_path)
                self.status_label.configure(text=f"파일이 저장되었습니다: {file_path}")


def main():
    # 한글 입력을 위한 환경 변수 설정
    os.environ['LANG'] = 'ko_KR.UTF-8'
    os.environ['LC_ALL'] = 'ko_KR.UTF-8'
    
    app = KoreanTTSApp()
    app.mainloop()


if __name__ == "__main__":
    main()

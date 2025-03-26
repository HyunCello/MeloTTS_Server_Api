#!/usr/bin/env python3

import sys
import os
import io
import time
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QComboBox, QSlider, QFileDialog, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QFont, QIcon, QKeyEvent

# 오디오 재생을 위한 라이브러리
try:
    import sounddevice as sd
    import soundfile as sf
    CAN_PLAY_AUDIO = True
except ImportError:
    CAN_PLAY_AUDIO = False

# API 서버 URL
BASE_URL = "http://localhost:8000"

# 저장 디렉토리 생성
OUTPUT_DIR = "tts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class TTSWorker(QThread):
    """백그라운드에서 TTS 요청을 처리하는 워커 스레드"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)
    
    def __init__(self, text, voice_id, speed):
        super().__init__()
        self.text = text
        self.voice_id = voice_id
        self.speed = speed
        self.filename = None
        self.audio_data = None
        self.sample_rate = None
    
    def run(self):
        try:
            self.progress.emit(10)
            
            # TTS 요청 보내기
            payload = {
                "text": self.text,
                "voice_id": self.voice_id,
                "speed": self.speed
            }
            
            self.progress.emit(30)
            response = requests.post(f"{BASE_URL}/tts/generate", json=payload)
            
            self.progress.emit(70)
            
            if response.status_code == 200:
                # 파일명 생성 및 저장
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                self.filename = f"{OUTPUT_DIR}/kr_tts_{timestamp}.wav"
                
                with open(self.filename, "wb") as f:
                    f.write(response.content)
                
                # 오디오 데이터 로드 (재생용)
                if CAN_PLAY_AUDIO:
                    self.audio_data, self.sample_rate = sf.read(io.BytesIO(response.content))
                
                self.progress.emit(100)
                self.finished.emit(True, self.filename)
            else:
                error_msg = f"TTS 생성 중 오류 발생: {response.status_code}\n{response.text}"
                self.finished.emit(False, error_msg)
        except Exception as e:
            self.finished.emit(False, f"API 요청 중 오류 발생: {e}")


class KoreanTTSApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.speakers = []
        self.current_audio = None
        self.current_sample_rate = None
        self.worker = None
        
        # 시작 시 화자 목록 가져오기
        self.fetch_speakers()
    
    def initUI(self):
        self.setWindowTitle('한국어 TTS 생성기')
        self.setGeometry(100, 100, 600, 400)
        
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 제목 레이블
        title_label = QLabel('한국어 TTS 생성기')
        title_label.setFont(QFont('Arial', 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 텍스트 입력 영역
        text_label = QLabel('텍스트 입력:')
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText('여기에 한국어 텍스트를 입력하세요...')
        # 엔터 키 이벤트 처리를 위한 이벤트 필터 설정
        self.text_edit.installEventFilter(self)
        main_layout.addWidget(text_label)
        main_layout.addWidget(self.text_edit)
        
        # 화자 선택 콤보박스
        speaker_layout = QHBoxLayout()
        speaker_label = QLabel('화자:')
        self.speaker_combo = QComboBox()
        speaker_layout.addWidget(speaker_label)
        speaker_layout.addWidget(self.speaker_combo)
        main_layout.addLayout(speaker_layout)
        
        # 속도 조절 슬라이더
        speed_layout = QHBoxLayout()
        speed_label = QLabel('속도:')
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(150)
        self.speed_slider.setValue(100)
        self.speed_value_label = QLabel('1.0')
        self.speed_slider.valueChanged.connect(self.update_speed_label)
        
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_value_label)
        main_layout.addLayout(speed_layout)
        
        # 진행 상태 표시줄
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        self.generate_button = QPushButton('음성 생성')
        self.generate_button.clicked.connect(self.generate_tts)
        
        self.play_button = QPushButton('재생')
        self.play_button.clicked.connect(self.play_audio)
        self.play_button.setEnabled(False)
        
        self.save_button = QPushButton('다른 이름으로 저장')
        self.save_button.clicked.connect(self.save_audio)
        self.save_button.setEnabled(False)
        
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)
        
        # 상태 표시줄
        self.status_label = QLabel('준비됨')
        main_layout.addWidget(self.status_label)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 오디오 재생 불가능한 경우 알림
        if not CAN_PLAY_AUDIO:
            QMessageBox.warning(self, '경고', 
                               '오디오 재생을 위한 라이브러리가 설치되지 않았습니다.\n'
                               '오디오 재생 기능을 사용하려면 다음 패키지를 설치하세요:\n'
                               'pip install sounddevice soundfile')
    
    def update_speed_label(self):
        speed_value = self.speed_slider.value() / 100.0
        self.speed_value_label.setText(f'{speed_value:.1f}')
    
    def fetch_speakers(self):
        """사용 가능한 화자 목록 가져오기"""
        try:
            response = requests.get(f"{BASE_URL}/speakers")
            if response.status_code == 200:
                self.speakers = response.json()["available_speakers"]
                self.speaker_combo.clear()
                self.speaker_combo.addItems(self.speakers)
                
                # KR 화자가 있으면 기본 선택
                if "KR" in self.speakers:
                    index = self.speakers.index("KR")
                    self.speaker_combo.setCurrentIndex(index)
                
                self.status_label.setText(f"화자 목록을 가져왔습니다. {len(self.speakers)}개의 화자가 있습니다.")
            else:
                self.status_label.setText(f"화자 목록을 가져오는 중 오류 발생: {response.status_code}")
                # 기본값 설정
                self.speakers = ["KR"]
                self.speaker_combo.clear()
                self.speaker_combo.addItems(self.speakers)
        except Exception as e:
            self.status_label.setText(f"API 요청 중 오류 발생: {e}")
            # 기본값 설정
            self.speakers = ["KR"]
            self.speaker_combo.clear()
            self.speaker_combo.addItems(self.speakers)
    
    def generate_tts(self):
        """TTS 생성 요청"""
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, '경고', '텍스트가 비어있습니다. 텍스트를 입력하세요.')
            return
        
        voice_id = self.speaker_combo.currentText()
        speed = self.speed_slider.value() / 100.0
        
        # UI 상태 업데이트
        self.generate_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("음성 생성 중...")
        
        # 워커 스레드 생성 및 시작
        self.worker = TTSWorker(text, voice_id, speed)
        self.worker.finished.connect(self.on_tts_finished)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.start()
    
    def on_tts_finished(self, success, result):
        """TTS 생성 완료 처리"""
        self.generate_button.setEnabled(True)
        
        if success:
            self.status_label.setText(f"음성 생성 완료: {result}")
            self.play_button.setEnabled(CAN_PLAY_AUDIO)
            self.save_button.setEnabled(True)
            
            # 오디오 데이터 저장
            if CAN_PLAY_AUDIO:
                self.current_audio = self.worker.audio_data
                self.current_sample_rate = self.worker.sample_rate
                
                # 음성 생성 후 자동 재생
                self.play_audio()
        else:
            self.status_label.setText(f"오류: {result}")
            QMessageBox.critical(self, '오류', result)
        
        self.progress_bar.setVisible(False)
    
    def play_audio(self):
        """생성된 오디오 재생"""
        if CAN_PLAY_AUDIO and self.current_audio is not None:
            self.status_label.setText("오디오 재생 중...")
            sd.play(self.current_audio, self.current_sample_rate)
            sd.wait()  # 재생이 끝날 때까지 대기
            self.status_label.setText("재생 완료")
    
    def save_audio(self):
        """오디오 파일 다른 이름으로 저장"""
        if self.worker and self.worker.filename:
            file_path, _ = QFileDialog.getSaveFileName(
                self, '다른 이름으로 저장', '', 'WAV 파일 (*.wav);;모든 파일 (*)')
            
            if file_path:
                # 원본 파일을 새 위치로 복사
                import shutil
                shutil.copy2(self.worker.filename, file_path)
                self.status_label.setText(f"파일이 저장되었습니다: {file_path}")
    
    def eventFilter(self, obj, event):
        """QTextEdit에서 엔터 키 이벤트를 처리하는 필터"""
        if obj is self.text_edit and event.type() == QEvent.KeyPress:
            key_event = QKeyEvent(event)
            # Ctrl+Enter 또는 Shift+Enter는 줄바꿈으로 처리
            if key_event.key() == Qt.Key_Return and not (key_event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                self.generate_tts()
                return True
        
        return super().eventFilter(obj, event)


def main():
    app = QApplication(sys.argv)
    window = KoreanTTSApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

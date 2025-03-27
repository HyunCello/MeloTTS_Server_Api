import soundcard as sc
import numpy as np
import socket
import time

# 네트워크 설정
SERVER_IP = '192.168.50.31'  # 사용자에게 서버 IP 주소 입력 요청
SERVER_PORT = 12345

# 오디오 설정
SAMPLE_RATE = 44100
CHANNELS = 1
BLOCKSIZE = 1024
DTYPE = 'float32'

def main():
    # 사용 가능한 마이크 목록 출력
    print("사용 가능한 마이크:")
    for i, mic in enumerate(sc.all_microphones(include_loopback=True)):
        print(f"{i}: {mic.name}")
    
    # 사용자에게 마이크 선택 요청
    mic_idx = int(input("사용할 마이크 번호를 입력하세요: "))
    selected_mic = sc.all_microphones(include_loopback=True)[mic_idx]
    
    print(f"선택된 마이크: {selected_mic.name}")
    
    # 소켓 연결
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER_IP, SERVER_PORT))
    
    try:
        # 마이크 스트리밍 시작
        with selected_mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=BLOCKSIZE) as mic:
            print("마이크 스트리밍 시작... Ctrl+C로 종료")
            while True:
                # 마이크에서 오디오 데이터 읽기
                data = mic.record(numframes=BLOCKSIZE)
                
                # 데이터를 바이트로 변환
                data_bytes = data.astype(DTYPE).tobytes()
                
                # 데이터 크기 전송 (4바이트 정수)
                size = len(data_bytes)
                client_socket.send(size.to_bytes(4, byteorder='little'))
                
                # 오디오 데이터 전송
                client_socket.send(data_bytes)
                
                time.sleep(0.001)  # CPU 사용량 감소
    except KeyboardInterrupt:
        print("스트리밍 종료")
    finally:
        client_socket.close()

if __name__ == "__main__":
    main()
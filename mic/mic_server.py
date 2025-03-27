import soundcard as sc
import numpy as np
import socket
import time

# 네트워크 설정
HOST = '0.0.0.0'
PORT = 12345

# 오디오 설정
SAMPLE_RATE = 44100
CHANNELS = 1
BLOCKSIZE = 1024
DTYPE = 'float32'

def main():
    # 사용 가능한 스피커 목록 출력
    print("사용 가능한 스피커:")
    for i, speaker in enumerate(sc.all_speakers()):
        print(f"{i}: {speaker.name}")

    # 사용자에게 스피커 선택 요청
    speaker_idx = int(input("사용할 스피커 번호를 입력하세요: "))
    selected_speaker = sc.all_speakers()[speaker_idx]

    print(f"선택된 스피커: {selected_speaker.name}")

    # 소켓 설정
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)

    print(f"서버가 {PORT} 포트에서 연결을 기다리고 있습니다...")
    client_socket, addr = server_socket.accept()
    print(f"클라이언트가 연결되었습니다: {addr}")

    try:
        # 스피커로 재생 시작
        with selected_speaker.player(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=BLOCKSIZE) as speaker:
            print("오디오 재생 시작... Ctrl+C로 종료")
            while True:
                # 데이터 크기 수신 (4바이트 정수)
                size_bytes = client_socket.recv(4)
                if not size_bytes:
                    break

                size = int.from_bytes(size_bytes, byteorder='little')

                # 오디오 데이터 수신
                data_bytes = b''
                while len(data_bytes) < size:
                    chunk = client_socket.recv(size - len(data_bytes))
                    if not chunk:
                        break
                    data_bytes += chunk

                # 바이트를 numpy 배열로 변환
                data = np.frombuffer(data_bytes, dtype=DTYPE).reshape(-1, CHANNELS)

                # 스피커로 재생
                speaker.play(data)
    except KeyboardInterrupt:
        print("재생 종료")
    finally:
        client_socket.close()
        server_socket.close()

if __name__ == "__main__":
    main()

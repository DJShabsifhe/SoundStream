#! env python3

import socket
import datetime
import pyaudio

print("UDP Sound Trans Client")

DEVICE_SERVER_IP = '192.168.31.121'
DEVICE_SERVER_PORT = 6666

# Parameters
FORMAT = pyaudio.paInt16  # 16bit PCM
CHANNELS = 1
RATE = 16000
CHUNK = 1024

wifi_server_addr = (DEVICE_SERVER_IP, DEVICE_SERVER_PORT)

udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udpsock.settimeout(0.05)

# Initialize PyAudio to capture system audio input
audio = pyaudio.PyAudio()
stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

def send(data):

    total_len = len(data)
    current_len = 0

    while current_len < total_len:
        print(str(datetime.datetime.now()), "send data [%08d]" % (current_len))
        ret = udpsock.sendto(data[current_len:current_len + CHUNK], wifi_server_addr)

        if ret < 0:
            print("send error at index", current_len)
            break
        current_len += ret

        try:
            receive_data, pair_addr = udpsock.recvfrom(64)
            print(str(datetime.datetime.now()), "receive data", receive_data, pair_addr)

        except:
            print("recvfrom timeout")
            pass

def apply_low_pass_filter(data):
    filtered_data = bytearray(len(data))
    alpha = 0.1  # Smoothing factor, adjust as needed
    prev_sample = 0

    for i in range(0, len(data), 2):
        sample = int.from_bytes(data[i:i+2], byteorder='little', signed=True)
        filtered_sample = int(alpha * sample + (1 - alpha) * prev_sample)
        filtered_data[i:i+2] = filtered_sample.to_bytes(2, byteorder='little', signed=True)
        prev_sample = filtered_sample

    return filtered_data

def send_audio():

    print("开始推送音频...")

    try:
        while True:
            audio_data = stream.read(CHUNK, exception_on_overflow=False)
            filtered_audio_data = apply_low_pass_filter(audio_data)  # Apply the low-pass filter
            send(filtered_audio_data)

    except KeyboardInterrupt:
        print("停止推送音频...")

    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        udpsock.close()


if __name__ == '__main__':
    send_audio()

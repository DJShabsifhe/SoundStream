import socket
import time
import threading

# CONFIGURATION (Match these to your receiver_config.h) 

DISCOVERY_PORT = 6667  # Change this to your DISCOVERY_PORT
AUDIO_PORT = 6666      # Change this to your PORT
DEVICE_NAME = "Vest-Parody"
BROADCAST_INTERVAL = 5  # Seconds

# Attempt to get the computer's local IP address
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

LOCAL_IP = get_local_ip()

def get_discovery_message():
    """Formats the message: SOUNDSTREAM_DISCOVERY|NAME|IP|PORT"""
    return f"SOUNDSTREAM_DISCOVERY|{DEVICE_NAME}|{LOCAL_IP}|{AUDIO_PORT}"

def periodic_broadcast():
    """Sends a UDP broadcast heartbeat every X seconds."""
    print(f"[*] Starting periodic broadcast on port {DISCOVERY_PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while True:
            message = get_discovery_message()
            sock.sendto(message.encode(), ('<broadcast>', DISCOVERY_PORT))
            print(f"[Broadcast] Sent: {message}")
            time.sleep(BROADCAST_INTERVAL)

def listen_for_requests():
    """Listens for 'SOUNDSTREAM_DISCOVERY_REQUEST' and replies directly."""
    print(f"[*] Listening for discovery requests on port {DISCOVERY_PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # Allow multiple apps to use the same port and bind to all interfaces
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', DISCOVERY_PORT))
        
        while True:
            data, addr = sock.recvfrom(1024)
            message = data.decode().strip()
            
            if message == "SOUNDSTREAM_DISCOVERY_REQUEST":
                print(f"[Request] Received request from {addr}")
                response = get_discovery_message()
                sock.sendto(response.encode(), addr)
                print(f"[Response] Sent info to {addr}")

if __name__ == "__main__":
    print(f"--- SoundStream Discovery Emulator ---")
    print(f"Emulating: {DEVICE_NAME} at {LOCAL_IP}")
    
    # Run both functions in separate threads
    t1 = threading.Thread(target=periodic_broadcast, daemon=True)
    t2 = threading.Thread(target=listen_for_requests, daemon=True)
    
    t1.start()
    t2.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping emulator...")
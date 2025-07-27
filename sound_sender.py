#! env python3

import socket
import datetime
import pyaudio
import threading
from queue import Queue, Full
import time
import curses
from collections import deque
import numpy as np
import sys

# Initialize logging
log_messages = deque(maxlen=1000)  # Store last 1000 messages
log_lock = threading.Lock()

DEVICES = [
    {'name': 'Device1', 'ip': '192.168.31.203', 'port': 6666}
]

# Parameters to match ESP32 I2S settings
FORMAT = pyaudio.paInt16  # 16bit PCM to match ESP32's I2S_BITS_PER_SAMPLE_16BIT
CHANNELS = 1
RATE = 8000  # Match ESP32's SAMPLE_RATE
CHUNK = 256  # Half of the ESP32's dma_buf_len
VOLUME_FACTOR = 2.0  # Volume amplification factor (adjustable)
AUDIO_SOURCE = 'blackhole'  # 'blackhole' or 'microphone'

# Global variables for device management
device_queues = {}
device_sockets = {}
device_threads = {}
stop_threads = False

def log_message(msg):
    """Add a message to the log with timestamp"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with log_lock:
        log_messages.append(f"{timestamp} - {msg}")

def device_sender_thread(device):
    """Thread function to handle sending data to a specific device"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.01)  # Reduced timeout for faster error detection
    device_sockets[device['name']] = sock
    
    while not stop_threads:
        try:
            chunk = device_queues[device['name']].get(timeout=1.0)
            if chunk is None:  # Sentinel value to stop the thread
                break
                
            try:
                ret = sock.sendto(chunk, (device['ip'], device['port']))
                if ret < 0:
                    log_message(f"Send error to {device['name']}")
                    continue
                    
                # Try to receive acknowledgment
                try:
                    receive_data, pair_addr = sock.recvfrom(64)
                    if pair_addr[0] == device['ip']:
                        log_message(f"Received ACK from {device['name']}")
                except socket.timeout:
                    log_message(f"No response from {device['name']}")
                    
            except Exception as e:
                log_message(f"Error sending to {device['name']}: {e}")
                
        except Queue.Empty:
            continue  # No data available, continue waiting
            
    sock.close()

# Initialize PyAudio to capture system audio
audio = pyaudio.PyAudio()

def list_audio_devices():
    """List all available audio input devices and their indices"""
    devices = []
    for i in range(audio.get_device_count()):
        device_info = audio.get_device_info_by_index(i)
        if device_info['maxInputChannels'] > 0:  # Only list input devices
            devices.append({
                'index': i,
                'name': device_info['name'],
                'is_virtual': 'Soundflower' in device_info['name'] or 'BlackHole' in device_info['name']
            })
    return devices

def select_audio_device():
    """Let user select the audio input device"""
    devices = list_audio_devices()

    print(r"""    ___             ___          _____                __         
   /   | __  ______/ (_____     / ___/___  ____  ____/ ___  _____
  / /| |/ / / / __  / / __ \    \__ \/ _ \/ __ \/ __  / _ \/ ___/
 / ___ / /_/ / /_/ / / /_/ /   ___/ /  __/ / / / /_/ /  __/ /    
/_/  |_\__,_/\__,_/_/\____/   /____/\___/_/ /_/\__,_/\___/_/     
   _________            __                                       
  / ____/ (____  ____  / /_                                      
 / /   / / / _ \/ __ \/ __/                                      
/ /___/ / /  __/ / / / /_                                        
\____/_/_/\___/_/ /_/\__/                                        
                                                                 
""")
    
    print("\nAvailable audio input devices:")
    print("-" * 50)
    for i, device in enumerate(devices):
        device_type = "Virtual Device" if device['is_virtual'] else "Physical Device"
        print(f"{i+1}. {device['name']} ({device_type})")
    print("-" * 50)
    
    while True:
        try:
            choice = input("Select device number (or press Enter for default based on AUDIO_SOURCE): ")
            if not choice:  # User pressed Enter
                # Find default device based on AUDIO_SOURCE
                if AUDIO_SOURCE == 'blackhole':
                    for device in devices:
                        if device['is_virtual']:
                            return device['index']
                    print("No virtual audio device found. Please install BlackHole or Soundflower.")
                    sys.exit(1)
                else:  # microphone
                    # Find first non-virtual device
                    for device in devices:
                        if not device['is_virtual']:
                            return device['index']
                    return None  # Use system default if no suitable device found
            
            choice = int(choice)
            if 1 <= choice <= len(devices):
                return devices[choice-1]['index']
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

# Select audio device
device_index = select_audio_device()

stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=device_index,
    frames_per_buffer=CHUNK
)

def send(data):
    total_len = len(data)
    current_len = 0

    while current_len < total_len:
        chunk = data[current_len:current_len + CHUNK]
        log_message(f"Queuing chunk {current_len//CHUNK + 1}")
        
        # Queue the chunk for all devices
        for device in DEVICES:
            try:
                # Non-blocking put with timeout
                device_queues[device['name']].put(chunk, timeout=0.1)
            except Full:
                log_message(f"Queue full for {device['name']}, dropping chunk")
                
        current_len += CHUNK

def toggle_input_source(stdscr):
    """Toggle between BlackHole and Microphone input"""
    global AUDIO_SOURCE
    height, width = stdscr.getmaxyx()
    
    # Create window
    select_win = curses.newwin(7, width - 4, height - 9, 2)
    select_win.box()
    select_win.addstr(1, 2, "Select Audio Input Source:")
    select_win.addstr(2, 2, "1. BlackHole/Soundflower (System Audio)")
    select_win.addstr(3, 2, "2. Microphone")
    select_win.addstr(5, 2, "Current: " + ("BlackHole" if AUDIO_SOURCE == 'blackhole' else "Microphone"))
    select_win.refresh()
    
    try:
        while True:
            ch = select_win.getch()
            if ch == ord('1'):
                AUDIO_SOURCE = 'blackhole'
                break
            elif ch == ord('2'):
                AUDIO_SOURCE = 'microphone'
                break
            elif ch == 27:  # ESC
                break
    except curses.error:
        pass

def configure_devices(stdscr):
    """Device configuration UI"""
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        # Draw title
        stdscr.addstr(0, 0, "Audio Sender Client - Device Configuration", curses.A_BOLD)
        stdscr.addstr(1, 0, "-" * (width - 1))
        
        # Show current devices
        stdscr.addstr(3, 0, "Configured Devices:", curses.A_BOLD)
        for i, device in enumerate(DEVICES):
            stdscr.addstr(4 + i, 2, f"{i+1}. {device['name']} - {device['ip']}:{device['port']}")
        
        # Show menu
        menu_start = 5 + len(DEVICES)
        stdscr.addstr(menu_start, 0, "-" * (width - 1))
        stdscr.addstr(menu_start + 1, 0, "Menu:", curses.A_BOLD)
        stdscr.addstr(menu_start + 2, 2, "a - Add new device")
        stdscr.addstr(menu_start + 3, 2, "e - Edit device")
        stdscr.addstr(menu_start + 4, 2, "d - Delete device")
        stdscr.addstr(menu_start + 5, 2, "i - Input source (BlackHole/Microphone)")
        stdscr.addstr(menu_start + 6, 2, "s - Start streaming")
        stdscr.addstr(menu_start + 7, 2, "q - Quit")
        
        stdscr.refresh()
        
        # Handle input
        try:
            key = stdscr.getch()
            if key == ord('q'):
                return False  # Don't start streaming
            elif key == ord('s') and len(DEVICES) > 0:
                return True   # Start streaming
            elif key == ord('a'):
                add_device(stdscr)
            elif key == ord('e'):
                edit_device(stdscr)
            elif key == ord('d'):
                delete_device(stdscr)
            elif key == ord('i'):
                toggle_input_source(stdscr)
        except curses.error:
            pass

def add_device(stdscr):
    """Add a new device UI"""
    curses.noecho()  # Disable automatic echo
    curses.curs_set(1)
    height, width = stdscr.getmaxyx()
    
    # Enable handling of escape sequences
    stdscr.keypad(True)
    
    # Draw input form
    form_win = curses.newwin(9, width - 4, height - 11, 2)
    form_win.box()
    form_win.addstr(1, 2, "Add New Device")
    form_win.addstr(2, 2, "Name: ")
    form_win.addstr(3, 2, "IP: ")
    form_win.addstr(4, 2, "Port: ")
    form_win.addstr(6, 2, "Press ESC to cancel", curses.A_DIM)
    form_win.refresh()
    
    # Get input
    name = ""
    ip = ""
    port = ""
    
    try:
        # Get name
        form_win.addstr(2, 8, " " * 30)  # Clear line
        name_pos = 0
        while True:
            form_win.move(2, 8 + name_pos)
            ch = form_win.getch()
            if ch == 27:  # ESC
                return
            elif ch == 10:  # Enter
                if name:  # Only proceed if name is not empty
                    break
            elif ch == 127 or ch == 263:  # Backspace/Delete
                if name_pos > 0:
                    name = name[:-1]
                    name_pos -= 1
                    form_win.addstr(2, 8 + name_pos, " ")
                    form_win.move(2, 8 + name_pos)
            elif ch >= 32 and ch < 127 and name_pos < 20:  # Printable characters
                name += chr(ch)
                form_win.addch(ch)
                name_pos += 1
            form_win.refresh()
        
        # Get IP
        form_win.addstr(3, 6, " " * 30)  # Clear line
        ip_pos = 0
        while True:
            form_win.move(3, 6 + ip_pos)
            ch = form_win.getch()
            if ch == 27:  # ESC
                return
            elif ch == 10:  # Enter
                if ip:  # Only proceed if IP is not empty
                    break
            elif ch == 127 or ch == 263:  # Backspace/Delete
                if ip_pos > 0:
                    ip = ip[:-1]
                    ip_pos -= 1
                    form_win.addstr(3, 6 + ip_pos, " ")
                    form_win.move(3, 6 + ip_pos)
            elif ch >= 32 and ch < 127 and ip_pos < 15:  # Printable characters
                ip += chr(ch)
                form_win.addch(ch)
                ip_pos += 1
            form_win.refresh()
        
        # Get port
        form_win.addstr(4, 8, " " * 10)  # Clear line
        port_pos = 0
        while True:
            form_win.move(4, 8 + port_pos)
            ch = form_win.getch()
            if ch == 27:  # ESC
                return
            elif ch == 10:  # Enter
                if port:  # Only proceed if port is not empty
                    break
            elif ch == 127 or ch == 263:  # Backspace/Delete
                if port_pos > 0:
                    port = port[:-1]
                    port_pos -= 1
                    form_win.addstr(4, 8 + port_pos, " ")
                    form_win.move(4, 8 + port_pos)
            elif ch >= 48 and ch <= 57 and port_pos < 5:  # Numbers only
                port += chr(ch)
                form_win.addch(ch)
                port_pos += 1
            form_win.refresh()
        
        if name and ip and port:
            try:
                port = int(port)
                DEVICES.append({'name': name, 'ip': ip, 'port': port})
            except ValueError:
                form_win.addstr(6, 2, "Invalid port number!", curses.color_pair(2))
                form_win.refresh()
                form_win.getch()
    except curses.error:
        pass
    
    curses.noecho()
    curses.curs_set(0)

def edit_device(stdscr):
    """Edit existing device UI"""
    if not DEVICES:
        return
        
    curses.noecho()  # Disable automatic echo
    curses.curs_set(1)
    height, width = stdscr.getmaxyx()
    
    # Select device
    select_win = curses.newwin(len(DEVICES) + 4, width - 4, height - len(DEVICES) - 6, 2)
    select_win.box()
    select_win.addstr(1, 2, "Select device number to edit (1-" + str(len(DEVICES)) + "): ")
    select_win.refresh()
    
    try:
        # Get device number
        select_win.move(1, 40)
        idx_str = ""
        while True:
            ch = select_win.getch()
            if ch == 27:  # ESC
                return
            elif ch == 10:  # Enter
                if idx_str:
                    break
            elif ch == 127 or ch == 263:  # Backspace/Delete
                if idx_str:
                    idx_str = idx_str[:-1]
                    select_win.addstr(1, 40 + len(idx_str), " ")
                    select_win.move(1, 40 + len(idx_str))
            elif ch >= 48 and ch <= 57 and len(idx_str) < 2:  # Numbers only
                idx_str += chr(ch)
                select_win.addch(ch)
            select_win.refresh()
            
        idx = int(idx_str) - 1
        
        if 0 <= idx < len(DEVICES):
            device = DEVICES[idx]
            form_win = curses.newwin(9, width - 4, height - 11, 2)
            form_win.box()
            form_win.addstr(1, 2, f"Edit Device {idx + 1}")
            form_win.addstr(2, 2, f"Name [{device['name']}]: ")
            form_win.addstr(3, 2, f"IP [{device['ip']}]: ")
            form_win.addstr(4, 2, f"Port [{device['port']}]: ")
            form_win.addstr(6, 2, "Press ESC to cancel, Enter to keep current value", curses.A_DIM)
            form_win.refresh()
            
            # Get new name
            name_start = len(device['name']) + 10
            form_win.move(2, name_start)
            new_name = ""
            name_pos = 0
            while True:
                form_win.move(2, name_start + name_pos)
                ch = form_win.getch()
                if ch == 27:  # ESC
                    return
                elif ch == 10:  # Enter
                    break
                elif ch == 127 or ch == 263:  # Backspace/Delete
                    if name_pos > 0:
                        new_name = new_name[:-1]
                        name_pos -= 1
                        form_win.addstr(2, name_start + name_pos, " ")
                        form_win.move(2, name_start + name_pos)
                elif ch >= 32 and ch < 127 and name_pos < 20:  # Printable characters
                    new_name += chr(ch)
                    form_win.addch(ch)
                    name_pos += 1
                form_win.refresh()
            
            # Get new IP
            ip_start = len(device['ip']) + 8
            form_win.move(3, ip_start)
            new_ip = ""
            ip_pos = 0
            while True:
                form_win.move(3, ip_start + ip_pos)
                ch = form_win.getch()
                if ch == 27:  # ESC
                    return
                elif ch == 10:  # Enter
                    break
                elif ch == 127 or ch == 263:  # Backspace/Delete
                    if ip_pos > 0:
                        new_ip = new_ip[:-1]
                        ip_pos -= 1
                        form_win.addstr(3, ip_start + ip_pos, " ")
                        form_win.move(3, ip_start + ip_pos)
                elif ch >= 32 and ch < 127 and ip_pos < 15:  # Printable characters
                    new_ip += chr(ch)
                    form_win.addch(ch)
                    ip_pos += 1
                form_win.refresh()
            
            # Get new port
            port_start = len(str(device['port'])) + 10
            form_win.move(4, port_start)
            new_port = ""
            port_pos = 0
            while True:
                form_win.move(4, port_start + port_pos)
                ch = form_win.getch()
                if ch == 27:  # ESC
                    return
                elif ch == 10:  # Enter
                    break
                elif ch == 127 or ch == 263:  # Backspace/Delete
                    if port_pos > 0:
                        new_port = new_port[:-1]
                        port_pos -= 1
                        form_win.addstr(4, port_start + port_pos, " ")
                        form_win.move(4, port_start + port_pos)
                elif ch >= 48 and ch <= 57 and port_pos < 5:  # Numbers only
                    new_port += chr(ch)
                    form_win.addch(ch)
                    port_pos += 1
                form_win.refresh()
            
            if new_name:
                device['name'] = new_name
            if new_ip:
                device['ip'] = new_ip
            if new_port:
                try:
                    device['port'] = int(new_port)
                except ValueError:
                    form_win.addstr(7, 2, "Invalid port number!", curses.color_pair(2))
                    form_win.refresh()
                    form_win.getch()
    except (ValueError, curses.error):
        pass
    
    curses.noecho()
    curses.curs_set(0)

def delete_device(stdscr):
    """Delete device UI"""
    if not DEVICES:
        return
        
    curses.echo()
    curses.curs_set(1)
    height, width = stdscr.getmaxyx()
    
    # Select device
    select_win = curses.newwin(len(DEVICES) + 4, width - 4, height - len(DEVICES) - 6, 2)
    select_win.box()
    select_win.addstr(1, 2, "Select device number to delete (1-" + str(len(DEVICES)) + "): ")
    select_win.refresh()
    
    try:
        select_win.move(1, 45)
        idx_str = select_win.getstr(2).decode('utf-8')
        idx = int(idx_str) - 1
        
        if 0 <= idx < len(DEVICES):
            del DEVICES[idx]
    except (ValueError, curses.error):
        pass
    
    curses.noecho()
    curses.curs_set(0)

def draw_screen(stdscr, header_win, log_win):
    """Update the screen with current information"""
    # Update header
    header_win.clear()
    header_win.addstr(0, 0, "Audio Stream Client", curses.A_BOLD)
    header_win.addstr(1, 0, "-" * (curses.COLS - 1))
    header_win.addstr(2, 0, "Configured devices:")
    
    row = 3
    for device in DEVICES:
        header_win.addstr(row, 0, f"- {device['name']}: {device['ip']}:{device['port']}")
        row += 1
    
    header_win.addstr(row, 0, "-" * (curses.COLS - 1))
    header_win.refresh()
    
    # Update log window with latest messages
    log_win.clear()
    with log_lock:
        messages = list(log_messages)
    
    # Calculate how many messages we can show
    height = curses.LINES - row - 1
    start_idx = max(0, len(messages) - height)
    
    for i, msg in enumerate(messages[start_idx:]):
        if i >= height:
            break
        try:
            log_win.addstr(i, 0, msg[:curses.COLS-1])
        except curses.error:
            pass
    
    log_win.refresh()

def send_audio(stdscr):
    global device_queues, device_threads, stop_threads

    # Set up colors
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    
    # Hide the cursor
    curses.curs_set(0)
    
    # Enable handling of escape sequences
    stdscr.keypad(True)
    stdscr.nodelay(1)  # Non-blocking input
    
    # Initialize queues and start sender threads for each device
    stop_threads = False
    device_queues.clear()
    device_threads.clear()
    
    for device in DEVICES:
        device_queues[device['name']] = Queue(maxsize=4)  # Further reduced buffer size
        thread = threading.Thread(target=device_sender_thread, args=(device,))
        thread.daemon = True
        device_threads[device['name']] = thread
        thread.start()
        log_message(f"Started sender thread for {device['name']}")
    
    # Create windows for header and log
    header_height = len(DEVICES) + 5  # Title + separator + "Configured devices:" + devices + separator
    header_win = curses.newwin(header_height, curses.COLS, 0, 0)
    log_win = curses.newwin(curses.LINES - header_height, curses.COLS, header_height, 0)
    
    # Enable scrolling for log window
    log_win.scrollok(True)
    
    # Draw initial screen
    draw_screen(stdscr, header_win, log_win)
    
    log_message("Starting audio stream...")
    
    try:
        while True:
            audio_data = stream.read(CHUNK, exception_on_overflow=False)
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            # Apply volume adjustment
            audio_array = np.clip(audio_array * VOLUME_FACTOR, -32768, 32767).astype(np.int16)
            
            # Convert mono to stereo by duplicating each sample
            stereo_array = np.repeat(audio_array, 2)
            
            # Convert back to bytes
            filtered_audio_data = stereo_array.tobytes()
            send(filtered_audio_data)
            
            # Update the display
            draw_screen(stdscr, header_win, log_win)
            
            # Check for key presses
            try:
                key = stdscr.getch()
                if key == ord('q'):
                    raise KeyboardInterrupt
                elif key == 27:  # ESC key
                    log_message("Going back to device configuration...")
                    return True  # Return True to indicate we should go back to config
            except curses.error:
                pass

    except KeyboardInterrupt:
        log_message("Stopping audio stream...")

    finally:
        # Stop all sender threads
        stop_threads = True
        for device in DEVICES:
            device_queues[device['name']].put(None)
            
        # Close audio resources
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Close all sockets
        for sock in device_sockets.values():
            sock.close()


def main(stdscr):
    while True:
        # Show device configuration UI first
        if configure_devices(stdscr):
            # If configuration successful and user wants to start streaming
            should_continue = send_audio(stdscr)
            if not should_continue:
                break
        else:
            break

if __name__ == '__main__':
    curses.wrapper(main)

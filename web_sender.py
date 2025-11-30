#!/usr/bin/env python3
"""
Web-based UI for SoundStream Audio Sender
Wraps sound_sender.py functionality with a Flask web interface
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import json
import os
import sys
import numpy as np

# Import functions from sound_sender without running the main script
import sound_sender

# Try to import noisereduce
try:
    import noisereduce as nr
    NOISE_REDUCE_AVAILABLE = True
except ImportError:
    NOISE_REDUCE_AVAILABLE = False
    print("Warning: noisereduce library not found. Noise reduction feature will be disabled.")

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = 'soundstream-secret-key'
CORS(app)

# Increase ping timeout/interval to fix connection instability
# ping_timeout: Time to wait for a pong before disconnecting (default 5)
# ping_interval: Time between pings (default 25)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

# Global state
streaming_active = False
streaming_thread = None
audio_stream = None
audio_obj = None
selected_device_index = None
noise_reduction_enabled = False

# Store original log_message function and wrap it to emit to websocket
original_log_message = sound_sender.log_message

def web_log_message(msg):
    """Wrapper for log_message that also emits to WebSocket"""
    original_log_message(msg)
    
    # Check for buffer full messages and emit special status
    if 'Queue full for' in msg:
        device_name = msg.split('Queue full for ')[1].split(',')[0]
        socketio.emit('device_status', {
            'device': device_name,
            'status': 'buffer_full'
        }, namespace='/logs')
    
    socketio.emit('log_message', {'message': msg}, namespace='/logs')

# Replace the log_message function in sound_sender module
sound_sender.log_message = web_log_message


@app.route('/')
def index():
    """Serve the main web interface"""
    return send_from_directory('static', 'index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(sound_sender.config)


@app.route('/api/config', methods=['PUT'])
def update_config():
    """Update configuration"""
    new_config = request.json
    sound_sender.config.update(new_config)
    if sound_sender.save_config(sound_sender.config):
        # Update global variables from config
        sound_sender.DEVICES = sound_sender.config['devices']
        sound_sender.VOLUME_FACTOR = sound_sender.config['audio']['volume_factor']
        sound_sender.AUDIO_SOURCE = sound_sender.config['audio']['audio_source']
        return jsonify({'success': True, 'config': sound_sender.config})
    return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get list of configured devices"""
    return jsonify(sound_sender.DEVICES)


@app.route('/api/devices', methods=['POST'])
def add_device():
    """Add a new device"""
    device = request.json
    
    # Validate device data
    if not all(k in device for k in ['name', 'ip', 'port']):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Check if device already exists
    for existing in sound_sender.DEVICES:
        if existing['ip'] == device['ip'] and existing['port'] == device['port']:
            return jsonify({'success': False, 'error': 'Device already exists'}), 400
    
    sound_sender.DEVICES.append(device)
    sound_sender.config['devices'] = sound_sender.DEVICES
    
    if sound_sender.save_config(sound_sender.config):
        return jsonify({'success': True, 'devices': sound_sender.DEVICES})
    return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500


@app.route('/api/devices/<int:index>', methods=['PUT'])
def update_device(index):
    """Update an existing device"""
    if index < 0 or index >= len(sound_sender.DEVICES):
        return jsonify({'success': False, 'error': 'Device not found'}), 404
    
    device_data = request.json
    
    # Update only provided fields
    for key in ['name', 'ip', 'port']:
        if key in device_data:
            sound_sender.DEVICES[index][key] = device_data[key]
    
    sound_sender.config['devices'] = sound_sender.DEVICES
    
    if sound_sender.save_config(sound_sender.config):
        return jsonify({'success': True, 'devices': sound_sender.DEVICES})
    return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500


@app.route('/api/devices/<int:index>', methods=['DELETE'])
def delete_device(index):
    """Delete a device"""
    if index < 0 or index >= len(sound_sender.DEVICES):
        return jsonify({'success': False, 'error': 'Device not found'}), 404
    
    del sound_sender.DEVICES[index]
    sound_sender.config['devices'] = sound_sender.DEVICES
    
    if sound_sender.save_config(sound_sender.config):
        return jsonify({'success': True, 'devices': sound_sender.DEVICES})
    return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500


@app.route('/api/devices/scan', methods=['POST'])
def scan_devices():
    """Scan for devices on the network"""
    discovered = sound_sender.discover_devices()
    return jsonify({'success': True, 'devices': discovered})


@app.route('/api/audio-devices', methods=['GET'])
def get_audio_devices():
    """Get list of available audio input devices"""
    devices = sound_sender.list_audio_devices()
    return jsonify(devices)


@app.route('/api/stream/start', methods=['POST'])
def start_streaming():
    """Start audio streaming"""
    global streaming_active, streaming_thread, audio_stream, audio_obj, selected_device_index
    
    if streaming_active:
        return jsonify({'success': False, 'error': 'Streaming already active'}), 400
    
    if not sound_sender.DEVICES:
        return jsonify({'success': False, 'error': 'No devices configured'}), 400
    
    # Get device index from request
    data = request.json or {}
    device_index = data.get('device_index')
    
    if device_index is None:
        return jsonify({'success': False, 'error': 'Please select an audio device'}), 400
    
    try:
        # Stop any existing audio stream first
        if audio_stream is not None:
            try:
                audio_stream.stop_stream()
                audio_stream.close()
            except:
                pass
            audio_stream = None
        
        # Initialize PyAudio if needed
        if audio_obj is None:
            import pyaudio
            audio_obj = pyaudio.PyAudio()
        
        # Store selected device
        selected_device_index = device_index
        
        # Open audio stream with the selected device
        audio_stream = audio_obj.open(
            format=sound_sender.FORMAT,
            channels=sound_sender.CHANNELS,
            rate=sound_sender.RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=sound_sender.CHUNK
        )
        
        # Initialize device queues and threads
        sound_sender.stop_threads = False
        sound_sender.device_queues.clear()
        sound_sender.device_threads.clear()
        
        for device in sound_sender.DEVICES:
            from queue import Queue
            sound_sender.device_queues[device['name']] = Queue(maxsize=sound_sender.QUEUE_MAXSIZE)
            thread = threading.Thread(target=sound_sender.device_sender_thread, args=(device,))
            thread.daemon = True
            sound_sender.device_threads[device['name']] = thread
            thread.start()
            web_log_message(f"Started sender thread for {device['name']}")
        
        # Start streaming thread
        streaming_active = True
        streaming_thread = threading.Thread(target=audio_streaming_worker, daemon=True)
        streaming_thread.start()
        
        web_log_message("Audio streaming started")
        return jsonify({'success': True, 'message': 'Streaming started'})
        
    except Exception as e:
        web_log_message(f"Error starting stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stream/stop', methods=['POST'])
def stop_streaming():
    """Stop audio streaming"""
    global streaming_active, audio_stream
    
    if not streaming_active:
        return jsonify({'success': False, 'error': 'Streaming not active'}), 400
    
    try:
        streaming_active = False
        
        # Stop sender threads
        sound_sender.stop_threads = True
        for device in sound_sender.DEVICES:
            if device['name'] in sound_sender.device_queues:
                try:
                    sound_sender.device_queues[device['name']].put(None, timeout=0.5)
                except:
                    pass
        
        # Give threads time to finish
        import time
        time.sleep(0.5)
        
        # Stop audio stream
        if audio_stream:
            try:
                audio_stream.stop_stream()
                audio_stream.close()
            except:
                pass
            audio_stream = None
        
        # Close sockets
        for sock in list(sound_sender.device_sockets.values()):
            try:
                sock.close()
            except:
                pass
        sound_sender.device_sockets.clear()
        
        web_log_message("Audio streaming stopped")
        return jsonify({'success': True, 'message': 'Streaming stopped'})
        
    except Exception as e:
        web_log_message(f"Error stopping stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stream/status', methods=['GET'])
def get_stream_status():
    """Get current streaming status"""
    return jsonify({
        'active': streaming_active,
        'devices_count': len(sound_sender.DEVICES),
        'noise_reduction': noise_reduction_enabled
    })


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get current logs"""
    with sound_sender.log_lock:
        logs = list(sound_sender.log_messages)
    return jsonify(logs)


@app.route('/api/noise-reduction', methods=['POST'])
def toggle_noise_reduction():
    """Toggle noise reduction"""
    global noise_reduction_enabled
    
    if not NOISE_REDUCE_AVAILABLE:
        return jsonify({'success': False, 'error': 'Noise reduction library not available'}), 400
        
    data = request.json or {}
    noise_reduction_enabled = data.get('enabled', False)
    
    web_log_message(f"Noise reduction {'enabled' if noise_reduction_enabled else 'disabled'}")
    return jsonify({'success': True, 'enabled': noise_reduction_enabled})


def audio_streaming_worker():
    """Worker thread for audio streaming"""
    global streaming_active, audio_stream
    
    import time
    
    last_level_emit = time.time()
    
    try:
        while streaming_active:
            # Yield to allow other threads (like heartbeat) to run
            time.sleep(0.001)
            
            if audio_stream:
                try:
                    audio_data = audio_stream.read(
                        sound_sender.CHUNK, 
                        exception_on_overflow=False # Ignore overflow to prevent crash
                    )
                except Exception as e:
                    # If read fails, wait a bit and try again
                    time.sleep(0.01)
                    continue
                
                # Convert bytes to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Apply noise reduction if enabled
                if noise_reduction_enabled and NOISE_REDUCE_AVAILABLE:
                    try:
                        # Simple spectral gating noise reduction
                        # We assume the signal is mostly speech/music, so we use a stationary noise assumption
                        # For real-time, we use a faster, less aggressive reduction
                        reduced_audio = nr.reduce_noise(
                            y=audio_array.astype(np.float32), 
                            sr=sound_sender.RATE,
                            stationary=True,
                            prop_decrease=0.75, # 75% reduction
                            n_fft=512 # Smaller FFT for speed
                        )
                        audio_array = reduced_audio.astype(np.int16)
                    except Exception as e:
                        # Fallback if NR fails
                        pass
                
                # Calculate audio levels for visualization
                # RMS (root mean square) for loudness
                rms = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
                # Normalize to 0-1 range (int16 max is 32768)
                level = min(rms / 32768.0, 1.0)
                
                # Peak level
                peak = np.abs(audio_array).max() / 32768.0
                
                # Emit audio levels to frontend via WebSocket (throttled to ~20fps)
                current_time = time.time()
                if current_time - last_level_emit >= 0.05:  # 50ms = 20fps
                    socketio.emit('audio_level', {
                        'rms': float(level),
                        'peak': float(peak),
                        'values': audio_array[:100].tolist()  # Send first 100 samples for waveform
                    }, namespace='/logs')
                    last_level_emit = current_time
                
                # Apply volume adjustment
                audio_array = np.clip(
                    audio_array * sound_sender.VOLUME_FACTOR, 
                    -32768, 
                    32767
                ).astype(np.int16)
                
                # Convert mono to stereo by duplicating each sample
                stereo_array = np.repeat(audio_array, 2)
                
                # Convert back to bytes
                filtered_audio_data = stereo_array.tobytes()
                
                # Send to all devices
                sound_sender.send(filtered_audio_data)
                
    except Exception as e:
        web_log_message(f"Streaming error: {e}")
        streaming_active = False


@socketio.on('connect', namespace='/logs')
def handle_connect():
    """Handle WebSocket connection"""
    print('Client connected to logs')
    # Send existing logs
    with sound_sender.log_lock:
        logs = list(sound_sender.log_messages)
    for log in logs:
        emit('log_message', {'message': log})


@socketio.on('disconnect', namespace='/logs')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected from logs')


if __name__ == '__main__':
    # Don't initialize audio device at startup - let user select in UI
    print("=" * 80)
    print("SoundStream Web Interface")
    print("=" * 80)
    print(f"Open your browser to: http://localhost:6001")
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print("\nNote: Select your audio device in the web interface before streaming")
    print()
    
    socketio.run(app, host='0.0.0.0', port=6001, debug=False, allow_unsafe_werkzeug=True)

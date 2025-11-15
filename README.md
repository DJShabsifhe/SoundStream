# UDP Sound Transmission Project

This project demonstrates how to transmit audio data from a computer to a ESP32S3 over UDP using Wi-Fi. The project consists of two components: a device-side firmware written in Arduino and a Python script for capturing and sending audio data from the computer. The firmware connects to a Wi-Fi network and listens for incoming UDP audio packets, while the Python script captures system audio and sends it to the device in real-time.

---

## Features

- **Device-side Firmware**:
  - Connects to a Wi-Fi network using a specified `SSID` and `password`.
  - Listens for incoming UDP packets on a specified port.
  - Processes the received audio data (can be extended for real-time playback or effects).

- **Python Client**:
  - Captures system audio using the `PyAudio` library.
  - Streams audio data to the device over UDP.
  - Handles packet acknowledgment and retransmission in case of network delays or timeouts.
  - Optional desktop GUI (`sound_gui.py`) for easy configuration and control.

---

## Getting Started

### Prerequisites

#### Device Firmware:
- An ESP32 or similar microcontroller with I2S support.
- Arduino IDE with the ESP32 board support package installed.
- A Wi-Fi network with credentials (SSID and password).
- An on-board LED (if applicable, for testing functionality).

#### Python Script / GUI:
- Python 3.x installed on your computer.
- Required Python libraries:
  - `pyaudio`
  - `socket`
  - `datetime`
- A microphone or audio input device.

For the GUI build on macOS you also need:
- `PySimpleGUI`
- `numpy`
- `pyinstaller`
- PortAudio (for PyAudio). On macOS via Homebrew: `brew install portaudio` if needed.

---

### Setup Instructions

#### 1. Device-Side Firmware

1. Install the Arduino IDE along with the ESP32 board support package.
2. Connect your ESP32 to your computer and load the firmware sketch.
3. In the firmware, replace the placeholders in receiver_config_example.h for `ssid` and `password` with your Wi-Fi credentials. Create a receiver_config.h with real values.
4. Compile, and upload the firmware to the ESP32.
5. Open the Serial Monitor to check the connection status. Once the ESP32 connects to Wi-Fi, it will listen for UDP packets on the specified port.

#### 2. Python Script (CLI) or GUI

1. Install the required Python libraries:

   ```bash
   pip install -r requirements.txt
   ```

2. Open the Python script and replace the `DEVICE_SERVER_IP` and `DEVICE_SERVER_PORT` values with the IP address and port of your ESP32 device.

3. CLI: Run the script to start capturing and streaming audio:

   ```bash
   python3 sound_sender.py

4. GUI: Launch the desktop app (TODO):

   ```bash
   python3 sound_gui.py
   ```

5. GUI Packaging for macOS (TODO):

   ```bash
   chmod +x build_mac.sh
   ./build_mac.sh
   ```

   The built app will be available at `dist/SoundStream.app`. On first run, macOS may ask for Microphone permission.
   ```

4. The script will begin streaming audio data to the ESP32. Check the Serial Monitor on the ESP32 for any received audio data logs.

---

### Usage

1. Power on the ESP32 and ensure it connects to the specified Wi-Fi network.
2. Run the Python script on your computer to stream audio data.
3. Monitor the ESP32's Serial Output to confirm it is receiving the audio data.

## Configuration

- **ESP32 Configuration**:
  - Update the `ssid` and `password` in the `keys.h` file with your Wi-Fi credentials.
  - Update the `PORT` value if necessary.

- **Python Script Configuration**:
  - Update `DEVICE_SERVER_IP` with the IP address of your ESP32.
  - Update `DEVICE_SERVER_PORT` with the port number the ESP32 is listening on.

---

## Dependencies

### Device-Side:
- ESP32 board library for Arduino.
- LED strip library (if applicable).

### Python-Side:
- `pyaudio`: To capture system audio input.
- `socket`: For UDP communication.
- `datetime`: For logging timestamps.

---

## Troubleshooting

- **ESP32 does not connect to Wi-Fi**:
  - Verify your Wi-Fi credentials in `keys.h`.
  - Check if the Wi-Fi network is operational and within range.

- **No audio received on ESP32**:
  - Ensure the IP address and port in the Python script match the ESP32's settings.
  - Check for UDP packet logs in the ESP32 Serial Monitor.
  - Verify your computer and ESP32 are on the same Wi-Fi network.

- **Audio quality issues**:
  - Reduce the `CHUNK` size in the Python script for smaller UDP packets.
  - Check the i2s buffer for latency test.
  - Ensure your network has low latency and sufficient bandwidth.

---

## Future Improvements

- Build the UI!
- Device discovery protocol...
- Implement error correction or retransmission for lost packets.
- Add UDP reliability layer.
- Extend the firmware to control an LED strip synchronized with the audio data.
- Add support for multiple audio channels, better sample rates/ codec. Maybe adaptive.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Acknowledgments

- [PyAudio Library](https://pypi.org/project/PyAudio/)

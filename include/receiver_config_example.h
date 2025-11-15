// WiFi Configuration
const char* ssid = "somewifi";
const char* password = "somepassword";

// Network Configuration
#define PORT 6666
#define ACK_ENABLED true
#define ACK_TIMEOUT_MS 100

// Device Discovery Configuration
#define DISCOVERY_PORT 6667          // Port for device discovery protocol
#define DEVICE_NAME "Vest"           // Device name for discovery
#define DISCOVERY_BROADCAST_INTERVAL 5000  // Broadcast interval in milliseconds
#define DISCOVERY_ENABLED true       // Enable device discovery

// Audio Configuration
#define SAMPLE_RATE 8000          // Sample rate in Hz (8000, 16000, 22050, 44100, 48000)
#define SAMPLE_BITS 16            // Bits per sample (16 or 32)
#define BUFFER_SIZE 512           // Audio buffer size in bytes
#define NUM_BUFFERS 16            // Number of circular buffers
#define BUFFER_THRESHOLD 2        // Minimum buffers before starting playback

// I2S Configuration
#define I2S_NUM (i2s_port_t)0
#define I2S_BCK_IO GPIO_NUM_4     // I2S Bit Clock (SCK)
#define I2S_WS_IO GPIO_NUM_5      // I2S Word Select (WS/LR Clock)
#define I2S_DO_IO GPIO_NUM_9      // I2S Data Output
#define I2S_SD_MODE (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX)
#define I2S_DMA_BUF_COUNT 4       // DMA buffer count
#define I2S_DMA_BUF_LEN 512       // DMA buffer length
#define I2S_USE_APLL false        // Use Audio PLL
#define I2S_TX_DESC_AUTO_CLEAR true

// NeoPixel LED Configuration
#define NEOPIXEL_PIN 48
#define NUM_PIXELS 1
#define LED_BRIGHTNESS 255

// Serial Configuration
#define SERIAL_BAUD 9600
#define SERIAL_TIMEOUT 1000

// WiFi Connection Settings
#define WIFI_CONNECT_TIMEOUT 20   // Timeout in 500ms increments (20 * 500ms = 10 seconds)
#define WIFI_RECONNECT_DELAY 1000 // Delay before restart on disconnect (ms)
#define WIFI_SCAN_DELAY 10        // Delay between network scans (ms)

// Audio Playback Settings
#define TONE_FREQUENCY 440        // Frequency for test tone in Hz
#define PLAYBACK_INTERVAL_MULTIPLIER 4  // Base interval multiplier
#define ADAPTIVE_PLAYBACK_ENABLED true  // Enable adaptive playback based on buffer fullness

// Status LED Colors (RGB)
#define LED_COLOR_NOT_CONNECTED_R 255
#define LED_COLOR_NOT_CONNECTED_G 0
#define LED_COLOR_NOT_CONNECTED_B 0

#define LED_COLOR_CONNECTED_R 0
#define LED_COLOR_CONNECTED_G 255
#define LED_COLOR_CONNECTED_B 0

#define LED_COLOR_PLAYING_R 0
#define LED_COLOR_PLAYING_G 0
#define LED_COLOR_PLAYING_B 255

#define LED_COLOR_BUFFER_FULL_R 255
#define LED_COLOR_BUFFER_FULL_G 165
#define LED_COLOR_BUFFER_FULL_B 0

#define LED_COLOR_INITIAL_R 50
#define LED_COLOR_INITIAL_G 0
#define LED_COLOR_INITIAL_B 0

// Buffer Management
#define BUFFER_FULL_THRESHOLD_PERCENT 66    // Play multiple chunks when buffer > 66% full
#define BUFFER_MODERATE_THRESHOLD_PERCENT 50 // Play two chunks when buffer > 50% full
#define BUFFER_CHECK_INTERVAL_MS 500        // Interval for resetting packet counter

// Audio Validation
#define VALIDATE_AUDIO_DATA true            // Validate incoming audio data
#define MIN_AUDIO_AMPLITUDE 0               // Minimum non-zero samples required

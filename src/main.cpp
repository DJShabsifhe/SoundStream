#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// Which you should have in your /include folder
#include "receiver_config.h"

// Circular buffer structure
struct AudioBuffer {
    char data[BUFFER_SIZE];
    int length;
    bool filled;
};

// Circular buffer management
AudioBuffer audioBuffers[NUM_BUFFERS];
volatile int writeIndex = 0;
volatile int readIndex = 0;
volatile int buffersAvailable = 0;

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

static unsigned int data_received_times = 0;
WiFiUDP udp;

void setup_i2s(); 

bool wifi_connected = false;

void setup() {
    Serial.begin(SERIAL_BAUD);
    
    strip.begin();
    strip.setPixelColor(0, strip.Color(LED_COLOR_INITIAL_R, LED_COLOR_INITIAL_G, LED_COLOR_INITIAL_B));
    strip.setBrightness(LED_BRIGHTNESS);
    strip.show();

    // First, scan for networks
    Serial.println("Scanning for WiFi networks...");
    int n = WiFi.scanNetworks();
    bool network_found = false;
    
    if (n == 0) {
        Serial.println("No networks found!");
    } else {
        Serial.printf("%d networks found\n", n);
        for (int i = 0; i < n; ++i) {
            if (WiFi.SSID(i) == String(ssid)) {
                network_found = true;
                Serial.printf("Target network '%s' found! Signal strength: %d dBm\n", ssid, WiFi.RSSI(i));
                break;
            }
            delay(WIFI_SCAN_DELAY);
        }
    }

    if (!network_found) {
        Serial.printf("Could not find network '%s'. Please check SSID spelling.\n", ssid);
        Serial.println("Available networks:");
        for (int i = 0; i < n; ++i) {
            Serial.printf("%d: %s (%d dBm)\n", i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
            delay(WIFI_SCAN_DELAY);
        }
        Serial.println("Restarting in 10 seconds...");
        delay(10000);
        ESP.restart();
    }

    // Try to connect
    Serial.printf("Attempting to connect to '%s'...\n", ssid);
    WiFi.disconnect(true);  // Disconnect from any previous connections
    WiFi.mode(WIFI_STA);   // Set to station mode
    delay(100);
    WiFi.begin(ssid, password);
    
    // Wait for connection with timeout
    int timeout_counter = 0;
    while (WiFi.status() != WL_CONNECTED && timeout_counter < WIFI_CONNECT_TIMEOUT) {
        delay(500);
        Serial.print(".");
        timeout_counter++;
        
        if (timeout_counter % 10 == 0) {
            Serial.println();
            int status = WiFi.status();
            Serial.printf("Still trying to connect... WiFi status: %d\n", status);
            switch(status) {
                case WL_IDLE_STATUS:
                    Serial.println("Idle");
                    break;
                case WL_NO_SSID_AVAIL:
                    Serial.println("Cannot find the target network");
                    break;
                case WL_SCAN_COMPLETED:
                    Serial.println("Scan completed");
                    break;
                case WL_CONNECT_FAILED:
                    Serial.println("Connect failed - Check your password");
                    break;
                case WL_CONNECTION_LOST:
                    Serial.println("Connection was lost");
                    break;
                case WL_DISCONNECTED:
                    Serial.println("Disconnected from network");
                    break;
                default:
                    Serial.println("Unknown status");
            }
        }
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("Connected to WiFi! IP address: ");
        Serial.println(WiFi.localIP());
        Serial.printf("SSID: %s, Signal Strength (RSSI): %d dBm\n", WiFi.SSID().c_str(), WiFi.RSSI());
        
        // Only initialize audio after WiFi is connected
        setup_i2s();
        
        // Initialize circular buffer
        for (int i = 0; i < NUM_BUFFERS; i++) {
            audioBuffers[i].filled = false;
        }
        
        strip.setPixelColor(0, strip.Color(LED_COLOR_CONNECTED_R, LED_COLOR_CONNECTED_G, LED_COLOR_CONNECTED_B)); // Green = connected
        strip.show();
        wifi_connected = true;
    } else {
        Serial.println("Failed to connect to WiFi! Please check your credentials or WiFi availability.");
        Serial.printf("Last WiFi Status: %d\n", WiFi.status());
        strip.setPixelColor(0, strip.Color(LED_COLOR_NOT_CONNECTED_R, LED_COLOR_NOT_CONNECTED_G, LED_COLOR_NOT_CONNECTED_B)); // Red = connection failed
        strip.show();
        // Restart the ESP32 after connection failure
        Serial.println("Restarting ESP32...");
        delay(WIFI_RECONNECT_DELAY);
        ESP.restart();
    }

    // Start UDP
    udp.begin(PORT);
    Serial.printf("Listening on UDP port %d\n", PORT);
}

void setup_i2s() {
    i2s_config_t i2s_config = {
        .mode = I2S_SD_MODE,
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = (SAMPLE_BITS == 16) ? I2S_BITS_PER_SAMPLE_16BIT : I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = I2S_DMA_BUF_COUNT,
        .dma_buf_len = I2S_DMA_BUF_LEN,
        .use_apll = I2S_USE_APLL,
        .tx_desc_auto_clear = I2S_TX_DESC_AUTO_CLEAR,
        .fixed_mclk = 0
    }; 

    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_BCK_IO,
        .ws_io_num = I2S_WS_IO,
        .data_out_num = I2S_DO_IO,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    // start I2S
    i2s_driver_install(I2S_NUM, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_NUM, &pin_config);
    i2s_set_clk(I2S_NUM, SAMPLE_RATE, SAMPLE_BITS, I2S_CHANNEL_STEREO);
    Serial.printf("I2S initialized. Rate: %d, Bits: %d\n", SAMPLE_RATE, SAMPLE_BITS);
}

bool add_to_buffer(char* buffer, int len) {
    if (buffersAvailable >= NUM_BUFFERS) {
        return false;  // Buffer full
    }

    // Validate buffer length for stereo 16-bit samples
    if (len % 4 != 0) {
        Serial.printf("Warning: Invalid buffer length %d, truncating to %d\n", len, (len / 4) * 4);
        len = (len / 4) * 4;
    }

    // Validate sample values
    if (VALIDATE_AUDIO_DATA) {
        int16_t* samples = (int16_t*)buffer;
        int num_samples = len / 2;
        bool valid_audio = false;
        
        for (int i = 0; i < num_samples && !valid_audio; i++) {
            int16_t sample = samples[i];
            // Check if sample is non-zero (above noise threshold)
            if (sample > MIN_AUDIO_AMPLITUDE || sample < -MIN_AUDIO_AMPLITUDE) {
                valid_audio = true;
            }
        }
        
        if (!valid_audio) {
            Serial.println("Warning: Received silent or invalid audio data");
            return false;
        }
    }

    // Copy data to the next write buffer
    memcpy(audioBuffers[writeIndex].data, buffer, len);
    audioBuffers[writeIndex].length = len;
    audioBuffers[writeIndex].filled = true;
    
    writeIndex = (writeIndex + 1) % NUM_BUFFERS;
    buffersAvailable++;
    
    return true;
}

void sound_play() {
    static bool is_playing = false;

    if (buffersAvailable == 0 || !audioBuffers[readIndex].filled) {
        if (is_playing) {
            // Was playing but now stopped - show green
            strip.setPixelColor(0, strip.Color(LED_COLOR_CONNECTED_R, LED_COLOR_CONNECTED_G, LED_COLOR_CONNECTED_B));
            strip.show();
            is_playing = false;
        }
        return;  // No data to play
    }

    // Start playing - show blue
    if (!is_playing) {
        strip.setPixelColor(0, strip.Color(LED_COLOR_PLAYING_R, LED_COLOR_PLAYING_G, LED_COLOR_PLAYING_B));
        strip.show();
        is_playing = true;
    }

    AudioBuffer* currentBuffer = &audioBuffers[readIndex];
        
    size_t wrote = 0;
    i2s_write(I2S_NUM, currentBuffer->data, currentBuffer->length, &wrote, portMAX_DELAY);
    
    if (wrote != currentBuffer->length) {
        Serial.printf("Warning: Only wrote %d of %d bytes\n", wrote, currentBuffer->length);
    }

    // Mark buffer as empty and move to next
    audioBuffers[readIndex].filled = false;
    readIndex = (readIndex + 1) % NUM_BUFFERS;
    buffersAvailable--;
}

void play_continuous_tone() {
    if (!wifi_connected) return;  // Don't play if not connected
    
    static unsigned long last_tone_time = 0;
    static bool tone_state = false;
    unsigned long current_time = millis();

    if (current_time - last_tone_time >= (1000 / TONE_FREQUENCY) / 2) {
        last_tone_time = current_time;
        tone_state = !tone_state;

        char tone_buffer[BUFFER_SIZE];
        memset(tone_buffer, tone_state ? 0x7F : 0x80, sizeof(tone_buffer)); // Generate square wave
        sound_play();
    }
}

void loop() {
    // Check WiFi connection status
    if (!wifi_connected || WiFi.status() != WL_CONNECTED) {
        wifi_connected = false;
        strip.setPixelColor(0, strip.Color(LED_COLOR_NOT_CONNECTED_R, LED_COLOR_NOT_CONNECTED_G, LED_COLOR_NOT_CONNECTED_B)); // Red = not connected
        strip.show();
        Serial.println("WiFi disconnected! Restarting...");
        delay(WIFI_RECONNECT_DELAY);
        ESP.restart();
        return;
    }

    static unsigned long last_play_time = 0;
    char buffer[BUFFER_SIZE];
    int packetSize = udp.parsePacket();

    // Handle incoming data
    if (packetSize) {
        int len = udp.read(buffer, BUFFER_SIZE);
        if (len > 0 && len == packetSize) {
            if (add_to_buffer(buffer, len)) {
                data_received_times++;
                // Ack
                if (ACK_ENABLED) {
                    udp.beginPacket(udp.remoteIP(), udp.remotePort());
                    udp.write((const uint8_t *)"OK", 2);
                    udp.endPacket();
                }
            } else {
                Serial.println("Buffer full, dropping packet");
                strip.setPixelColor(0, strip.Color(LED_COLOR_BUFFER_FULL_R, LED_COLOR_BUFFER_FULL_G, LED_COLOR_BUFFER_FULL_B)); // Orange = buffer full
                strip.show();
            }
        }
    }

    // Handle playback timing
    unsigned long current_time = millis();
    unsigned long target_interval = (1000 * BUFFER_SIZE) / (SAMPLE_RATE * PLAYBACK_INTERVAL_MULTIPLIER);
    
    if (current_time - last_play_time >= target_interval) {
        last_play_time = current_time;
        
        if (ADAPTIVE_PLAYBACK_ENABLED) {
            // Adaptive playback based on buffer fullness
            if (buffersAvailable > NUM_BUFFERS * BUFFER_FULL_THRESHOLD_PERCENT / 100) {
                // Buffer is getting full, play multiple chunks
                for (int i = 0; i < 3; i++) {
                    sound_play();
                }
                // Reduce interval temporarily
                target_interval = (1000 * BUFFER_SIZE) / (SAMPLE_RATE * 6);
            }
            else if (buffersAvailable > NUM_BUFFERS * BUFFER_MODERATE_THRESHOLD_PERCENT / 100) {
                // Buffer is moderately full, play two chunks
                for (int i = 0; i < 2; i++) {
                    sound_play();
                }
                // Slightly reduced interval
                target_interval = (1000 * BUFFER_SIZE) / (SAMPLE_RATE * 5);
            }
            else if (buffersAvailable >= BUFFER_THRESHOLD || data_received_times > 0) {
                sound_play();
                // Normal interval
                target_interval = (1000 * BUFFER_SIZE) / (SAMPLE_RATE * PLAYBACK_INTERVAL_MULTIPLIER);
            } else {
                // Output silence if no data
                char silent_buffer[BUFFER_SIZE] = {0};
                add_to_buffer(silent_buffer, BUFFER_SIZE);
                sound_play();
                Serial.println("Outputting silent sound");
            }
        } else {
            // Simple playback mode
            if (buffersAvailable >= BUFFER_THRESHOLD || data_received_times > 0) {
                sound_play();
            }
        }
    }

    // Reset counter periodically
    static unsigned long last_check = 0;
    if (current_time - last_check > BUFFER_CHECK_INTERVAL_MS) {
        last_check = current_time;
        data_received_times = 0;
    }
}
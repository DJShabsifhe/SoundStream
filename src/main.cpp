#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

#include "keys.h"

#define PORT 6666
#define SAMPLE_RATE (16000)
#define SAMPLE_BITS (16)
#define I2S_NUM (i2s_port_t)0
#define I2S_BCK_IO (GPIO_NUM_4)
#define I2S_WS_IO (GPIO_NUM_5)
#define I2S_DO_IO (GPIO_NUM_9)
#define BUFFER_SIZE (1024)

#define PIN         48
#define NUM_PIXELS  1

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUM_PIXELS, PIN, NEO_GRB + NEO_KHZ800);

static unsigned int data_received_times = 0;
WiFiUDP udp;

void setup_i2s(); 

void setup() {
    Serial.begin(9600);
    setup_i2s();

    strip.begin();
    strip.show();

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("Connected to Wi-Fi");

    // Start UDP
    udp.begin(PORT);
    Serial.printf("Listening on UDP port %d\n", PORT);
}

void setup_i2s() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_MSB,
        .intr_alloc_flags = 0, // Set this to 0 or appropriate flags
        .dma_buf_count = 64,
        .dma_buf_len = 256,
        .use_apll = false,
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

void sound_play(char* buffer, int len) {
    size_t wrote = 0;
    i2s_write(I2S_NUM, buffer, len, &wrote, portMAX_DELAY);
}

void loop() {
    char buffer[BUFFER_SIZE];
    int packetSize = udp.parsePacket();

    if (packetSize) {
        int len = udp.read(buffer, BUFFER_SIZE);
        if (len > 0) {
            buffer[len] = 0; // Null-terminate the buffer
            sound_play(buffer, len);
            data_received_times++;

            strip.setPixelColor(0, strip.Color(0, 0, 255));
            strip.show();

            // Print received data to serial
            Serial.printf("Received %d bytes: ", len);
            for (int i = 0; i < len; i++) {
                Serial.printf("%02X ", (unsigned char)buffer[i]); // in hex format
            }
            Serial.println();

            // Ack
            udp.beginPacket(udp.remoteIP(), udp.remotePort());
            udp.write((const uint8_t *)"OK", 2); // Send "OK" as a byte array
            udp.endPacket();
            Serial.printf("Acknowledgment sent for %d bytes\n", len);
        }

        strip.setPixelColor(0, strip.Color(0, 0, 0));
        strip.show();
    }

    // Check for receive
    static unsigned long last_check = 0;
    if (millis() - last_check > 500) {
        last_check = millis();
        if (data_received_times == 0) {
            char silent_buffer[BUFFER_SIZE] = {0};
            sound_play(silent_buffer, sizeof(silent_buffer));
            Serial.println("Outputting silent sound");
        }
        data_received_times = 0; // Reset for the next interval
    }
}
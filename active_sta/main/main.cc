#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_spi_flash.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "lwip/err.h"
#include "lwip/sys.h"

#include "../../_components/nvs_component.h"
#include "../../_components/sd_component.h"
#include "../../_components/csi_component.h"
#include "../../_components/time_component.h"
#include "../../_components/input_component.h"
#include "../../_components/sockets_component.h"

/*
 * ESP32-S3 CSI Transmitter (Station Mode)
 *
 * IMPORTANT: This device (STA) must match the AP (receiver) configuration:
 *   1. CHANNEL: Must match AP's channel exactly (check WIFI_CHANNEL below)
 *   2. SSID: Must match AP's SSID exactly
 *   3. PASSWORD: Must match AP's password
 *   4. AP_IP: Must be set to the AP's IP address (default: 192.168.4.1)
 *
 * The examples use WiFi configuration that you can set via 'idf.py menuconfig'.
 *
 * If you'd rather not, just change the below entries to strings with
 * the config you want - ie #define ESP_WIFI_SSID "mywifissid"
 */
#define ESP_WIFI_SSID      CONFIG_ESP_WIFI_SSID
#define ESP_WIFI_PASS      CONFIG_ESP_WIFI_PASSWORD

// AP IP address for UDP transmission (default ESP32 AP IP)
#ifdef CONFIG_AP_IP_ADDR
#define AP_IP_ADDR         CONFIG_AP_IP_ADDR
#else
#define AP_IP_ADDR         "192.168.4.1"
#endif

#ifdef CONFIG_WIFI_CHANNEL
#define WIFI_CHANNEL CONFIG_WIFI_CHANNEL
#else
#define WIFI_CHANNEL 6
#endif

#ifdef CONFIG_SHOULD_COLLECT_CSI
#define SHOULD_COLLECT_CSI 1
#else
#define SHOULD_COLLECT_CSI 0
#endif

#ifdef CONFIG_SHOULD_COLLECT_ONLY_LLTF
#define SHOULD_COLLECT_ONLY_LLTF 1
#else
#define SHOULD_COLLECT_ONLY_LLTF 0
#endif

#ifdef CONFIG_SEND_CSI_TO_SERIAL
#define SEND_CSI_TO_SERIAL 1
#else
#define SEND_CSI_TO_SERIAL 0
#endif

#ifdef CONFIG_SEND_CSI_TO_SD
#define SEND_CSI_TO_SD 1
#else
#define SEND_CSI_TO_SD 0
#endif

static int s_retry_num = 0;
static const int MAX_RETRY = 10;

/* FreeRTOS event group to signal when we are connected*/
static EventGroupHandle_t s_wifi_event_group;

/* The event group allows multiple bits for each event, but we only care about one event
 * - are we connected to the AP with an IP? */
const int WIFI_CONNECTED_BIT = BIT0;

static const char *TAG = "Active CSI collection (Station)";

esp_err_t _http_event_handle(esp_http_client_event_t *evt) {
    switch (evt->event_id) {
        case HTTP_EVENT_ON_DATA:
            ESP_LOGI(TAG, "HTTP_EVENT_ON_DATA, len=%d", evt->data_len);
            if (!esp_http_client_is_chunked_response(evt->client)) {
                if (!real_time_set) {
                    char *data = (char *) malloc(evt->data_len + 1);
                    strncpy(data, (char *) evt->data, evt->data_len);
                    data[evt->data_len] = '\0';
                    time_set(data);
                    free(data);
                }
            }
            break;
        default:
            break;
    }
    return ESP_OK;
}

//// en_sys_seq: see https://github.com/espressif/esp-idf/blob/master/docs/api-guides/wifi.rst#wi-fi-80211-packet-send for details
esp_err_t esp_wifi_80211_tx(wifi_interface_t ifx, const void *buffer, int len, bool en_sys_seq);

static void event_handler(void* arg, esp_event_base_t event_base,
                          int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Station started, connecting to AP...");
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t* event = (wifi_event_sta_disconnected_t*) event_data;

        // Log disconnect reason for debugging
        const char* reason_str;
        switch (event->reason) {
            case WIFI_REASON_AUTH_EXPIRE:          reason_str = "AUTH_EXPIRE"; break;
            case WIFI_REASON_AUTH_LEAVE:           reason_str = "AUTH_LEAVE"; break;
            case WIFI_REASON_ASSOC_EXPIRE:         reason_str = "ASSOC_EXPIRE"; break;
            case WIFI_REASON_ASSOC_TOOMANY:        reason_str = "ASSOC_TOOMANY"; break;
            case WIFI_REASON_NOT_AUTHED:           reason_str = "NOT_AUTHED"; break;
            case WIFI_REASON_NOT_ASSOCED:          reason_str = "NOT_ASSOCED"; break;
            case WIFI_REASON_ASSOC_LEAVE:          reason_str = "ASSOC_LEAVE"; break;
            case WIFI_REASON_ASSOC_NOT_AUTHED:     reason_str = "ASSOC_NOT_AUTHED"; break;
            case WIFI_REASON_DISASSOC_PWRCAP_BAD:  reason_str = "DISASSOC_PWRCAP_BAD"; break;
            case WIFI_REASON_DISASSOC_SUPCHAN_BAD: reason_str = "DISASSOC_SUPCHAN_BAD"; break;
            case WIFI_REASON_IE_INVALID:           reason_str = "IE_INVALID"; break;
            case WIFI_REASON_MIC_FAILURE:            reason_str = "MIC_FAILURE"; break;
            case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT: reason_str = "4WAY_HANDSHAKE_TIMEOUT"; break;
            case WIFI_REASON_GROUP_KEY_UPDATE_TIMEOUT: reason_str = "GROUP_KEY_UPDATE_TIMEOUT"; break;
            case WIFI_REASON_IE_IN_4WAY_DIFFERS:   reason_str = "IE_IN_4WAY_DIFFERS"; break;
            case WIFI_REASON_GROUP_CIPHER_INVALID: reason_str = "GROUP_CIPHER_INVALID"; break;
            case WIFI_REASON_PAIRWISE_CIPHER_INVALID: reason_str = "PAIRWISE_CIPHER_INVALID"; break;
            case WIFI_REASON_AKMP_INVALID:         reason_str = "AKMP_INVALID"; break;
            case WIFI_REASON_UNSUPP_RSN_IE_VERSION: reason_str = "UNSUPP_RSN_IE_VERSION"; break;
            case WIFI_REASON_INVALID_RSN_IE_CAP:   reason_str = "INVALID_RSN_IE_CAP"; break;
            case WIFI_REASON_802_1X_AUTH_FAILED:   reason_str = "802_1X_AUTH_FAILED"; break;
            case WIFI_REASON_CIPHER_SUITE_REJECTED: reason_str = "CIPHER_SUITE_REJECTED"; break;
            case WIFI_REASON_INVALID_PMKID:        reason_str = "INVALID_PMKID"; break;
            case WIFI_REASON_BEACON_TIMEOUT:       reason_str = "BEACON_TIMEOUT"; break;
            case WIFI_REASON_NO_AP_FOUND:           reason_str = "NO_AP_FOUND"; break;
            case WIFI_REASON_AUTH_FAIL:            reason_str = "AUTH_FAIL"; break;
            case WIFI_REASON_ASSOC_FAIL:           reason_str = "ASSOC_FAIL"; break;
            case WIFI_REASON_HANDSHAKE_TIMEOUT:    reason_str = "HANDSHAKE_TIMEOUT"; break;
            case WIFI_REASON_CONNECTION_FAIL:      reason_str = "CONNECTION_FAIL"; break;
            case WIFI_REASON_AP_TSF_RESET:         reason_str = "AP_TSF_RESET"; break;
            case WIFI_REASON_ROAMING:              reason_str = "ROAMING"; break;
            default:                               reason_str = "UNKNOWN";
        }

        ESP_LOGW(TAG, "Disconnected from AP, reason: %d (%s)", event->reason, reason_str);

        // Specific troubleshooting hints based on disconnect reason
        switch (event->reason) {
            case WIFI_REASON_NO_AP_FOUND:
                ESP_LOGE(TAG, "TROUBLESHOOT: AP '%s' not found! Check: 1) AP is powered on, 2) Channel %d matches AP channel", ESP_WIFI_SSID, WIFI_CHANNEL);
                break;
            case WIFI_REASON_AUTH_FAIL:
                ESP_LOGE(TAG, "TROUBLESHOOT: Authentication failed! Check password matches AP password");
                break;
            case WIFI_REASON_HANDSHAKE_TIMEOUT:
            case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
                ESP_LOGE(TAG, "TROUBLESHOOT: Handshake timeout! Check password and security settings match AP");
                break;
            case WIFI_REASON_ASSOC_FAIL:
                ESP_LOGE(TAG, "TROUBLESHOOT: Association failed! AP may have reached max connections (check MAX_STA_CONN)");
                break;
            case WIFI_REASON_BEACON_TIMEOUT:
                ESP_LOGW(TAG, "TROUBLESHOOT: Beacon timeout - signal weak or AP too far/turned off");
                break;
        }

        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT);

        // Exponential backoff for reconnection
        int delay_ms = 2000;
        if (s_retry_num > 5) {
            delay_ms = 5000;
        }
        if (s_retry_num > MAX_RETRY) {
            ESP_LOGW(TAG, "Max retries reached, waiting longer before retry...");
            delay_ms = 10000;
            s_retry_num = 0;
        }
        s_retry_num++;

        ESP_LOGI(TAG, "Retrying connection in %d ms... (attempt %d)", delay_ms, s_retry_num);
        vTaskDelay(delay_ms / portTICK_PERIOD_MS);
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got ip:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0; // Reset retry counter on successful connection
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED) {
        wifi_event_sta_connected_t* event = (wifi_event_sta_connected_t*) event_data;
        ESP_LOGI(TAG, "Connected to AP SSID:%s channel:%d", ESP_WIFI_SSID, event->channel);
    }
}

bool is_wifi_connected() {
    return (xEventGroupGetBits(s_wifi_event_group) & WIFI_CONNECTED_BIT);
}

void station_init() {
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());

    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_sta_config_t wifi_sta_config = {};
    wifi_sta_config.channel = WIFI_CHANNEL;
    // Set scan method to fast scan for quicker connection
    wifi_sta_config.scan_method = WIFI_FAST_SCAN;
    // Set minimum RSSI to -100 (accept weaker signals)
    wifi_sta_config.threshold.rssi = -100;
    // Use all auth modes for compatibility
    wifi_sta_config.threshold.authmode = WIFI_AUTH_WPA_WPA2_PSK;

    wifi_config_t wifi_config = {
            .sta = wifi_sta_config,
    };

    strlcpy((char *) wifi_config.sta.ssid, ESP_WIFI_SSID, sizeof(ESP_WIFI_SSID));
    strlcpy((char *) wifi_config.sta.password, ESP_WIFI_PASS, sizeof(ESP_WIFI_PASS));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    // Disable power saving — critical for stable CSI packet flow
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    ESP_LOGI(TAG, "Station init complete. SSID:%s channel:%d target_AP:%s",
             ESP_WIFI_SSID, WIFI_CHANNEL, AP_IP_ADDR);
}

TaskHandle_t xHandle = NULL;

void vTask_socket_transmitter_sta_loop(void *pvParameters) {
    for (;;) {
        socket_transmitter_sta_loop(&is_wifi_connected, AP_IP_ADDR);
    }
}

void config_print() {
    printf("\n\n");
    printf("╔═══════════════════════════════════════════════════════════╗\n");
    printf("║        ESP32 CSI Tool - STATION (Transmitter)           ║\n");
    printf("╠═══════════════════════════════════════════════════════════╣\n");
    printf("║  PROJECT_NAME: ACTIVE_STA                                 ║\n");
    printf("║  IDF_VER: %s\n", IDF_VER);
    printf("╠═══════════════════════════════════════════════════════════╣\n");
    printf("║  ⚠️  CRITICAL: Ensure AP uses the SAME CHANNEL!          ║\n");
    printf("║  WIFI_CHANNEL: %d                                         ║\n", WIFI_CHANNEL);
    printf("║  ESP_WIFI_SSID: %s\n", ESP_WIFI_SSID);
    printf("║  AP_IP_ADDR: %s                                         ║\n", AP_IP_ADDR);
    printf("║  PACKET_RATE: %i packets/sec                            ║\n", CONFIG_PACKET_RATE);
    printf("╠═══════════════════════════════════════════════════════════╣\n");
    printf("║  SHOULD_COLLECT_CSI: %d                                   ║\n", SHOULD_COLLECT_CSI);
    printf("║  SHOULD_COLLECT_ONLY_LLTF: %d                             ║\n", SHOULD_COLLECT_ONLY_LLTF);
    printf("║  SEND_CSI_TO_SERIAL: %d                                 ║\n", SEND_CSI_TO_SERIAL);
    printf("║  SEND_CSI_TO_SD: %d                                       ║\n", SEND_CSI_TO_SD);
    printf("╚═══════════════════════════════════════════════════════════╝\n");
    printf("\n\n");
}

extern "C" void app_main() {
    config_print();
    nvs_init();
    sd_init();
    station_init();
    csi_init((char *) "STA");

#if !(SHOULD_COLLECT_CSI)
    printf("CSI will not be collected. Check `idf.py menuconfig  # > ESP32 CSI Tool Config` to enable CSI");
#endif

    xTaskCreatePinnedToCore(&vTask_socket_transmitter_sta_loop, "socket_transmitter_sta_loop",
                            10000, (void *) &is_wifi_connected, 100, &xHandle, 1);
}

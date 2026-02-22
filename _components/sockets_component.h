#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include <esp_http_server.h>

char *data = (char *) "1\n";

void socket_transmitter_sta_loop(bool (*is_wifi_connected)(), const char* ap_ip) {
    if (ap_ip == NULL) {
        ap_ip = "192.168.4.1";
    }

    int socket_fd = -1;
    int consecutive_errors = 0;
    const int MAX_CONSECUTIVE_ERRORS = 50;

    while (1) {
        close(socket_fd);
        socket_fd = -1;
        char *ip = (char *) ap_ip;
        struct sockaddr_in caddr;
        caddr.sin_family = AF_INET;
        caddr.sin_port = htons(2223);

        // Wait for WiFi connection
        int wifi_wait_count = 0;
        while (!is_wifi_connected()) {
            printf("[SOCKET] WiFi not connected. Waiting... (%d sec)\n", wifi_wait_count);
            vTaskDelay(1000 / portTICK_PERIOD_MS);
            wifi_wait_count++;
        }
        printf("[SOCKET] WiFi connection established.\n");

        if (inet_aton(ap_ip, &caddr.sin_addr) == 0) {
            printf("[SOCKET] ERROR: inet_aton failed for IP %s\n", ap_ip);
            vTaskDelay(1000 / portTICK_PERIOD_MS);
            continue;
        }

        socket_fd = socket(PF_INET, SOCK_DGRAM, 0);
        if (socket_fd == -1) {
            printf("[SOCKET] ERROR: Socket creation failed [%s]\n", strerror(errno));
            vTaskDelay(1000 / portTICK_PERIOD_MS);
            continue;
        }

        // Set socket timeout for sending
        struct timeval tv;
        tv.tv_sec = 1;
        tv.tv_usec = 0;
        setsockopt(socket_fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

        printf("[SOCKET] Starting to send frames to %s:2223\n", ip);
        consecutive_errors = 0;
        double lag = 0.0;

        while (1) {
            double start_time = get_steady_clock_timestamp();

            if (!is_wifi_connected()) {
                printf("[SOCKET] WiFi disconnected, pausing transmission...\n");
                break;
            }

            ssize_t sent = sendto(socket_fd, data, strlen(data), 0,
                                  (const struct sockaddr *) &caddr, sizeof(caddr));

            if (sent < 0) {
                consecutive_errors++;
                if (consecutive_errors >= MAX_CONSECUTIVE_ERRORS) {
                    printf("[SOCKET] Too many consecutive errors (%d), reconnecting socket...\n", consecutive_errors);
                    break;
                }
                vTaskDelay(10 / portTICK_PERIOD_MS);
                continue;
            } else if (sent != (ssize_t)strlen(data)) {
                printf("[SOCKET] WARNING: Partial send (%zd/%zu bytes)\n", sent, strlen(data));
            } else {
                consecutive_errors = 0; // Reset on successful send
            }

#if defined CONFIG_PACKET_RATE && (CONFIG_PACKET_RATE > 0)
            double wait_duration = (1000.0 / CONFIG_PACKET_RATE) - lag;
            int w = (wait_duration > 0) ? (int)wait_duration : 1;
            vTaskDelay(w / portTICK_PERIOD_MS);
#else
            vTaskDelay(10 / portTICK_PERIOD_MS); // ~100 packets/sec
#endif
            double end_time = get_steady_clock_timestamp();
            lag = end_time - start_time;
        }

        printf("[SOCKET] Socket loop ended, reconnecting in 1 second...\n");
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
}

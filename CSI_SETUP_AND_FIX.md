# CSI Setup & Transmitter Crash Fix

## If you see: `This chip is ESP32-S3(beta3) not ESP32-S3(beta2). Wrong --chip argument?`

Your board is an **ESP32-S3(beta3)** revision, but the project was built for **esp32s3beta2**. Two options:

**Option A – Use project defaults (already set for beta3)**  
This repo’s `active_ap/sdkconfig.defaults` sets `CONFIG_IDF_TARGET_ESP32S3_BETA_VERSION_3=y`. Recreate config and build so it takes effect:

```bash
cd /Users/sagardubey/Desktop/ESP32/ESP32-CSI-Tool/active_ap
idf.py fullclean
idf.py --preview set-target esp32s3
idf.py build
idf.py -p /dev/tty.usbmodem101 flash monitor
```

**Option B – Switch in menuconfig (no fullclean)**  
If you already have a build for esp32s3:

```bash
idf.py menuconfig
```

Go to **Espressif IoT Development Framework** (top level) → **ESP32-S3 beta version** → choose **ESP32-S3 beta3** → Save (S), Quit (Q). Then:

```bash
idf.py build
idf.py -p /dev/tty.usbmodem101 flash monitor
```

Use your actual port instead of `tty.usbmodem101` if different.

---

## If you see: `Invalid head of packet (0x50)` when flashing

This usually happens **after** "Stub running" / "Changing baud rate to 460800" — the serial link is unstable at the default high baud rate. Try flashing at a **lower baud rate**:

```bash
idf.py -p /dev/tty.usbmodem101 -b 115200 flash monitor
```

If it still fails, try an even lower rate:

```bash
idf.py -p /dev/tty.usbmodem101 -b 57600 flash monitor
```

Also: use a good USB cable, avoid hubs if possible, and close any other app using the same serial port (e.g. another terminal with monitor open).

**If it fails during "Connecting..." (never reaches "Stub running"):**  
The chip may not be entering the ROM bootloader — you may be reading app serial output instead of sync packets (hence "Invalid head of packet" with different bytes each time).

- **Erase first, then flash:** Put the board in download mode (hold BOOT → press RESET → release BOOT), then *immediately* run (from `active_ap/build`):
  ```bash
  python $IDF_PATH/components/esptool_py/esptool/esptool.py -p /dev/cu.usbmodem101 -b 9600 --chip esp32s3beta3 --before no_reset_no_sync --after no_reset erase_flash
  ```
  If erase succeeds, run the normal flash command (with `default_reset`); the chip will have no app and should stay in bootloader on reset.
- Use the **cu** device instead of **tty** (on Mac this can be more reliable):  
  `idf.py -p /dev/cu.usbmodem101 -b 57600 flash`
- List ports: `ls /dev/tty.usb* /dev/cu.usb*` — if you see two (e.g. usbmodem101 and usbserial-xxx), try the other one.
- Increase connection attempts (run from `active_ap/build`):
  ```bash
  python $IDF_PATH/components/esptool_py/esptool/esptool.py -p /dev/cu.usbmodem101 -b 9600 --chip esp32s3beta3 --connect-attempts 15 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_freq 80m --flash_size 2MB 0x0 bootloader/bootloader.bin 0x8000 partition_table/partition-table.bin 0x10000 active-ap.bin
  ```
- If the board has a **BOOT** button: hold **BOOT**, run the flash command, and when you see "Connecting..." press **RESET** once, then release **BOOT** after ~1 second.

**If it still fails at "Configuring flash size..." or similar:** Put the board in download mode manually, then flash without reset:

1. Hold the **BOOT** (or **IO0**) button.
2. Press and release **RESET** (or **EN**).
3. Release **BOOT**.
4. From the **build** directory, run esptool directly (board already in download mode):
   ```bash
   cd /Users/sagardubey/Desktop/ESP32/ESP32-CSI-Tool/active_ap/build
   $IDF_PATH/components/esptool_py/esptool/esptool.py -p /dev/tty.usbmodem101 -b 57600 --chip esp32s3beta3 --before no_reset_no_sync --after hard_reset write_flash --flash_mode dio --flash_freq 80m --flash_size 2MB 0x0 bootloader/bootloader.bin 0x8000 partition_table/partition-table.bin 0x10000 active-ap.bin
   ```
   (Use `$IDF_PATH` from your environment after running `source $HOME/esp/esp-idf/export.sh`, or replace it with the full path to esp-idf.) If your board has no BOOT button, try another USB cable/port or a different machine.

---

## If you see: `This chip is ESP32-S3(beta3) not ESP32. Wrong --chip argument?`

Your board is an **ESP32-S3**, but the project was built for **esp32**. In ESP-IDF v4.3, esp32s3 is a preview target, so you must use `--preview` when setting the target:

```bash
cd /Users/sagardubey/Desktop/ESP32/ESP32-CSI-Tool/active_ap
idf.py --preview set-target esp32s3
idf.py build
idf.py -p /dev/tty.usbmodem101 flash monitor
```

Use your actual port instead of `tty.usbmodem101` if different. After this, the build and flash will use the correct ESP32-S3 chip type. If you then see the beta2 vs beta3 error, follow the “ESP32-S3(beta3) not ESP32-S3(beta2)” section above.

---

## If you see: `E (618) wifi: CSI not enabled in menuconfig!`

The transmitter (AP) is crashing because the **Wi-Fi component** was built without CSI support. Enable it and reflash.

---

## Fix transmitter (active_ap)

### 1. Enable CSI in menuconfig (required)

```bash
cd /Users/sagardubey/Desktop/ESP32/ESP32-CSI-Tool/active_ap
idf.py menuconfig
```

In menuconfig:

1. **Component config** → **Wi-Fi**
2. Find **"WiFi CSI(Channel State Information)"**
3. Press **Space** or **Y** to enable it (show `[*]`)
4. **S** to save, **Q** to quit

**Note:** This repo’s `active_ap/sdkconfig.defaults` already sets `CONFIG_ESP32_WIFI_CSI_ENABLED=y`. If you run a **full clean** and reconfigure, CSI will be enabled by default. If you already have an existing `sdkconfig`, you must enable it once in menuconfig as above.

### 2. WiFi credentials (this project)

- Menu: **ESP32 CSI Tool Config** (not "Example Configuration")
- Set **WiFi SSID** and **WiFi Password** to match your setup (e.g. `ESP32_CSI_AP` / `hackathon2026`, or keep `myssid` / `mypassword`). Receivers must use the **same** SSID/password.

### 3. Rebuild and reflash transmitter

```bash
idf.py fullclean
idf.py build
idf.py -p /dev/tty.usbmodem5AB90777761 flash monitor
```

(Replace the port with your TX board’s port.)

After flashing you should see something like:

- `softap_init finished. SSID:... password:...`
- No "CSI not enabled" error; the board should stay up.

---

## Receivers: use `active_sta`, not `passive_sta`

This repo has **no** `passive_sta` folder. Use:

- **active_ap** = transmitter (AP)
- **active_sta** = receivers (stations that connect to the AP and get CSI)

For each receiver:

```bash
cd /Users/sagardubey/Desktop/ESP32/ESP32-CSI-Tool/active_sta
idf.py menuconfig
```

- Go to **ESP32 CSI Tool Config**
- Set **WiFi SSID** and **WiFi Password** to the **same** as the transmitter (e.g. `ESP32_CSI_AP` / `hackathon2026`, or `myssid` / `mypassword`)
- Save (S), Quit (Q)

Then build and flash each receiver (one at a time, each on its own port):

```bash
idf.py build
idf.py -p /dev/tty.usbmodem[RX_PORT] flash
```

---

## Quick reference

| Role       | Project folder | Menu for SSID/Password   |
|-----------|----------------|---------------------------|
| Transmitter (AP) | `active_ap`    | ESP32 CSI Tool Config     |
| Receivers (STA)  | `active_sta`   | ESP32 CSI Tool Config     |

CSI for the Wi-Fi driver: **Component config → Wi-Fi → WiFi CSI(Channel State Information)** (enable for `active_ap`; enable for `active_sta` if you want CSI on the station side as well).

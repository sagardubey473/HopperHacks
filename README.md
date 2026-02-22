# ESP32 CSI Tool

Through-wall human presence detection using WiFi Channel State Information (CSI) and camera-based pose estimation. Two ESP32-S3 microcontrollers form a WiFi transmitter-receiver pair. When a person disturbs the WiFi signal path — even through walls — the system detects their presence using a combination of signal processing, deep learning, and computer vision.

How It Works                                                                                                                                                                                                                                          
  A Station (TX) sends WiFi packets at 100 pkt/s. An Access Point (RX) extracts CSI — amplitude and phase across 64 subcarrier frequencies — from every received frame. Three detection systems run in parallel:
  1. Threshold Detector — Sliding window variance vs. calibrated empty-room baseline. Sub-second response.
  2. CNN (CSINet) — 4-layer convolutional neural network (147K params) classifies 52x400 CSI spectrograms as "empty" or "present." Trained on through-wall research data, 100% test accuracy.
  3. MediaPipe Pose — USB webcam at ~23 FPS tracking 33 skeletal landmarks.
  A fusion state machine combines all three into:
  - VISIBLE (green) — Camera sees the person
  - OCCLUDED (orange) — Person behind a wall, detected by WiFi CSI
  - ABSENT (gray) — No one detected
  Hardware Requirements
  - 2x ESP32-S3 development boards
  - USB webcam
  - 2 computers (one per ESP32)
  Setup
  ESP32 Firmware
  Both boards use https://docs.espressif.com/projects/esp-idf/en/release-v4.4/esp32/get-started/index.html.
  AP (Receiver) — Computer 1:
  source ~/esp/esp-idf/export.sh
  cd active_ap
  idf.py set-target esp32s3
  idf.py build flash monitor -p /dev/cu.usbmodem101
  STA (Transmitter) — Computer 2:
  source ~/esp/esp-idf/export.sh
  cd active_sta
  idf.py set-target esp32s3
  idf.py build flash monitor -p /dev/cu.usbmodem101
  Default config: SSID ESP32_CSI_AP, password hackathon2026, channel 6.
  Python Environment (AP Computer)
  python3 -m venv csi_env
  source csi_env/bin/activate
  pip install -r python_utils/requirements.txt
  Usage
  Fusion Dashboard (Camera + CSI + CNN)
  source csi_env/bin/activate
  python python_utils/fusion_dashboard.py --port /dev/cu.usbmodem101
  Controls:
  - c — Start/stop calibration (keep area empty during calibration)
  - q — Quit
  Options:
  ┌────────────────────┬──────────────────────────────────────────────────┐
  │        Flag        │                   Description                    │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --port PORT        │ Serial port (required)                           │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --baud BAUD        │ Baud rate (default: 921600)                      │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --camera INDEX     │ Camera index (default: 0)                        │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --no-camera        │ CSI-only mode, no webcam                         │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --no-cnn           │ Disable CNN, threshold-only detection            │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --cnn-interval SEC │ CNN inference interval (default: 1.0)            │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --model-path PATH  │ Custom CNN model weights                         │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --load-calibration │ Load previous calibration on startup             │
  ├────────────────────┼──────────────────────────────────────────────────┤
  │ --expected-rate N  │ Expected pkt/s for rate indicator (default: 100) │
  └────────────────────┴──────────────────────────────────────────────────┘
  Train the CNN Model
  # Binary presence detection (recommended)
  python python_utils/train_model.py --dataset DP_NLOS --binary --epochs 100
  # Multi-class room detection
  python python_utils/train_model.py --dataset DP_NLOS --epochs 100
  # Activity recognition
  python python_utils/train_model.py --dataset DA_NLOS --epochs 100
  # Evaluate a saved model
  python python_utils/train_model.py --dataset DP_NLOS --binary --evaluate models/best_DP_NLOS_binary.pt
  Other Tools
  # Check CSI packet rate
  python python_utils/serial_rate_check.py --port /dev/cu.usbmodem101
  # Explore training dataset
  python python_utils/explore_dataset.py --dataset DP_NLOS
  # Basic CSI dashboard (no camera/CNN)
  python python_utils/realtime_dashboard.py --port /dev/cu.usbmodem101
  Project Structure
  WallSense/
  ├── active_ap/                  # ESP32 Access Point firmware (CSI receiver)
  ├── active_sta/                 # ESP32 Station firmware (packet transmitter)
  ├── _components/                # Shared ESP-IDF components (CSI callback, sockets)
  ├── models/                     # Trained CNN weights and training curves
  │   ├── best_DP_NLOS_binary.pt  # Binary presence model (100% test acc)
  │   ├── best_DP_NLOS.pt         # 6-class room detection model
  │   └── best_DA_NLOS.pt         # Activity recognition model
  ├── data/                       # CSI recordings and training datasets
  │   ├── DP_NLOS/                # Through-wall presence spectrograms
  │   ├── DA_NLOS/                # Through-wall activity spectrograms
  │   └── calibration.json        # Saved calibration data
  └── python_utils/
      ├── fusion_dashboard.py     # Main dashboard (camera + CSI + CNN)
      ├── fusion_state.py         # Fusion state machine (VISIBLE/OCCLUDED/ABSENT)
      ├── camera_processor.py     # MediaPipe Pose background thread
      ├── cnn_detector.py         # CNN adapter for live CSI inference
      ├── train_model.py          # CSINet training pipeline
      ├── presence_detector.py    # Threshold-based CSI detector
      ├── csi_processing.py       # CSI parsing, I/Q to amplitude, sliding window
      ├── realtime_dashboard.py   # Basic CSI-only dashboard
      ├── serial_rate_check.py    # Packet rate verification tool
      ├── explore_dataset.py      # Dataset visualization
      └── requirements.txt        # Python dependencies
  CNN Architecture
  Input: (1, 52, 400) — 52 subcarriers × 400 time steps
  Conv2d(1→16, 3×3) → BatchNorm → ReLU → MaxPool(2)    → 16 × 26 × 200
  Conv2d(16→32, 3×3) → BatchNorm → ReLU → MaxPool(2)    → 32 × 13 × 100
  Conv2d(32→64, 3×3) → BatchNorm → ReLU → MaxPool(2)    → 64 × 6 × 50
  Conv2d(64→128, 3×3) → BatchNorm → ReLU → AdaptiveAvg  → 128 × 1 × 1
  Flatten → Linear(128→256) → ReLU → Dropout(0.5)
         → Linear(256→64)  → ReLU → Dropout(0.3)
         → Linear(64→2)    → Softmax → [Empty, Present]
  Total: 147,234 parameters
  Pre-trained Model Results
  ┌────────────────────────┬─────────────────────────────────┬───────────────┐
  │         Model          │              Task               │ Test Accuracy │
  ├────────────────────────┼─────────────────────────────────┼───────────────┤
  │ best_DP_NLOS_binary.pt │ Present vs Empty (through-wall) │ 100%          │
  ├────────────────────────┼─────────────────────────────────┼───────────────┤
  │ best_DP_NLOS.pt        │ Room localization (6-class)     │ 100%          │
  ├────────────────────────┼─────────────────────────────────┼───────────────┤
  │ best_DA_NLOS.pt        │ Activity recognition (3-class)  │ 60.5%         │
  └────────────────────────┴─────────────────────────────────┴───────────────┘
  Built With
  - ESP-IDF v4.4.7
  - PyTorch
  - MediaPipe
  - OpenCV
  - matplotlib
  - NumPy
  Acknowledgments
  Built on top of https://stevenmhernandez.github.io/ESP32-CSI-Tool/ by Steven M. Hernandez. Training data from the https://zenodo.org/.

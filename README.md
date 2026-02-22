Detect humans through walls using WiFi signals and camera pose tracking.                                                                                                                                                                        
                                                          
  What It Does                                                                                                                                                                                                                                    
                                                          
  Two ESP32-S3 boards create a WiFi link. When a person walks between them — even through a wall — their body disturbs the WiFi signal. Three systems detect this in parallel:
  
  1. Threshold Detector — Compares live WiFi signal variance against an empty-room baseline
  2. CNN Model — A 4-layer neural network classifies WiFi spectrograms as "empty" or "present" (100% test accuracy)
  3. Camera Pose Tracking — MediaPipe tracks 33 skeletal landmarks at ~23 FPS
  A fusion state machine combines them into three states:
  - VISIBLE — Camera sees the person
  - OCCLUDED — Camera lost them, WiFi still detects them through the wall
  - ABSENT — No one detected
  
  Hardware
  - 2x ESP32-S3 boards
  - USB webcam
  - 2 computers
  
  Quick Start
  Flash the ESP32s (one per computer):
  
  source ~/esp/esp-idf/export.sh
  
  cd active_ap   # or active_sta on the other computer
  
  idf.py set-target esp32s3
  
  idf.py build flash monitor -p /dev/cu.usbmodem101
  
  Run the dashboard (on the AP computer):
  
  python3 -m venv csi_env
  
  source csi_env/bin/activate
  
  pip install -r python_utils/requirements.txt
  
  python python_utils/fusion_dashboard.py --port /dev/cu.usbmodem101
  
  Press c to calibrate (keep the area empty), then walk around and behind walls.
  
  Project Structure

  
  WallSense/
  ├── active_ap/              # AP firmware (WiFi receiver)
  
  ├── active_sta/             # Station firmware (WiFi transmitter)
  
  ├── models/                 # Trained CNN weights
  
  ├── data/                   # Training datasets and CSI recordings
  
  └── python_utils/
      
      ├── fusion_dashboard.py # Main dashboard (camera + CSI + CNN)
      
      ├── fusion_state.py     # Fusion state machine
      
      ├── camera_processor.py # MediaPipe Pose thread
      
      ├── cnn_detector.py     # CNN adapter for live inference
      
      ├── train_model.py      # CNN training pipeline
      
      ├── presence_detector.py# Threshold-based detector
      
      └── csi_processing.py   # CSI parsing and feature extraction
  
  CNN Architecture
  Input: 52 WiFi subcarriers x 400 time steps
  
  Conv(1->16) -> Conv(16->32) -> Conv(32->64) -> Conv(64->128)
  
  Each with BatchNorm, ReLU, and Pooling
  
  Classifier: 128 -> 256 -> 64 -> 2 (Empty vs Present)
  
  147,234 parameters

  
  Built With
  
  ESP-IDF v4.4.7, PyTorch, MediaPipe, OpenCV, matplotlib, NumPy

  
  Acknowledgments
  
  Built on ESP32 CSI Tool by Steven M. Hernandez. Training data from Zenodo.


# Distributed Smart Office Architecture (Mac Brain + Raspberry Pi Actuator)

## 1. System Overview
```
┌────────────────────────────────┐       WiFi (HTTP/RTSP)      ┌─────────────────────────────────────────────────────┐
│    iPhone 8 (Vantage Point)    │ ──────────────────────────> │                   MAC (AI Brain)                    │
│ • DroidCam / IP WebCam App     │                             │ • Ingests stream & auto-resizes to 640x480          │
│ • Bottom-right vantage point   │                             │ • YOLOv8 real-time inference (30-60 FPS)            │
└────────────────────────────────┘                             │ • 6th Floor Zone Mapping (Bays 1-4 & Cabins)        │
                                                               │ • Energy & Sustainability Analytics (₹9.50/kWh)     │
                                                               │ • Interactive Web Dashboard (Port 8000)             │
                                                               └─────────────────────────────────────────────────────┘
                                                                                          │
                                                                                          │ Local WebSocket / REST
                                                                                          │ (Sub-5ms, Zero Lag)
                                                                                          ▼
                                                               ┌─────────────────────────────────────────────────────┐
                                                               │         RASPBERRY PI (Edge Actuator & Sensors)       │
                                                               │ • Lightweight client: `scripts/pi_relay_client.py`  │
                                                               │ • Controls 4/8-channel Relay Modules (220V/12V)     │
                                                               │ • Reads PIR Sensors for Conference & Manager Cabin  │
                                                               └─────────────────────────────────────────────────────┘
```

---

## 2. Why This is the "Smart Way"
1. **Solves Pi Overheating & FPS Bottlenecks:**
   - Pi 4 CPU throttles at 80°C and drops to 1–2 FPS under heavy PyTorch/YOLO compute.
   - Mac (Apple Silicon Neural Engine / M-Series GPU) runs YOLOv8 at **30–60+ FPS** effortlessly.
2. **Solves Pi Storage & pip Failures:**
   - The Pi only needs a lightweight Python client (`pip install websocket-client`). No 4GB CUDA wheels or PyTorch required.
3. **Dedicated Physical I/O:**
   - The Pi is rock-solid at hardware GPIO switching (<1ms latency) and reading digital PIR motion sensors.

---

## 3. GPIO Pin Mapping Table

### A. Relay Outputs (Active-Low)
| Zone | Appliance | Switch ID | BCM GPIO | Physical Board Pin |
|---|---|---|---|---|
| **Bay 1** | Overhead Lights | `RELAY_LGT_BAY_1` | **GPIO 17** | Pin 11 |
| **Bay 1** | Central HVAC AC | `RELAY_AC_BAY_1` | **GPIO 27** | Pin 13 |
| **Bay 2** | Overhead Lights | `RELAY_LGT_BAY_2` | **GPIO 22** | Pin 15 |
| **Bay 2** | Central HVAC AC | `RELAY_AC_BAY_2` | **GPIO 23** | Pin 16 |
| **Bay 3** | Overhead Lights | `RELAY_LGT_BAY_3` | **GPIO 24** | Pin 18 |
| **Bay 3** | Central HVAC AC | `RELAY_AC_BAY_3` | **GPIO 25** | Pin 22 |
| **Bay 4** | Overhead Lights | `RELAY_LGT_BAY_4` | **GPIO 5** | Pin 29 |
| **Bay 4** | Central HVAC AC | `RELAY_AC_BAY_4` | **GPIO 6** | Pin 31 |
| **Conference** | Downlights | `RELAY_LGT_CONF` | **GPIO 12** | Pin 32 |
| **Conference** | Split AC | `RELAY_AC_CONF` | **GPIO 13** | Pin 33 |
| **Manager** | Cabin Light | `RELAY_LGT_MGR` | **GPIO 16** | Pin 36 |

### B. PIR Motion Sensor Inputs (Non-Camera Privacy Zones)
| Zone | Sensor Type | Target Zone ID | BCM GPIO | Physical Board Pin |
|---|---|---|---|---|
| **Conference Room** | Digital PIR Motion Sensor | `conf_room` | **GPIO 21** | Pin 40 |
| **Manager Cabin** | Digital PIR Motion Sensor | `manager_cabin` | **GPIO 4** | Pin 7 |

---

## 4. How to Run

### Step 1: Start Central Server on Mac
1. Find your Mac's Local IP address:
   ```bash
   ipconfig getifaddr en0
   # Example output: 192.168.1.100
   ```
2. Start the vision & dashboard server:
   ```bash
   # Running with iPhone DroidCam feed:
   python run.py --source http://<IPHONE_IP>:4747/video

   # Or running with live simulation:
   python run.py --source synthetic
   ```
   Open `http://localhost:8000` to view the live dashboard.

---

### Step 2: Start Edge Actuator on Raspberry Pi
1. In the Pi terminal, clone/pull the repo:
   ```bash
   cd ~/Desktop/techathon-26
   git pull origin main
   ```
2. Install the lightweight WebSocket client (takes 2 seconds, no PyTorch required!):
   ```bash
   pip install websocket-client
   ```
3. Run the relay & sensor client:
   ```bash
   # Connect to your Mac's IP on port 8000:
   python3 scripts/pi_relay_client.py --server http://192.168.1.100:8000
   ```
4. For testing without physical relays wired yet, add `--mock`:
   ```bash
   python3 scripts/pi_relay_client.py --server http://192.168.1.100:8000 --mock
   ```

---

## 5. DroidCam Resolution Question
- **No paid app needed**: DroidCam default stream resolution is completely fine.
- **Handled in Code**: Our threaded capture pipeline in `src/video_stream.py` automatically reads incoming frames in a background thread and resizes them down to 640x480 before YOLOv8 inference. This eliminates buffer lag and keeps the video buttery smooth at 30+ FPS!

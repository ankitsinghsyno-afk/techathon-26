# EcoFloor AI ⚡🏢
### AI-Powered Smart Office Sustainability & Energy Management System

> **Hackathon Solution**: Intelligent zone-based occupancy detection, smart electrical switch automation, and real-time sustainability analytics for IT offices.

---

## 🌟 The Problem & Solution
In large IT office floors, lighting and HVAC are often wired in broad sweeps. When only **one team** is working late or occupying a single bay, lighting across the entire floor remains powered, leading to massive electricity waste, high operational costs, and unnecessary carbon emissions.

**EcoFloor AI** uses open-source computer vision (**YOLOv8**) to detect human presence, maps occupants' ground positions to configurable floor plan zones, and automatically switches off lights and appliances in vacant bays while keeping occupied bays energized.

---

## 🚀 Key Features
- **Open-Source Person Detection**: Ultralytics YOLOv8 for real-time person detection and feet ground-contact mapping.
- **Dynamic 2D Floor Plan Zoning**: Scaled polygon zoning mapping camera coordinates directly to office bays (Engineering Bays, Conference Rooms, Lounges).
- **Anti-Flicker Debounce Filtering**: Configurable hold timer (e.g. 8s) prevents annoying switch flickers when employees move or bend down.
- **Plug-and-Play IoT Switch Integration**: Designed for zero electrical rewiring using standard micro-relays (Shelly Plus 1, Sonoff Mini, ESP32) inside existing switchboards.
- **Real-Time Sustainability Dashboard**:
  - Live AI camera feed with bounding boxes, zone overlays, and ground contact indicators.
  - Interactive top-down 2D floor plan highlighting active vs standby bays.
  - Live Energy & Carbon Metrics: Power draw (Watts), Watts saved, cumulative kWh, cost savings (₹), and avoided CO₂ emissions.
  - One-click presentation scenarios to demonstrate the problem statement in seconds.

---

## 📂 Project Structure
```
techathon-26/
├── config/
│   └── default_zones.json       # Configurable office bays, appliances & polygons
├── docs/
│   └── ARCHITECTURE.md          # Technical architecture & relay wiring guide
├── frontend/
│   └── index.html               # Modern high-performance interactive dashboard
├── src/
│   ├── detector.py              # YOLOv8 human detection & feet coordinate extractor
│   ├── energy_tracker.py        # Power, cost (₹) and CO2 reduction engine
│   ├── models.py                # Pydantic domain models
│   ├── pipeline.py              # Orchestration loop (Vision -> Zoning -> Relays -> Analytics)
│   ├── server.py                # FastAPI, WebSockets & MJPEG video streaming server
│   ├── switch_controller.py     # Micro-relay IoT controller (Mock, MQTT, HTTP)
│   ├── video_stream.py          # Video input handler (Synthetic sim, Webcam, RTSP)
│   └── zone_manager.py          # Ray-casting point-in-polygon & debounce logic
├── tests/
│   ├── test_api.py              # FastAPI endpoint tests
│   ├── test_energy_tracker.py   # Energy & carbon metrics tests
│   └── test_zone_manager.py     # Point-in-polygon & debouncing tests
├── run.py                       # Application entry point
└── requirements.txt             # Pinned Python dependencies
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+ (macOS, Linux, or Windows)
- Webcam (optional) or use the built-in synthetic office simulator

### 2. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Launch the Server
```bash
# Launch with synthetic office simulation (recommended for hackathon presentations):
./venv/bin/python run.py

# Or launch with your laptop's built-in webcam:
./venv/bin/python run.py --source 0

# Or connect to an office RTSP CCTV camera:
./venv/bin/python run.py --source rtsp://admin:password@192.168.1.50:554/stream1
```

### 4. Open the Dashboard
Open your browser at:
**[http://localhost:8000](http://localhost:8000)**

---

## 🎯 Live Presentation Scenarios
On the dashboard, click any of the preset scenario buttons to immediately demonstrate the AI system in action:
1. **"Only Team A Working"** *(Target Prompt Scenario)*: Occupants are placed in Bay Alpha (Frontend Team). All other bays (Backend, QA, Conference 3A, Cafeteria) automatically turn lights OFF, saving **>5,000 Watts** instantly!
2. **"Only Team B Working"**: Isolates Bay Beta while keeping other bays in energy-saving standby.
3. **"Meeting in Conf 3A"**: Activates conference room display and lights while keeping unused bays dark.
4. **"All Vacant (Off Hours)"**: Simulates end-of-day; switches off 100% of lighting fixtures.

---

## 🧪 Running Tests
```bash
./venv/bin/python -m pytest tests/
```
All 7 unit and integration tests verify point-in-polygon math, debounce hold times, energy calculations, and API endpoints.

---

## 🔌 Hardware Integration (Zero-Rewiring)
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full circuit diagrams showing how **Shelly Plus 1** or **Sonoff Mini** micro-relays fit behind standard wall switches, allowing software automation while retaining manual switch operation.

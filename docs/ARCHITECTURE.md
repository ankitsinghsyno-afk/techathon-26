# EcoFloor AI — System Architecture & Implementation Guide

## 1. Executive Summary
EcoFloor AI is an AI-powered, IoT-integrated Energy and Sustainability Management System designed for large-scale IT office floors. 

In large office layouts, when only a single project team is working overtime or sitting in a dedicated bay, traditional lighting circuits keep entire floor wings illuminated. EcoFloor AI solves this by:
1. Detecting people in real-time using open-source Computer Vision (**Ultralytics YOLOv8**).
2. Projecting feet/ground contact points `((x1+x2)/2, y2)` to calibrated 2D floor zones.
3. Automatically switching off lighting and HVAC in vacant bays while preserving power in occupied bays.
4. Integrating directly with existing wall switches using **plug-and-play IoT micro-relays** (Shelly, Sonoff, ESP32) without electrical rewiring.
5. Providing an executive dashboard displaying live floor occupancy, power savings, and carbon reduction metrics.

---

## 2. End-to-End Pipeline Architecture

```
[ CCTV / Camera Feed / RTSP ]
              │
              ▼
[ YOLOv8 Person Detector ] ───> Extract Bounding Box [x1, y1, x2, y2]
              │
              ▼
[ Ground Contact Calculator ] ─> Feet Point (fx = (x1+x2)/2, fy = y2)
              │
              ▼
[ Point-in-Polygon Engine ] ───> Ray-casting pointPolygonTest against Zone Polygons
              │
              ▼
[ Zone State Machine ] ────────> Debounce Hold Timer (8s anti-flicker policy)
              │
              ├───> [ IoT Switch Controller ] ──> MQTT / HTTP Relay (Shelly/Sonoff/ESP32)
              │
              └───> [ Energy & Carbon Engine ] ─> Watts Saved, kWh, ₹ Cost, kg CO2e
                          │
                          ▼
            [ FastAPI + WebSockets + MJPEG ]
                          │
                          ▼
       [ Interactive Executive Floor Map Dashboard ]
```

---

## 3. Floor Plan & Zone Mapping Technique

### Why Feet Ground-Contact Mapping?
A person walking or sitting occupies 3D space. Bounding box centers `(x_center, y_center)` often hover in the air and lead to false zone classification if a camera has an angled perspective. 

EcoFloor AI calculates the **ground contact point**:
$$\text{feet\_x} = \frac{x_1 + x_2}{2}, \quad \text{feet\_y} = y_2$$

This contact coordinate is tested against zone polygons using the Ray-Casting algorithm (`src/zone_manager.py`).

### Anti-Flicker Debounce Policy
If an employee bends down to tie their shoe or is momentarily occluded behind a pillar, lighting must **not** flicker off immediately. Each zone implements a configurable hold timer (`debounce_seconds = 8s` by default). Lights stay energized during momentary dropouts and switch off only after the timer elapses.

---

## 4. Plug-and-Play IoT Switch Integration (No Rewiring)

The system is designed to integrate with existing office wall switches without requiring conduit modifications or running new building cables:

### Micro-Relay Architecture (e.g. Shelly Plus 1 / Sonoff Mini / ESP32)
1. **Physical Retrofit**: Micro-relays are placed inside existing electrical wall switchboards behind the faceplate.
2. **Wiring Hookup**:
   - The live phase supply connects to relay `L`.
   - The original physical toggle switch wire is connected to relay input `SW`.
   - The appliance feed connects to relay output `O`.
3. **Dual Control**:
   - Facility managers or staff can still toggle the physical wall switch manually.
   - The micro-relay's onboard firmware (MQTT/HTTP) allows EcoFloor AI to command state toggles over the local office IoT WiFi or Zigbee network.

```
       [ Existing Phase Line (L) ]
                    │
            ┌───────┴────────┐
            │   Micro-Relay   │ <─── [ EcoFloor AI Server (MQTT/REST) ]
            │ (Shelly/Sonoff) │
            └───┬────────┬───┘
                │        │
   [ Existing Switch ]   └──> [ Overhead LED Fixture ]
       (SW input)
```

---

## 5. Sustainability & Carbon Metrics Formulation

- **Real-Time Power Draw**:
  $$P_{\text{active}} = \sum_{z \in \text{Zones}} \sum_{a \in \text{Appliances}_z} a_{\text{wattage}} \times \mathbb{I}(a_{\text{active}})$$

- **Power Saved**:
  $$P_{\text{saved}} = P_{\text{baseline}} - P_{\text{active}}$$

- **Energy Conserved (kWh)**:
  $$E_{\text{saved}} = \int \frac{P_{\text{saved}}(t)}{1000} \, dt$$

- **Cost Savings**:
  $$\text{Cost Saved} = E_{\text{saved}} \times \text{Rate}_{\text{commercial}} \quad (\text{Default: } ₹9.50/\text{kWh})$$

- **Carbon Avoided (kg CO₂e)**:
  $$\text{CO}_2 = E_{\text{saved}} \times 0.82 \, \text{kg CO}_2\text{e/kWh}$$

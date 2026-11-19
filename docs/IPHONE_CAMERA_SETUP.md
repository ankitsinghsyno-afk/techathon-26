# Using iPhone 8 as a Wireless AI Camera for EcoFloor

You can turn your **iPhone 8** into an overhead or wall-mounted AI camera streaming wirelessly over your office Wi-Fi.

---

## 📱 Recommended Free Apps (from iOS App Store)

### Option 1: DroidCam Webcam (Fastest & Simplest)
1. On your iPhone 8, open the App Store and install **DroidCam Webcam**.
2. Connect the iPhone 8 to the **same Wi-Fi network** as your laptop.
3. Open the DroidCam app on your iPhone.
4. The screen will display:
   ```text
   WiFi IP: 192.168.1.45   (example)
   Port: 4747
   ```
5. Your streaming URL is:
   ```text
   http://192.168.1.45:4747/video
   ```

---

### Option 2: IP Camera Lite
1. Install **IP Camera Lite** (by ShenYao) from the iOS App Store.
2. Connect to the office Wi-Fi and tap **Turn On IP Camera Server** at the bottom.
3. The app shows the stream URL:
   - HTTP MJPEG: `http://<IPHONE_IP>:8081/video`
   - RTSP Stream: `rtsp://<IPHONE_IP>:8554/live`

---

## 🚀 How to Connect to EcoFloor AI

### Method A: Via the Web Dashboard (Live Switching)
1. Start the server:
   ```bash
   ./venv/bin/python run.py
   ```
2. Open **[http://localhost:8000](http://localhost:8000)**.
3. In the top-right header, click **Camera Source**.
4. Select **iPhone / Wireless IP Camera / RTSP**.
5. Paste your URL (e.g. `http://192.168.1.45:4747/video`) and click **Apply Source**.
6. The AI vision feed will switch to your iPhone wirelessly and begin running YOLOv8 person detection!

### Method B: Launching directly via Terminal CLI
```bash
./venv/bin/python run.py --source http://192.168.1.45:4747/video
```

---

## 💡 Positioning Tips for Office Floor AI
- **Mount High**: Place the iPhone on a shelf, monitor stand, or ceiling mount angled down at ~30°–45° towards the office bays.
- **Power**: Keep the iPhone plugged into a Lightning charger so the screen and Wi-Fi stream stay active indefinitely.
- **Auto-Lock**: In iPhone Settings > Display & Brightness, set **Auto-Lock to Never** while demoing.

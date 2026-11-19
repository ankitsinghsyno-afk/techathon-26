#!/usr/bin/env python3
"""
Interactive Camera Permission & Test Tool for macOS/Linux/Windows.
Run this script directly in your terminal to trigger the macOS camera permission dialog.
"""
import sys
import time
import cv2

print("=" * 60)
print(" EcoFloor AI — Camera Permission & Hardware Check")
print("=" * 60)
print("Testing webcam index 0 via AVFoundation / V4L2...")

cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Failed to open camera (index 0).")
    print("\nIf you are on macOS:")
    print(" 1. Open: System Settings > Privacy & Security > Camera")
    print(" 2. Ensure your Terminal application (Terminal, iTerm, VS Code, Antigravity) is toggled ON.")
    print(" 3. Re-run this script: ./venv/bin/python scripts/test_camera.py")
    sys.exit(1)

print("✅ Camera connection opened successfully!")
print("Reading test frame...")
ret, frame = cap.read()
if ret and frame is not None:
    print(f"🎉 SUCCESS: Captured test frame ({frame.shape[1]}x{frame.shape[0]} px).")
    print("Camera permission is verified and ready for EcoFloor AI!")
else:
    print("⚠️ Camera opened but could not read frame. Check if another app is using the webcam.")

cap.release()
print("=" * 60)

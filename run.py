#!/usr/bin/env python3
"""
EcoFloor AI — Smart Office Energy & Sustainability Management System.
Entry point to launch the web server and computer vision pipeline.
"""
import argparse
import sys
import os
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Optimize multi-core CPU inference for Raspberry Pi 4 (Cortex-A72 4-core)
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")


def main():
    parser = argparse.ArgumentParser(description="Smart Office AI Energy Management System")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--source", default="synthetic", help="Video source: 'synthetic', '0' for webcam, or rtsp URL")
    args = parser.parse_args()

    print("=" * 70)
    print(" EcoFloor AI — Smart Office Sustainability & Energy Controller")
    print("=" * 70)
    print(f" • Server URL:     http://localhost:{args.port}")
    print(f" • Video Source:   {args.source}")
    print(f" • AI Model:       Ultralytics YOLOv8 (Human Detection & Feet Tracking)")
    print(f" • Floor Plan:     config/default_zones.json")
    print("=" * 70)

    uvicorn.run("src.server:app", host=args.host, port=args.port, reload=False, log_level="info")


if __name__ == "__main__":
    main()

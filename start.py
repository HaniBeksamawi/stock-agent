#!/usr/bin/env python3
"""
Starts both the trading bot and the dashboard web server in parallel.
"""
import subprocess
import sys
import os

def main():
    bot_proc = subprocess.Popen([sys.executable, "bot.py"])
    dash_proc = subprocess.Popen([sys.executable, "dashboard.py"])
    print("✅ Bot + Dashboard started")
    print("📊 Dashboard running on http://localhost:8080")
    try:
        bot_proc.wait()
        dash_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        bot_proc.terminate()
        dash_proc.terminate()

if __name__ == "__main__":
    main()

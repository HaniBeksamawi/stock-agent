import subprocess, sys

def main():
    bot  = subprocess.Popen([sys.executable, "bot.py"])
    dash = subprocess.Popen([sys.executable, "dashboard.py"])
    print("✅ Bot + Dashboard running")
    print("📊 Dashboard: http://localhost:8080")
    try:
        bot.wait(); dash.wait()
    except KeyboardInterrupt:
        bot.terminate(); dash.terminate()

if __name__ == "__main__": main()

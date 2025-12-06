# k Turret Project

## Setup on Raspberry Pi

1. Copy this folder to Pi via USB or SCP (e.g., scp -r grok\_turret\_project pi@your-pi-ip:/home/pi/)
2. On Pi: cd grok\_turret\_project
3. Install: sudo pip3 install -r requirements.txt
4. Run: sudo python3 grok\_turret.py
5. Access UI: http://your-pi-ip or http://raspberrypi.local

## VS Code on Windows for Remote Editing

1. Install VS Code: https://code.visualstudio.com/
2. Install Extension: "Remote - SSH" (Microsoft)
3. Connect: F1 > Remote-SSH: Connect to Host > pi@your-pi-ip (password: raspberry default)
4. Open Folder on Pi: /home/pi/grok\_turret\_project
5. Edit code, run in VS Code terminal: sudo python3 grok\_turret.py

## Hardware Wiring

See pinout.txt for GPIO connections. Use A4988 or TMC2209 drivers, 12V PSU for steppers. Camera optional (USB or Pi Cam).

Troubleshoot:

* No movement: Check wiring, power, EN pins LOW.
* No camera: Modes fall back gracefully.
* Logs: Check Pi terminal for errors.

#!/usr/bin/env python3
from flask import Flask, render_template_string, request, jsonify
import RPi.GPIO as GPIO
import time
import threading
import cv2
import math
from datetime import datetime
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

PAN_STEP, PAN_DIR, PAN_EN = 17, 27, 22
TILT_STEP, TILT_DIR, TILT_EN = 23, 24, 25
LASER = 18

LAT, LON = 40.7128, -74.0060

current_mode = "manual"
stop_event = threading.Event()
mode_thread = None
camera = None
pan = None
tilt = None

def setup_gpio():
    global pan, tilt
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for pin in [PAN_STEP, PAN_DIR, PAN_EN, TILT_STEP, TILT_DIR, TILT_EN, LASER]:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output([PAN_EN, TILT_EN], GPIO.LOW)
        log.info("GPIO initialized")
    except Exception as e:
        log.error(f"GPIO failed: {e}")
        sys.exit(1)

    class Stepper:
        def __init__(self, step_pin, dir_pin):
            self.step = step_pin
            self.dir = dir_pin
            self.current_pos = 0
            self.lock = threading.Lock()

        def move_to(self, target_steps, speed=0.001):
            try:
                with self.lock:
                    steps = int(target_steps - self.current_pos)
                    if steps == 0 or stop_event.is_set(): return
                    direction = GPIO.HIGH if steps > 0 else GPIO.LOW
                    steps = abs(steps)
                    GPIO.output(self.dir, direction)
                    for _ in range(steps):
                        if stop_event.is_set(): break
                        GPIO.output(self.step, GPIO.HIGH)
                        time.sleep(speed/2)
                        GPIO.output(self.step, GPIO.LOW)
                        time.sleep(speed/2)
                    self.current_pos += steps if direction == GPIO.HIGH else -steps
            except Exception as e:
                log.error(f"Stepper error: {e}")

    pan = Stepper(PAN_STEP, PAN_DIR)
    tilt = Stepper(TILT_STEP, TILT_DIR)

def init_camera():
    global camera
    for i in range(3):
        try:
            camera = cv2.VideoCapture(i)
            if camera.isOpened():
                camera.set(3, 640)
                camera.set(4, 480)
                camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                log.info(f"Camera on /dev/video{i}")
                return True
        except:
            continue
    log.warning("No camera — limited modes")
    camera = None
    return False

def mosquito_killer():
    if not camera:
        log.warning("Mosquito mode disabled")
        return
    bg = None
    while current_mode == "mosquito" and not stop_event.is_set():
        try:
            ret, frame = camera.read()
            if not ret: continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if bg is None:
                bg = gray.copy().astype("float")
                continue
            cv2.accumulateWeighted(gray, bg, 0.5)
            delta = cv2.absdiff(gray, cv2.convertScaleAbs(bg))
            thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                c = max(contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] > 1000:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    pan.move_to(pan.current_pos + (cx - 320) * 1.5)
                    tilt.move_to(tilt.current_pos + (cy - 240) * 1.5)
                    if abs(cx - 320) < 40 and abs(cy - 240) < 40:
                        GPIO.output(LASER, GPIO.HIGH)
                        time.sleep(0.15)
                        GPIO.output(LASER, GPIO.LOW)
        except Exception as e:
            log.error(f"Mosquito error: {e}")
        time.sleep(0.03)

def solar_tracking():
    while current_mode == "solar" and not stop_event.is_set():
        try:
            now = datetime.now()
            doy = now.timetuple().tm_yday
            t = now.hour + now.minute/60.0 + now.second/3600.0 + LON/15.0
            decl = 23.45 * math.sin(math.radians(360*(284 + doy)/365))
            ha = 15 * (t - 12)
            if abs(ha) > 120:
                time.sleep(300)
                continue
            zenith = math.degrees(math.acos(
                math.sin(math.radians(LAT))*math.sin(math.radians(decl)) +
                math.cos(math.radians(LAT))*math.cos(math.radians(decl))*math.cos(math.radians(ha))
            ))
            elevation = 90 - zenith
            azimuth = (math.degrees(math.atan2(
                math.sin(math.radians(ha)),
                math.cos(math.radians(ha))*math.sin(math.radians(LAT)) -
                math.tan(math.radians(decl))*math.cos(math.radians(LAT))
            )) + 180) % 360
            pan.move_to(int(azimuth * 5.55))
            tilt.move_to(int(elevation * 5.55))
            time.sleep(60)
        except Exception as e:
            log.error(f"Solar error: {e}")
            time.sleep(10)

def security_scanner():
    while current_mode == "security" and not stop_event.is_set():
        try:
            for a in range(-1000, 1000, 300):
                if current_mode != "security": break
                pan.move_to(a)
                tilt.move_to(0)
                GPIO.output(LASER, GPIO.HIGH)
                time.sleep(0.3)
                GPIO.output(LASER, GPIO.LOW)
                time.sleep(1)
        except Exception as e:
            log.error(f"Security error: {e}")

def laser_etcher():
    while current_mode == "etcher" and not stop_event.is_set():
        try:
            for i in range(0, 360, 15):
                if current_mode != "etcher": break
                x = int(800 * math.sin(math.radians(i)))
                y = int(800 * math.cos(math.radians(i)))
                pan.move_to(x)
                tilt.move_to(y)
                GPIO.output(LASER, GPIO.HIGH)
                time.sleep(0.02)
            GPIO.output(LASER, GPIO.LOW)
            time.sleep(1)
        except Exception as e:
            log.error(f"Etcher error: {e}")

def star_tracker():
    while current_mode == "star" and not stop_event.is_set():
        try:
            pan.move_to(0)
            tilt.move_to(int((90 - LAT) * 22.22))
            time.sleep(300)
        except Exception as e:
            log.error(f"Star error: {e}")

HTML = """<!DOCTYPE html><html><head><title>Grok Turret</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#000;color:#0f0;font-family:monospace;text-align:center;padding:20px;}
button,select{width:90%;padding:20px;margin:10px;font-size:1.8em;background:#001100;color:#0f0;border:3px solid #0f0;border-radius:15px;}
.red{background:#300;color:#f00;}</style>
<script>function setMode(){fetch('/set_mode?mode='+document.getElementById('mode').value).then(r=>r.text()).then(t=>alert(t));}</script>
</head><body><h1>GROK TURRET v3</h1>
<select id="mode" onchange="setMode()">
<option value="manual">Manual Control</option>
<option value="mosquito">Mosquito Killer</option>
<option value="solar">Solar Tracker</option>
<option value="security">Security Scanner</option>
<option value="etcher">Laser Etcher</option>
<option value="star">Star Tracker</option>
</select>
<button onclick="fetch('/left')">LEFT</button><button onclick="fetch('/right')">RIGHT</button>
<button onclick="fetch('/up')">UP</button><button onclick="fetch('/down')">DOWN</button>
<button onclick="fetch('/home')">HOME</button>
<button class="red" onclick="fetch('/stop')">EMERGENCY STOP</button>
</body></html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/set_mode")
def set_mode():
    global current_mode, mode_thread
    try:
        new_mode = request.args.get("mode", "manual")
        stop_event.set()
        time.sleep(0.3)
        stop_event.clear()
        current_mode = new_mode

        if mode_thread and mode_thread.is_alive():
            mode_thread.join(timeout=1.0)

        mode_thread = None
        if current_mode == "mosquito":
            mode_thread = threading.Thread(target=mosquito_killer, daemon=True)
        elif current_mode == "solar":
            mode_thread = threading.Thread(target=solar_tracking, daemon=True)
        elif current_mode == "security":
            mode_thread = threading.Thread(target=security_scanner, daemon=True)
        elif current_mode == "etcher":
            mode_thread = threading.Thread(target=laser_etcher, daemon=True)
        elif current_mode == "star":
            mode_thread = threading.Thread(target=star_tracker, daemon=True)

        if mode_thread:
            mode_thread.start()
        return f"Mode: {current_mode.upper()}"
    except Exception as e:
        return f"Error: {e}"

@app.route("/left")
def left():
    pan.move_to(pan.current_pos - 400)
    return "OK"

@app.route("/right")
def right():
    pan.move_to(pan.current_pos + 400)
    return "OK"

@app.route("/up")
def up():
    tilt.move_to(tilt.current_pos - 400)
    return "OK"

@app.route("/down")
def down():
    tilt.move_to(tilt.current_pos + 400)
    return "OK"

@app.route("/home")
def home():
    pan.move_to(0)
    tilt.move_to(0)
    return "HOMED"

@app.route("/stop")
def stop():
    stop_event.set()
    GPIO.output(LASER, GPIO.LOW)
    return "STOPPED"

if __name__ == "__main__":
    print("\\nGROK TURRET STARTING...")
    setup_gpio()
    init_camera()
    print("TURRET READY → http://raspberrypi.local")
    try:
        app.run(host="0.0.0.0", port=80, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\\nShutting down...")
    finally:
        stop_event.set()
        if camera: camera.release()
        GPIO.cleanup()
        print("Grok Turret offline. Safe shutdown complete.")
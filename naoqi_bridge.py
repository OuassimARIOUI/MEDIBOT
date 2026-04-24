#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
naoqi_bridge.py -- Pont NAOqi Python 2.7

Lance un petit serveur HTTP sur localhost:9560 qui expose les services
Pepper (TTS, LEDs, Motion, Audio) via des endpoints REST simples.

Usage:
    C:\\Python27\\python.exe naoqi_bridge.py

Le processus principal (Python 3.10 / Rasa) communique avec ce bridge
via des requetes HTTP localhost.
"""
import sys
import os
import json
import time
import threading

# Ajouter le SDK NAOqi au path
SDK_PATH = r"C:\Python27\Lib\site-packages\pynaoqi-python2.7-2.8.6.23-win64-vs2015-20191127_152649\lib"
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

import imp
try:
    fp, pathname, description = imp.find_module('qi', [SDK_PATH])
    try:
        qi = imp.load_module('qi', fp, pathname, description)
    finally:
        if fp:
            fp.close()
except ImportError:
    print("[BRIDGE] ERREUR: Module qi introuvable. Verifiez le SDK_PATH.")
    sys.exit(1)

# Python 2.7 HTTP server
try:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler


BRIDGE_PORT = 9560
session = None
tts = None
leds = None
motion = None
audio_device = None
audio_recorder = None
audio_player = None


def connect_pepper(ip, port):
    """Connecte au robot Pepper via NAOqi."""
    global session, tts, leds, motion, audio_device, audio_recorder, audio_player
    session = qi.Session()
    url = "tcp://%s:%s" % (ip, port)
    print("[BRIDGE] Connexion a %s..." % url)
    session.connect(url)
    print("[BRIDGE] Connecte !")

    try:
        tts = session.service("ALTextToSpeech")
        tts.setLanguage("French")
        tts.setParameter("speed", 85)
        print("[BRIDGE] TTS OK")
    except Exception as e:
        print("[BRIDGE] TTS indisponible: %s" % e)

    try:
        leds = session.service("ALLeds")
        print("[BRIDGE] LEDs OK")
    except Exception as e:
        print("[BRIDGE] LEDs indisponible: %s" % e)

    try:
        motion = session.service("ALMotion")
        print("[BRIDGE] Motion OK")
    except Exception as e:
        print("[BRIDGE] Motion indisponible: %s" % e)

    try:
        audio_device = session.service("ALAudioDevice")
        print("[BRIDGE] AudioDevice OK")
    except Exception as e:
        print("[BRIDGE] AudioDevice indisponible: %s" % e)

    try:
        audio_recorder = session.service("ALAudioRecorder")
        print("[BRIDGE] ALAudioRecorder OK")
    except Exception as e:
        print("[BRIDGE] ALAudioRecorder indisponible: %s" % e)

    try:
        audio_player = session.service("ALAudioPlayer")
        print("[BRIDGE] ALAudioPlayer OK")
    except Exception as e:
        print("[BRIDGE] ALAudioPlayer indisponible: %s" % e)


class BridgeHandler(BaseHTTPRequestHandler):
    """Gestionnaire HTTP pour les commandes NAOqi."""

    def log_message(self, format, *args):
        # Silencer les logs HTTP standard
        pass

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        return {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "pepper": session is not None})
        elif self.path == "/status":
            self._send_json({
                "connected": session is not None,
                "tts": tts is not None,
                "leds": leds is not None,
                "motion": motion is not None,
                "recorder": audio_recorder is not None,
                "player": audio_player is not None,
            })
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        try:
            body = self._read_body()

            if self.path == "/tts/say":
                text = body.get("text", "")
                if tts and text:
                    tts.say(text.encode("utf-8") if isinstance(text, unicode) else text)
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False, "reason": "no tts or empty text"})

            elif self.path == "/tts/volume":
                vol = body.get("volume", 0.6)
                if tts:
                    tts.setVolume(float(vol))
                if audio_device:
                    audio_device.setOutputVolume(int(vol * 100))
                self._send_json({"ok": True})

            elif self.path == "/leds/fade":
                group = body.get("group", "FaceLeds")
                color = body.get("color", 0xFFFFFF)
                duration = body.get("duration", 1.0)
                if leds:
                    leds.fadeRGB(str(group), int(color), float(duration))
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False, "reason": "no leds"})

            elif self.path == "/motion/wakeup":
                if motion:
                    motion.wakeUp()
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False})

            elif self.path == "/motion/rest":
                if motion:
                    motion.rest()
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False})

            elif self.path == "/audio/play":
                remote_path = body.get("path")
                if audio_player and remote_path:
                    audio_player.playFile(str(remote_path))
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False})

            elif self.path == "/mic/record":
                remote_path = body.get("path")
                duration = body.get("duration", 4.0)
                if audio_recorder and remote_path:
                    try:
                        audio_recorder.stopMicrophonesRecording()
                    except:
                        pass
                    channels = [0, 0, 1, 0]
                    audio_recorder.startMicrophonesRecording(str(remote_path), "wav", 16000, channels)
                    time.sleep(float(duration))
                    audio_recorder.stopMicrophonesRecording()
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False})

            else:
                self._send_json({"error": "unknown endpoint"}, 404)

        except Exception as e:
            self._send_json({"error": str(e)}, 500)


def main():
    ip = os.environ.get("PEPPER_IP", "192.168.13.228")
    port = int(os.environ.get("PEPPER_PORT", "9559"))

    try:
        connect_pepper(ip, port)
    except Exception as e:
        print("[BRIDGE] ERREUR connexion Pepper: %s" % e)
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", BRIDGE_PORT), BridgeHandler)
    print("[BRIDGE] Serveur HTTP demarre sur http://127.0.0.1:%d" % BRIDGE_PORT)
    print("[BRIDGE] Endpoints: /tts/say, /leds/fade, /motion/wakeup, /mic/record, /audio/play, /health")
    print("[BRIDGE] Ctrl+C pour arreter")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\n[BRIDGE] Arret.")
        server.server_close()


if __name__ == "__main__":
    main()

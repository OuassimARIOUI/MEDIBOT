# -*- coding: utf-8 -*-
"""
qi.py -- Drop-in replacement pour NAOqi SDK (Python 3 compatible).

Ce module simule l'interface `qi` attendue par le code Python 3.
En arriere-plan, il communique avec `naoqi_bridge.py` (qui tourne
en Python 2.7) via des requetes HTTP REST sur localhost:9560.

Cela permet au code existant (Rasa, voice_bridge, etc.) de controler
Pepper sans aucune modification !
"""
import requests
import time
import os
import subprocess

BRIDGE_URL = "http://127.0.0.1:9560"
BRIDGE_PROC = None

def _start_bridge():
    global BRIDGE_PROC
    # Ne demarrer que si pas deja en cours
    try:
        r = requests.get(f"{BRIDGE_URL}/health", timeout=1)
        if r.status_code == 200:
            return  # Deja en cours
    except:
        pass
    
    # Demarrer le bridge Python 2.7
    python27 = r"C:\Python27\python.exe"
    bridge_script = os.path.join(os.path.dirname(__file__), "naoqi_bridge.py")
    
    if os.path.exists(python27) and os.path.exists(bridge_script):
        print("[QI PROXY] Lancement du bridge NAOqi (Python 2.7)...")
        BRIDGE_PROC = subprocess.Popen(
            [python27, bridge_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # Attendre que le serveur demarre

class PostProxy:
    def __init__(self, service):
        self.service = service
    def __getattr__(self, name):
        def _wrapper(*args, **kwargs):
            import threading
            target = getattr(self.service, name)
            threading.Thread(target=target, args=args, kwargs=kwargs).start()
            return 1 # fake task id
        return _wrapper

class ServiceProxy:
    def __init__(self, name):
        self.name = name

    @property
    def post(self):
        return PostProxy(self)

    def _post(self, endpoint, data):
        try:
            requests.post(f"{BRIDGE_URL}{endpoint}", json=data, timeout=10)
        except Exception as e:
            print(f"[QI PROXY] Erreur {self.name}{endpoint}: {e}")

class ALTextToSpeech(ServiceProxy):
    def __init__(self):
        super().__init__("ALTextToSpeech")
    def setLanguage(self, lang): pass
    def setParameter(self, param, value): pass
    def setVolume(self, vol): 
        self._post("/tts/volume", {"volume": vol})
    def say(self, text):
        self._post("/tts/say", {"text": text})
    def stopAll(self):
        pass # Not easily supported via HTTP, but prevents crash

class ALLeds(ServiceProxy):
    def __init__(self):
        super().__init__("ALLeds")
    def fadeRGB(self, group, color, duration):
        self._post("/leds/fade", {"group": group, "color": color, "duration": duration})

class ALMotion(ServiceProxy):
    def __init__(self):
        super().__init__("ALMotion")
    def wakeUp(self):
        self._post("/motion/wakeup", {})
    def rest(self):
        self._post("/motion/rest", {})

class ALAudioDevice(ServiceProxy):
    def __init__(self):
        super().__init__("ALAudioDevice")
    def setOutputVolume(self, vol):
        self._post("/tts/volume", {"volume": vol / 100.0})

class ALAudioRecorder(ServiceProxy):
    def __init__(self):
        super().__init__("ALAudioRecorder")
        self._current_path = "/home/nao/temp_medibot.wav"

    def stopMicrophonesRecording(self):
        pass # Gere par le bridge avec la duree

    def startMicrophonesRecording(self, path, typ, samplerate, channels):
        self._current_path = path
        # L'API NAOqi est non-bloquante, on lance l'appel au bridge en arriere-plan
        import threading
        def _record():
            # On demande au bridge d'enregistrer pendant 4 secondes
            self._post("/mic/record", {"path": path, "duration": 4.0})
        threading.Thread(target=_record).start()

class ALAudioPlayer(ServiceProxy):
    def __init__(self):
        super().__init__("ALAudioPlayer")
    def playFile(self, path):
        self._post("/audio/play", {"path": path})

class Session:
    def __init__(self):
        self.ip = None
        self.port = None

    def connect(self, url):
        self.ip = url.split("://")[1].split(":")[0]
        self.port = int(url.split("://")[1].split(":")[1])
        _start_bridge()
        # Verifier si Pepper est connecte cote bridge
        r = requests.get(f"{BRIDGE_URL}/health", timeout=5)
        data = r.json()
        if not data.get("pepper"):
            raise RuntimeError("Le bridge Python 2.7 n'a pas pu se connecter a Pepper")

    def service(self, service_name):
        if service_name == "ALTextToSpeech":
            return ALTextToSpeech()
        elif service_name == "ALLeds":
            return ALLeds()
        elif service_name == "ALMotion":
            return ALMotion()
        elif service_name == "ALAudioDevice":
            return ALAudioDevice()
        elif service_name == "ALAudioRecorder":
            return ALAudioRecorder()
        elif service_name == "ALAudioPlayer":
            return ALAudioPlayer()
        else:
            raise ValueError(f"Service {service_name} non supporte par le proxy")

#!/usr/bin/env python3
"""
MEDIBOT - Script de lancement principal
Lance tous les services nécessaires au fonctionnement du projet.
Supporte le mode Pepper robot avec indicateur de connexion.
"""
import subprocess
import sys
import os
import signal
import time
import platform
import socket
from pathlib import Path

# Charger les variables d'environnement depuis .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv pas installé, on utilise les vars d'env système

# Couleurs pour le terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    BG_GREEN = '\033[42m'
    BG_RED = '\033[41m'
    BG_YELLOW = '\033[43m'

def log(message, color=Colors.RESET):
    """Affiche un message coloré."""
    print(f"{color}{message}{Colors.RESET}")

def log_service(service_name, status, color):
    """Affiche le statut d'un service."""
    print(f"{color}[{service_name}]{Colors.RESET} {status}")

def print_separator(char="═", length=62, color=Colors.CYAN):
    """Affiche un séparateur visuel."""
    print(f"{color}{char * length}{Colors.RESET}")

def print_connection_box(title, status_lines, success=True):
    """Affiche une boîte de statut de connexion bien visible."""
    color = Colors.GREEN if success else Colors.RED
    bg = Colors.BG_GREEN if success else Colors.BG_RED
    icon = "✅" if success else "❌"
    
    print()
    print(f"{color}{'╔' + '═' * 60 + '╗'}{Colors.RESET}")
    print(f"{color}║{Colors.RESET} {bg}{Colors.WHITE}{Colors.BOLD} {icon} {title:<55}{Colors.RESET} {color}║{Colors.RESET}")
    print(f"{color}{'╠' + '═' * 60 + '╣'}{Colors.RESET}")
    for line in status_lines:
        # Pad line to fill the box
        clean_len = len(line.replace(Colors.GREEN, '').replace(Colors.RED, '')
                       .replace(Colors.YELLOW, '').replace(Colors.CYAN, '')
                       .replace(Colors.RESET, '').replace(Colors.BOLD, '')
                       .replace(Colors.DIM, '').replace(Colors.WHITE, '')
                       .replace(Colors.MAGENTA, ''))
        padding = 58 - min(clean_len, 58)
        print(f"{color}║{Colors.RESET} {line}{' ' * padding} {color}║{Colors.RESET}")
    print(f"{color}{'╚' + '═' * 60 + '╝'}{Colors.RESET}")
    print()

class MediBotLauncher:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.processes = []
        self.is_windows = platform.system() == "Windows"
        self.pepper_controller = None
        self.pepper_connected = False
        # Dossier de logs pour les sous-processus
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_files = []  # Garder les handles ouverts
        
    def check_dependencies(self):
        """Vérifie que les dépendances sont installées."""
        log("\n🔍 Vérification des dépendances...", Colors.CYAN)
        
        checks = [
            ("rasa", [sys.executable, "-m", "rasa", "--version"]),
            ("node", ["node", "--version"]),
            ("npm", ["npm", "--version"]),
        ]
        
        all_ok = True
        for name, cmd in checks:
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    shell=self.is_windows
                )
                if result.returncode == 0:
                    version = result.stdout.strip().split('\n')[0]
                    log_service(name, f"✓ {version}", Colors.GREEN)
                else:
                    log_service(name, "✗ Non trouvé", Colors.RED)
                    all_ok = False
            except FileNotFoundError:
                log_service(name, "✗ Non installé", Colors.RED)
                all_ok = False
        
        return all_ok
    
    def _open_log(self, name: str):
        """Ouvre un fichier de log pour un service et retourne le handle."""
        log_path = self.log_dir / f"{name.lower().replace(' ', '_')}.log"
        f = open(log_path, 'w', encoding='utf-8')
        self.log_files.append(f)
        log(f"  → Log : logs/{log_path.name}", Colors.DIM)
        return f

    def start_rasa_actions(self):
        """Lance le serveur d'actions Rasa."""
        log_service("Rasa Actions", "Démarrage sur le port 5055...", Colors.YELLOW)
        
        cmd = [sys.executable, "-m", "rasa", "run", "actions", "--debug"]
        cwd = self.base_dir / "rasa_bot"
        log_f = self._open_log("rasa_actions")
        
        kwargs = {
            'cwd': cwd,
            'stdout': log_f,
            'stderr': log_f,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Rasa Actions", process))
        time.sleep(3)
        # Détecter un crash immédiat
        if process.poll() is not None:
            log_service("Rasa Actions", f"✗ Crash immédiat (code {process.returncode}) — voir logs/rasa_actions.log", Colors.RED)
            # Afficher les 10 dernières lignes du log
            try:
                log_f.flush()
                with open(self.log_dir / "rasa_actions.log", 'r', encoding='utf-8', errors='replace') as rf:
                    lines = rf.readlines()
                    for line in lines[-10:]:
                        print(f"  {Colors.RED}{line.rstrip()}{Colors.RESET}")
            except Exception:
                pass
        return process
    
    def start_rasa_server(self):
        """Lance le serveur Rasa principal avec API."""
        log_service("Rasa Server", "Démarrage sur le port 5005...", Colors.YELLOW)
        
        cmd = [sys.executable, "-m", "rasa", "run", "--enable-api", "--cors", "*"]
        cwd = self.base_dir / "rasa_bot"
        log_f = self._open_log("rasa_server")
        
        kwargs = {
            'cwd': cwd,
            'stdout': log_f,
            'stderr': log_f,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Rasa Server", process))
        time.sleep(3)
        return process
    
    def start_api_server(self):
        """Lance le serveur API Flask."""
        log_service("API Server", "Démarrage sur le port 5000...", Colors.YELLOW)
        
        cmd = [sys.executable, "app.py"]
        cwd = self.base_dir / "api_server"
        log_f = self._open_log("api_server")
        
        kwargs = {
            'cwd': cwd,
            'stdout': log_f,
            'stderr': log_f,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("API Server", process))
        time.sleep(2)
        if process.poll() is not None:
            log_service("API Server", f"✗ Crash (code {process.returncode}) — voir logs/api_server.log", Colors.RED)
            try:
                log_f.flush()
                with open(self.log_dir / "api_server.log", 'r', encoding='utf-8', errors='replace') as rf:
                    lines = rf.readlines()
                    for line in lines[-10:]:
                        print(f"  {Colors.RED}{line.rstrip()}{Colors.RESET}")
            except Exception:
                pass
        return process
    
    def start_voice_bridge(self):
        """Lance le pont vocal (voice_bridge.py) pour l'interaction voix ↔ Rasa."""
        log_service("Voice Bridge", "Démarrage du pont vocal Whisper → Rasa → TTS...", Colors.YELLOW)
        
        cmd = [sys.executable, "voice_bridge.py"]
        cwd = self.base_dir / "stt_whisper"
        
        # Le pont vocal affiche ses messages directement sur la console
        # pour que l'utilisateur voie l'interaction en temps réel
        kwargs = {
            'cwd': cwd,
            'env': {**os.environ},  # Hériter toutes les vars d'env (.env déjà chargé)
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Voice Bridge", process))
        time.sleep(2)
        
        if process.poll() is not None:
            log_service("Voice Bridge", f"✗ Crash (code {process.returncode})", Colors.RED)
        else:
            log_service("Voice Bridge", "✓ Pont vocal lancé — le robot écoute !", Colors.GREEN)
        
        return process

    def start_emotion_detection(self, use_server_vision: bool = True):
        """Lance la détection d'émotions + urgences via la caméra (Pepper ou webcam).

        OPTIMISÉ : Utilise run_emotion_optimized.py avec pipeline asynchrone.
        
        Args:
            use_server_vision: Si True, déporte DeepFace sur le serveur Flask
                              (recommandé pour Pepper car réduit la charge CPU)

        Utilise un venv séparé (EMOTION_VENV_PYTHON) pour éviter les conflits
        deepface/tensorflow vs Rasa.  Si la variable n'est pas définie,
        on tente avec le Python courant (mais deepface risque de manquer).
        """
        log_service("Emotion", "Démarrage de la détection d'émotions (OPTIMISÉ)...", Colors.YELLOW)

        # --- Déterminer quel interpréteur Python utiliser ---
        emotion_python = os.getenv("EMOTION_VENV_PYTHON", "").strip()
        if emotion_python and os.path.isfile(emotion_python):
            python_exe = emotion_python
            log(f"  → Venv émotions : {python_exe}", Colors.DIM)
        else:
            python_exe = sys.executable
            if emotion_python:
                log(f"  ⚠️  EMOTION_VENV_PYTHON={emotion_python} introuvable, utilisation du Python courant.", Colors.YELLOW)
            else:
                log(f"  → Pas de venv séparé (EMOTION_VENV_PYTHON non défini)", Colors.DIM)

        # Utiliser la version optimisée si disponible
        optimized_path = self.base_dir / "emotion_detection" / "run_emotion_optimized.py"
        legacy_path = self.base_dir / "emotion_detection" / "_run_emotion.py"
        
        if optimized_path.exists():
            launcher_path = optimized_path
            # Ajouter l'option --server si demandé (recommandé pour Pepper)
            cmd = [python_exe, str(launcher_path)]
            if use_server_vision:
                cmd.append("--server")
                log(f"  → Mode SERVEUR : DeepFace déporté sur Flask API", Colors.CYAN)
            else:
                log(f"  → Mode LOCAL : DeepFace sur ce CPU (peut être lent)", Colors.YELLOW)
        else:
            launcher_path = legacy_path
            cmd = [python_exe, str(launcher_path)]
            log(f"  ⚠️  Version optimisée non trouvée, utilisation legacy", Colors.YELLOW)
        
        cwd = self.base_dir / "emotion_detection"
        log_f = self._open_log("emotion_detection")

        # Passer les variables d'environnement pertinentes au subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.base_dir)  # pour les imports cross-modules

        kwargs = {
            'cwd': cwd,
            'stdout': log_f,
            'stderr': log_f,
            'env': env,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True

        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Emotion Detection", process))
        time.sleep(3)

        if process.poll() is not None:
            log_service("Emotion", f"✗ Crash (code {process.returncode}) — voir logs/emotion_detection.log", Colors.RED)
            try:
                log_f.flush()
                with open(self.log_dir / "emotion_detection.log", 'r', encoding='utf-8', errors='replace') as rf:
                    lines = rf.readlines()
                    for line in lines[-10:]:
                        print(f"  {Colors.RED}{line.rstrip()}{Colors.RESET}")
            except Exception:
                pass
        else:
            log_service("Emotion", "✓ Détection émotions + urgences active (async)", Colors.GREEN)

        return process

    def start_frontend(self):
        """Lance le serveur de développement frontend."""
        log_service("Frontend", "Démarrage sur le port 5173...", Colors.YELLOW)
        
        cmd = ["npm", "run", "dev"]
        cwd = self.base_dir / "api_server" / "frontend"
        log_f = self._open_log("frontend")
        
        kwargs = {
            'cwd': cwd,
            'stdout': log_f,
            'stderr': log_f,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Frontend", process))
        time.sleep(2)
        return process

    # =================================================================
    # CONNEXION ROBOT PEPPER
    # =================================================================
    
    def check_pepper_env(self):
        """Vérifie la configuration Pepper dans .env."""
        pepper_ip = os.getenv("PEPPER_IP")
        pepper_port = os.getenv("PEPPER_PORT", "9559")
        
        log("\n🤖 Configuration Robot Pepper :", Colors.MAGENTA)
        
        if not pepper_ip:
            log_service("PEPPER_IP", "⚠️  Non configuré dans .env", Colors.YELLOW)
            log(f"   → Créez un fichier .env à la racine du projet avec :", Colors.DIM)
            log(f"     PEPPER_IP=<adresse_ip_du_robot>", Colors.DIM)
            log(f"     PEPPER_PORT=9559", Colors.DIM)
            return None, None
        
        log_service("PEPPER_IP", f"✓ {pepper_ip}", Colors.GREEN)
        log_service("PEPPER_PORT", f"✓ {pepper_port}", Colors.GREEN)
        
        return pepper_ip, int(pepper_port)
    
    def test_network_reachability(self, ip, port, timeout=10):
        """Teste si le robot est joignable sur le réseau (ping TCP)."""
        log_service("Réseau", f"Test de connectivité vers {ip}:{port}...", Colors.YELLOW)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                log_service("Réseau", f"✓ Robot joignable sur {ip}:{port}", Colors.GREEN)
                return True
            else:
                log_service("Réseau", f"✗ Port {port} fermé sur {ip}", Colors.RED)
                return False
        except socket.timeout:
            log_service("Réseau", f"✗ Timeout - Robot injoignable sur {ip}", Colors.RED)
            return False
        except socket.gaierror:
            log_service("Réseau", f"✗ Adresse IP invalide : {ip}", Colors.RED)
            return False
        except Exception as e:
            log_service("Réseau", f"✗ Erreur réseau : {e}", Colors.RED)
            return False
    
    def connect_to_pepper(self, max_retries=3):
        """
        Tente de se connecter au robot Pepper avec indicateurs visuels.
        
        Returns:
            bool: True si la connexion est établie
        """
        pepper_ip, pepper_port = self.check_pepper_env()
        
        if not pepper_ip:
            print_connection_box(
                "PEPPER - NON CONFIGURÉ",
                [
                    f"Aucune IP robot trouvée dans le fichier .env",
                    f"",
                    f"Pour configurer, ajoutez dans .env :",
                    f"  PEPPER_IP=<ip_du_robot>",
                    f"  PEPPER_PORT=9559",
                    f"",
                    f"{Colors.YELLOW}Les services logiciels continuent sans robot.{Colors.RESET}",
                ],
                success=False
            )
            return False
        
        # Étape 1 : Test réseau
        print_separator("─", 62, Colors.MAGENTA)
        log(f"  🔌 ÉTAPE 1/3 : Test de connectivité réseau", Colors.MAGENTA)
        print_separator("─", 62, Colors.MAGENTA)
        
        if not self.test_network_reachability(pepper_ip, pepper_port):
            print_connection_box(
                "PEPPER - INJOIGNABLE SUR LE RÉSEAU",
                [
                    f"IP : {pepper_ip}   Port : {pepper_port}",
                    f"",
                    f"Vérifiez que :",
                    f"  1. Le robot Pepper est allumé",
                    f"  2. Il est connecté au même réseau WiFi",
                    f"  3. L'adresse IP est correcte",
                    f"  4. Le pare-feu ne bloque pas le port {pepper_port}",
                ],
                success=False
            )
            return False
        
        # Étape 2 : Connexion NAOqi
        print_separator("─", 62, Colors.MAGENTA)
        log(f"  🔗 ÉTAPE 2/3 : Connexion au service NAOqi", Colors.MAGENTA)
        print_separator("─", 62, Colors.MAGENTA)
        
        for attempt in range(1, max_retries + 1):
            log_service("NAOqi", f"Tentative {attempt}/{max_retries}...", Colors.YELLOW)
            
            try:
                import qi
                
                session = qi.Session()
                url = f"tcp://{pepper_ip}:{pepper_port}"
                log_service("NAOqi", f"Connexion à {url}...", Colors.YELLOW)
                
                session.connect(url)
                
                log_service("NAOqi", "✓ Session NAOqi établie !", Colors.GREEN)
                
                # Étape 3 : Initialisation des sous-systèmes
                print_separator("─", 62, Colors.MAGENTA)
                log(f"  ⚙️  ÉTAPE 3/3 : Initialisation des sous-systèmes", Colors.MAGENTA)
                print_separator("─", 62, Colors.MAGENTA)
                
                subsystems_status = self._init_pepper_subsystems(session)
                
                # Afficher le résultat final
                status_lines = [
                    f"IP : {pepper_ip}   Port : {pepper_port}",
                    f"Session NAOqi : {Colors.GREEN}Connectée{Colors.RESET}",
                    f"",
                ]
                
                all_ok = True
                for name, ok in subsystems_status.items():
                    icon = "✓" if ok else "✗"
                    c = Colors.GREEN if ok else Colors.RED
                    status_lines.append(f"  {c}{icon}{Colors.RESET} {name}")
                    if not ok:
                        all_ok = False
                
                status_lines.append(f"")
                if all_ok:
                    status_lines.append(f"{Colors.GREEN}{Colors.BOLD}Tous les sous-systèmes sont opérationnels !{Colors.RESET}")
                else:
                    status_lines.append(f"{Colors.YELLOW}Certains sous-systèmes non disponibles.{Colors.RESET}")
                    status_lines.append(f"{Colors.YELLOW}Le robot fonctionnera en mode dégradé.{Colors.RESET}")
                
                print_connection_box("PEPPER - CONNEXION ÉTABLIE !", status_lines, success=True)
                
                self.pepper_connected = True
                return True
                
            except ImportError:
                log_service("NAOqi", "✗ Module 'qi' non trouvé (NAOqi SDK manquant)", Colors.RED)
                print_connection_box(
                    "PEPPER - SDK NAOqi NON INSTALLÉ",
                    [
                        f"Le module Python 'qi' n'est pas installé.",
                        f"",
                        f"Installez le NAOqi SDK Python :",
                        f"  pip install qi  (ou depuis le SDK Aldebaran)",
                        f"",
                        f"{Colors.YELLOW}Les services continuent sans robot.{Colors.RESET}",
                    ],
                    success=False
                )
                return False
                
            except Exception as e:
                log_service("NAOqi", f"✗ Échec : {e}", Colors.RED)
                if attempt < max_retries:
                    wait_time = attempt * 2
                    log_service("NAOqi", f"  Nouvelle tentative dans {wait_time}s...", Colors.YELLOW)
                    time.sleep(wait_time)
        
        # Toutes les tentatives échouées
        print_connection_box(
            "PEPPER - CONNEXION ÉCHOUÉE",
            [
                f"IP : {pepper_ip}   Port : {pepper_port}",
                f"Tentatives : {max_retries}/{max_retries} épuisées",
                f"",
                f"Vérifiez que :",
                f"  1. NAOqi est en cours d'exécution sur le robot",
                f"  2. Le robot n'est pas en mode veille",
                f"  3. Aucun autre client NAOqi n'occupe la session",
            ],
            success=False
        )
        return False
    
    def _init_pepper_subsystems(self, session):
        """
        Initialise les sous-systèmes Pepper et retourne leur statut.
        
        Returns:
            dict: {nom_sous_systeme: bool_ok}
        """
        from robot_control.pepper_main import PepperController
        
        controller = PepperController.__new__(PepperController)
        controller.session = session
        controller.ip = os.getenv("PEPPER_IP", "127.0.0.1")
        controller.port = int(os.getenv("PEPPER_PORT", "9559"))
        controller._command_queue = __import__('queue').Queue()
        controller._running = False
        controller._loop_thread = None
        controller._on_command_complete = None
        controller._on_error = None
        
        status = {}
        
        # TTS
        try:
            from robot_control.pepper_tts import PepperTTS
            controller.tts = PepperTTS(session)
            status["ALTextToSpeech (Parole)"] = True
            log_service("TTS", "✓ Service de parole prêt", Colors.GREEN)
        except Exception as e:
            controller.tts = None
            status["ALTextToSpeech (Parole)"] = False
            log_service("TTS", f"✗ {e}", Colors.RED)
        
        # Motion
        try:
            from robot_control.pepper_motion import PepperMotion
            controller.motion = PepperMotion(session)
            status["ALMotion (Mouvements)"] = True
            log_service("Motion", "✓ Service de mouvements prêt", Colors.GREEN)
        except Exception as e:
            controller.motion = None
            status["ALMotion (Mouvements)"] = False
            log_service("Motion", f"✗ {e}", Colors.RED)
        
        # LEDs
        try:
            from robot_control.pepper_leds import PepperLEDs
            controller.leds = PepperLEDs(session)
            status["ALLeds (LEDs émotions)"] = True
            log_service("LEDs", "✓ Service LEDs prêt", Colors.GREEN)
        except Exception as e:
            controller.leds = None
            status["ALLeds (LEDs émotions)"] = False
            log_service("LEDs", f"✗ {e}", Colors.RED)
        
        # Behavior
        try:
            from robot_control.pepper_behavior import PepperBehavior
            controller.behavior = PepperBehavior(session)
            status["ALBehaviorManager (Animations)"] = True
            log_service("Behavior", "✓ Service d'animations prêt", Colors.GREEN)
        except Exception as e:
            controller.behavior = None
            status["ALBehaviorManager (Animations)"] = False
            log_service("Behavior", f"✗ {e}", Colors.RED)
        
        # Camera
        try:
            from robot_control.pepper_camera import PepperCamera
            controller.camera = PepperCamera(session)
            status["ALVideoDevice (Caméra)"] = True
            log_service("Camera", "✓ Service caméra prêt", Colors.GREEN)
        except Exception as e:
            controller.camera = None
            status["ALVideoDevice (Caméra)"] = False
            log_service("Camera", f"✗ {e}", Colors.RED)
        
        self.pepper_controller = controller
        return status
    
    def stop_all(self):
        """Arrête tous les processus et déconnecte Pepper."""
        log("\n🛑 Arrêt de tous les services...", Colors.RED)
        
        # Fermer les fichiers de log
        for f in self.log_files:
            try:
                f.close()
            except Exception:
                pass

        # Déconnecter Pepper si connecté
        if self.pepper_controller and self.pepper_connected:
            log_service("Pepper", "Déconnexion du robot...", Colors.YELLOW)
            try:
                self.pepper_controller.disconnect()
                log_service("Pepper", "✓ Robot déconnecté", Colors.GREEN)
            except Exception as e:
                log_service("Pepper", f"⚠️ Erreur déconnexion: {e}", Colors.RED)
        
        # --- Phase 1 : SIGTERM gracieux sur tous les groupes de processus ---
        still_alive = []
        for name, process in self.processes:
            if process.poll() is None:
                log_service(name, "Arrêt...", Colors.YELLOW)
                try:
                    if self.is_windows:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            capture_output=True
                        )
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    still_alive.append((name, process))
                except Exception:
                    still_alive.append((name, process))
        
        # Attendre que les processus se terminent gracieusement (max 4s)
        deadline = time.time() + 4
        for name, process in still_alive:
            remaining = max(0, deadline - time.time())
            try:
                process.wait(timeout=remaining)
                log_service(name, "✓ Arrêté", Colors.GREEN)
            except subprocess.TimeoutExpired:
                pass
        
        # --- Phase 2 : SIGKILL forcé pour tout ce qui survit ---
        for name, process in still_alive:
            if process.poll() is None:
                log_service(name, "Force kill...", Colors.RED)
                try:
                    if self.is_windows:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            capture_output=True
                        )
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait(timeout=3)
                    log_service(name, "✓ Forcé", Colors.YELLOW)
                except Exception as e:
                    log_service(name, f"⚠️ Impossible de tuer: {e}", Colors.RED)
    
    def run(self, connect_pepper=False):
        """Lance tous les services."""
        log(f"""
{Colors.BOLD}{Colors.CYAN}
╔══════════════════════════════════════════════════════════════╗
║                      🤖 MEDIBOT                              ║
║              Assistant Médical Intelligent                   ║
║                                                              ║
║  Mode : {'PEPPER ROBOT 🦾' if connect_pepper else 'SIMULATION PC 💻':>44}  ║
╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}""")
        
        # Vérification des dépendances
        if not self.check_dependencies():
            log("\n⚠️  Certaines dépendances sont manquantes.", Colors.RED)
            response = input("Continuer quand même ? (o/N): ")
            if response.lower() != 'o':
                return
        
        log("\n🚀 Lancement des services...\n", Colors.GREEN)
        
        # Installer un handler de signal pour s'assurer que Ctrl+C tue tout
        def _signal_handler(sig, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGINT, _signal_handler)
        if not self.is_windows:
            signal.signal(signal.SIGTERM, _signal_handler)
        
        try:
            # Lancer les services dans l'ordre
            self.start_rasa_actions()
            self.start_rasa_server()
            self.start_api_server()
            self.start_frontend()
            
            log(f"""
{Colors.GREEN}{Colors.BOLD}
✅ Services logiciels démarrés !
{Colors.RESET}
{Colors.CYAN}Services disponibles :{Colors.RESET}
  • Rasa Actions    : http://localhost:5055
  • Rasa API        : http://localhost:5005
  • API Dashboard   : http://localhost:5000
  • Frontend        : http://localhost:5173

{Colors.CYAN}Modules lancés avec --pepper :{Colors.RESET}
  • Voice Bridge    : Whisper STT → Rasa → TTS (écoute/parole)
  • Emotion Detect. : Caméra → DeepFace + MediaPipe (émotions/urgences)
""")
            
            # === CONNEXION PEPPER (si demandé) ===
            if connect_pepper:
                print_separator("═", 62, Colors.MAGENTA)
                log(f"  {Colors.BOLD}{Colors.MAGENTA}🤖 CONNEXION AU ROBOT PEPPER{Colors.RESET}", Colors.MAGENTA)
                print_separator("═", 62, Colors.MAGENTA)
                
                pepper_ok = self.connect_to_pepper(max_retries=3)
                
                if pepper_ok:
                    # Test de bienvenue sur le robot
                    log("🎤 Test de parole sur le robot...", Colors.CYAN)
                    try:
                        if self.pepper_controller and self.pepper_controller.tts:
                            tts_svc = self.pepper_controller.tts.tts_service

                            # --- Forcer le volume directement via la session NAOqi ---
                            session = self.pepper_controller.session
                            try:
                                ad = session.service("ALAudioDevice")
                                current_vol = ad.getOutputVolume()
                                log_service("Audio", f"Volume master actuel : {current_vol}%", Colors.CYAN)
                                ad.setOutputVolume(100)
                                log_service("Audio", "Volume master forcé → 100%", Colors.GREEN)
                            except Exception as e:
                                log_service("Audio", f"⚠️ ALAudioDevice : {e}", Colors.YELLOW)

                            try:
                                tts_svc.setVolume(1.0)
                                tts_svc.setLanguage("French")
                                tts_svc.setParameter("speed", 85)
                            except Exception:
                                pass

                            # Parler — appel bloquant, attend la fin de la phrase
                            log_service("TTS", "Robot parle maintenant...", Colors.CYAN)
                            tts_svc.say("\\vol=150\\ Bonjour ! Je suis Médi Bot. Connexion réussie.")
                            log_service("Test TTS", "✓ Le robot a parlé !", Colors.GREEN)
                        
                        if self.pepper_controller and self.pepper_controller.leds:
                            self.pepper_controller.leds.set_emotion_led("happy")
                            log_service("Test LEDs", "✓ LEDs en mode 'happy'", Colors.GREEN)
                    except Exception as e:
                        log_service("Test", f"⚠️ {e}", Colors.YELLOW)
                    
                    log(f"""
{Colors.GREEN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║  🟢  MEDIBOT EST PRÊT - ROBOT PEPPER CONNECTÉ               ║
║                                                              ║
║  Le robot est opérationnel et attend les commandes.          ║
║  Le chatbot Rasa communiquera avec Pepper en temps réel.     ║
╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}""")
                    # Lancer le pont vocal pour que le robot écoute et parle
                    log("\n🎤 Lancement du pont vocal (Whisper → Rasa → TTS)...\n", Colors.CYAN)
                    self.start_voice_bridge()
                    
                    # Lancer la détection d'émotions + urgences via caméra
                    log("\n👁️ Lancement de la détection d'émotions...\n", Colors.CYAN)
                    self.start_emotion_detection()
                else:
                    log(f"""
{Colors.YELLOW}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║  🟡  MEDIBOT EN MODE DÉGRADÉ - SANS ROBOT                   ║
║                                                              ║
║  Les services logiciels fonctionnent normalement.            ║
║  Le robot Pepper n'est pas connecté.                         ║
║  Corrigez la configuration et relancez avec --pepper         ║
╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}""")
            else:
                log(f"""
{Colors.CYAN}
  ℹ️  Mode simulation PC (sans robot physique).
  Pour connecter Pepper, relancez avec :
    python run.py --pepper
{Colors.RESET}""")
            
            log(f"{Colors.YELLOW}Appuyez sur Ctrl+C pour arrêter tous les services.{Colors.RESET}")
            
            # Attendre l'interruption
            already_warned = set()
            while True:
                # Vérifier que les processus tournent toujours (une seule alerte par service)
                for name, process in self.processes:
                    if process.poll() is not None and name not in already_warned:
                        already_warned.add(name)
                        log_name = name.lower().replace(' ', '_')
                        log_service(name, f"⚠️  Processus terminé (code {process.returncode}) — voir logs/{log_name}.log", Colors.RED)
                
                # Vérifier la connexion Pepper périodiquement
                if self.pepper_connected and self.pepper_controller:
                    if not self.pepper_controller.is_connected():
                        log_service("Pepper", "⚠️ Connexion perdue avec le robot !", Colors.RED)
                        self.pepper_connected = False
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()
            log("\n👋 MEDIBOT arrêté. À bientôt !", Colors.CYAN)


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MEDIBOT - Lanceur de services")
    parser.add_argument(
        "--no-frontend", 
        action="store_true", 
        help="Ne pas lancer le frontend"
    )
    parser.add_argument(
        "--no-rasa", 
        action="store_true", 
        help="Ne pas lancer les serveurs Rasa"
    )
    parser.add_argument(
        "--api-only", 
        action="store_true", 
        help="Lancer uniquement le serveur API"
    )
    parser.add_argument(
        "--pepper",
        action="store_true",
        help="Activer la connexion au robot Pepper (nécessite PEPPER_IP dans .env)"
    )
    
    args = parser.parse_args()
    
    launcher = MediBotLauncher()
    
    if args.api_only:
        log("\n Mode API uniquement\n", Colors.GREEN)
        try:
            launcher.start_api_server()
            log(f"\n{Colors.GREEN}✅ API Server démarré sur http://localhost:5000{Colors.RESET}")
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            launcher.stop_all()
    else:
        # Modifier la méthode run pour respecter les flags
        if args.no_rasa:
            launcher.start_rasa_actions = lambda: None
            launcher.start_rasa_server = lambda: None
        if args.no_frontend:
            launcher.start_frontend = lambda: None
        
        launcher.run(connect_pepper=args.pepper)


if __name__ == "__main__":
    main()

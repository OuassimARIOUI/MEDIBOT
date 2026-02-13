#!/usr/bin/env python3
"""
MEDIBOT - Script de lancement principal
Lance tous les services nécessaires au fonctionnement du projet.
"""
import subprocess
import sys
import os
import signal
import time
import platform
from pathlib import Path

# Couleurs pour le terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(message, color=Colors.RESET):
    """Affiche un message coloré."""
    print(f"{color}{message}{Colors.RESET}")

def log_service(service_name, status, color):
    """Affiche le statut d'un service."""
    print(f"{color}[{service_name}]{Colors.RESET} {status}")

class MediBotLauncher:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.processes = []
        self.is_windows = platform.system() == "Windows"
        
    def check_dependencies(self):
        """Vérifie que les dépendances sont installées."""
        log("\n🔍 Vérification des dépendances...", Colors.CYAN)
        
        checks = [
            ("rasa", "rasa --version"),
            ("node", "node --version"),
            ("npm", "npm --version"),
        ]
        
        all_ok = True
        for name, cmd in checks:
            try:
                result = subprocess.run(
                    cmd.split(), 
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
    
    def start_rasa_actions(self):
        """Lance le serveur d'actions Rasa."""
        log_service("Rasa Actions", "Démarrage sur le port 5055...", Colors.YELLOW)
        
        cmd = ["rasa", "run", "actions"]
        cwd = self.base_dir / "rasa_bot"
        
        kwargs = {
            'cwd': cwd,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("Rasa Actions", process))
        time.sleep(2)
        return process
    
    def start_rasa_server(self):
        """Lance le serveur Rasa principal avec API."""
        log_service("Rasa Server", "Démarrage sur le port 5005...", Colors.YELLOW)
        
        cmd = ["rasa", "run", "--enable-api", "--cors", "*"]
        cwd = self.base_dir / "rasa_bot"
        
        kwargs = {
            'cwd': cwd,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
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
        
        kwargs = {
            'cwd': cwd,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
        }
        if self.is_windows:
            kwargs['shell'] = True
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        
        process = subprocess.Popen(cmd, **kwargs)
        self.processes.append(("API Server", process))
        time.sleep(1)
        return process
    
    def start_frontend(self):
        """Lance le serveur de développement frontend."""
        log_service("Frontend", "Démarrage sur le port 5173...", Colors.YELLOW)
        
        cmd = ["npm", "run", "dev"]
        cwd = self.base_dir / "api_server" / "frontend"
        
        kwargs = {
            'cwd': cwd,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
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
    
    def stop_all(self):
        """Arrête tous les processus."""
        log("\n🛑 Arrêt de tous les services...", Colors.RED)
        
        for name, process in self.processes:
            if process.poll() is None:  # Si le processus tourne encore
                log_service(name, "Arrêt...", Colors.YELLOW)
                try:
                    if self.is_windows:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            capture_output=True
                        )
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=5)
                    log_service(name, "✓ Arrêté", Colors.GREEN)
                except Exception as e:
                    log_service(name, f"⚠️ Erreur: {e}", Colors.RED)
                    process.kill()
    
    def run(self):
        """Lance tous les services."""
        log(f"""
{Colors.BOLD}{Colors.CYAN}
╔══════════════════════════════════════════════════════════════╗
║                      🤖 MEDIBOT                              ║
║              Assistant Médical Intelligent                   ║
╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}""")
        
        # Vérification des dépendances
        if not self.check_dependencies():
            log("\n⚠️  Certaines dépendances sont manquantes.", Colors.RED)
            response = input("Continuer quand même ? (o/N): ")
            if response.lower() != 'o':
                return
        
        log("\n🚀 Lancement des services...\n", Colors.GREEN)
        
        try:
            # Lancer les services dans l'ordre
            self.start_rasa_actions()
            self.start_rasa_server()
            self.start_api_server()
            self.start_frontend()
            
            log(f"""
{Colors.GREEN}{Colors.BOLD}
✅ Tous les services sont démarrés !
{Colors.RESET}
{Colors.CYAN}Services disponibles :{Colors.RESET}
  • Rasa Actions    : http://localhost:5055
  • Rasa API        : http://localhost:5005
  • API Dashboard   : http://localhost:5000
  • Frontend        : http://localhost:5173

{Colors.YELLOW}Appuyez sur Ctrl+C pour arrêter tous les services.{Colors.RESET}
""")
            
            # Attendre l'interruption
            while True:
                # Vérifier que les processus tournent toujours
                for name, process in self.processes:
                    if process.poll() is not None:
                        log_service(name, f"⚠️ Processus terminé (code: {process.returncode})", Colors.RED)
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
    
    args = parser.parse_args()
    
    launcher = MediBotLauncher()
    
    if args.api_only:
        log("\n🚀 Mode API uniquement\n", Colors.GREEN)
        try:
            launcher.start_api_server()
            log(f"\n{Colors.GREEN}✅ API Server démarré sur http://localhost:5000{Colors.RESET}")
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            launcher.stop_all()
    else:
        # Modifier la méthode run pour respecter les flags
        if args.no_rasa:
            launcher.start_rasa_actions = lambda: None
            launcher.start_rasa_server = lambda: None
        if args.no_frontend:
            launcher.start_frontend = lambda: None
        
        launcher.run()


if __name__ == "__main__":
    main()

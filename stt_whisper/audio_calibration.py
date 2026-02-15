"""
Outil de calibration du microphone pour optimiser la capture vocale.
Permet de mesurer le niveau sonore ambiant et ajuster le seuil de détection.
"""

import sounddevice as sd
import numpy as np
import time

FS = 16000
CALIBRATION_DURATION = 3  # Secondes

def calibrate_microphone():
    """
    Calibre le microphone en mesurant le bruit ambiant.
    Retourne le seuil optimal pour la détection vocale.
    """
    print("\n" + "="*60)
    print("🎤 CALIBRATION DU MICROPHONE")
    print("="*60)
    print("\n[1/3] Restez silencieux pendant 3 secondes...")
    print("       (Mesure du bruit ambiant)\n")
    
    time.sleep(1)
    
    # Mesure du silence
    print("⏳ Enregistrement du silence...")
    silence = sd.rec(int(CALIBRATION_DURATION * FS), samplerate=FS, channels=1, dtype='float32')
    sd.wait()
    silence_energy = np.sqrt(np.mean(silence**2))
    
    print(f"✅ Énergie du bruit ambiant : {silence_energy:.6f}\n")
    
    # Mesure de la voix
    print("[2/3] Parlez maintenant pendant 3 secondes !")
    print("      Dites : 'Bonjour je suis [votre nom]'\n")
    
    time.sleep(1)
    print("⏳ Enregistrement de votre voix...")
    speech = sd.rec(int(CALIBRATION_DURATION * FS), samplerate=FS, channels=1, dtype='float32')
    sd.wait()
    speech_energy = np.sqrt(np.mean(speech**2))
    
    print(f"✅ Énergie de votre voix : {speech_energy:.6f}\n")
    
    # Calcul du seuil optimal
    if speech_energy <= silence_energy * 1.5:
        print("⚠️  ATTENTION : Votre voix est trop faible ou le microphone trop éloigné !")
        print("   Recommandations :")
        print("   - Rapprochez-vous du microphone (15-30 cm)")
        print("   - Parlez plus fort")
        print("   - Vérifiez les paramètres de volume du système\n")
        threshold = silence_energy * 1.2
    else:
        # Seuil = 60% entre silence et voix
        threshold = silence_energy + (speech_energy - silence_energy) * 0.3
    
    print("[3/3] Résultat de la calibration :")
    print(f"      📊 Rapport signal/bruit : {speech_energy/silence_energy:.2f}x")
    print(f"      🎯 Seuil optimal : {threshold:.6f}")
    
    if speech_energy / silence_energy < 2:
        print("      ⚠️  Qualité : FAIBLE (rapprochez-vous du micro)")
    elif speech_energy / silence_energy < 4:
        print("      ⚠️  Qualité : MOYENNE (essayez de parler plus fort)")
    else:
        print("      ✅ Qualité : BONNE (conditions optimales)")
    
    print("\n" + "="*60 + "\n")
    
    return threshold

def test_microphone_levels():
    """
    Test en temps réel du niveau d'entrée du microphone.
    """
    print("\n🎤 TEST DU MICROPHONE EN TEMPS RÉEL")
    print("   Parlez et observez les niveaux affichés")
    print("   (CTRL+C pour arrêter)\n")
    
    def callback(indata, frames, time, status):
        energy = np.sqrt(np.mean(indata**2))
        bars = int(energy * 1000)
        print(f"\r🔊 Niveau : {'█' * min(bars, 50):<50} {energy:.6f}", end='')
    
    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=FS):
            while True:
                sd.sleep(100)
    except KeyboardInterrupt:
        print("\n\n✅ Test terminé\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_microphone_levels()
    else:
        threshold = calibrate_microphone()
        print(f"💾 Utilisez cette valeur dans voice_bridge.py :")
        print(f"   MIN_ENERGY_THRESHOLD = {threshold:.6f}\n")

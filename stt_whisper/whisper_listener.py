import whisper
import torch

class MediBotListener:
    def __init__(self, model_size="medium"):
        # Utilise le GPU si disponible pour réduire les 5s de latence
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model(model_size, device=device)
        self.model_size = model_size  # Store model size for testing

    def transcribe(self, audio_path):
        # language="fr" : évite la détection automatique (gain ~0.5s)
        # beam_size=3    : compromis précision/vitesse (défaut=5, greedy=1)
        # condition_on_previous_text=False : évite l'accumulation de contexte
        # no_speech_threshold=0.6 : rejet rapide du silence
        result = self.model.transcribe(
            audio_path,
            language="fr",
            fp16=False,
            beam_size=3,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        return result.get("text", "").strip()
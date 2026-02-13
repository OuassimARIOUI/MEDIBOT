import whisper
import torch

class MediBotListener:
    def __init__(self, model_size="tiny"):
        # Utilise le GPU si disponible pour réduire les 5s de latence
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model(model_size, device=device)

    def transcribe(self, audio_path):
        # On force la langue en français pour éviter les erreurs d'interprétation
        result = self.model.transcribe(audio_path, language="fr", fp16=False)
        return result.get("text", "").strip()
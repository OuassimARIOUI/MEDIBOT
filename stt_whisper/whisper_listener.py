import whisper
import torch

class MediBotListener:
    def __init__(self, model_size="medium"):
        # GPU si dispo → latence divisée par 3-5x sur "medium"
        self._use_cuda = torch.cuda.is_available()
        device = "cuda" if self._use_cuda else "cpu"
        print(f"[Whisper] Chargement du modèle '{model_size}' sur {device.upper()}...")
        self.model = whisper.load_model(model_size, device=device)
        self.model_size = model_size

    def transcribe(self, audio_path):
        # Optimisations latence :
        #   language="fr"                   → pas de détection auto (-0.5s)
        #   fp16=True si CUDA              → moitié mémoire, 2x plus rapide sur GPU
        #   beam_size=1 (greedy) si CUDA   → meilleur compromis pour le live
        #   beam_size=2 sur CPU            → précision raisonnable sans surcoût majeur
        #   condition_on_previous_text=False → pas d'accumulation de contexte
        #   no_speech_threshold=0.6         → rejet rapide du silence
        result = self.model.transcribe(
            audio_path,
            language="fr",
            fp16=self._use_cuda,
            beam_size=1 if self._use_cuda else 2,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0.0,  # sortie déterministe, latence minimale
        )
        return result.get("text", "").strip()
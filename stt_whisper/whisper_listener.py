"""
whisper_listener.py — Wrapper Whisper STT optimisé pour la latence.

Optimisations :
  - faster-whisper (CTranslate2) si installé : 4-10x plus rapide qu'openai-whisper
  - Choix du modèle via env WHISPER_MODEL (default: "base" sur CPU, "small" sur GPU)
  - Greedy decoding (beam_size=1) en mode live
  - VAD interne désactivé (le voice_bridge fait déjà du end-pointing)
"""

import os

# Modèle par défaut : "base" sur CPU (bon compromis vitesse/précision pour le FR),
# "small" si CUDA disponible. Surchargeable via WHISPER_MODEL.
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "").strip()


class MediBotListener:
    def __init__(self, model_size: str = ""):
        # Priorité : argument > env WHISPER_MODEL > auto
        model_size = (model_size or _DEFAULT_MODEL or "").strip()

        # Détection GPU (utile pour faster-whisper aussi)
        try:
            import torch
            self._use_cuda = bool(torch.cuda.is_available())
        except Exception:
            self._use_cuda = False

        if not model_size:
            model_size = "small" if self._use_cuda else "base"
        self.model_size = model_size

        # ── Backend 1 : faster-whisper (préféré, CTranslate2) ─────────────
        self._backend = None
        try:
            from faster_whisper import WhisperModel  # type: ignore
            device = "cuda" if self._use_cuda else "cpu"
            compute_type = "float16" if self._use_cuda else "int8"
            print(f"[Whisper] faster-whisper '{model_size}' sur {device.upper()} (compute={compute_type})...")
            self._fw_model = WhisperModel(
                model_size, device=device, compute_type=compute_type
            )
            self._backend = "faster-whisper"
        except ImportError:
            # ── Backend 2 : openai-whisper (fallback) ─────────────────────
            import whisper
            device = "cuda" if self._use_cuda else "cpu"
            print(f"[Whisper] openai-whisper '{model_size}' sur {device.upper()}...")
            self._ow_model = whisper.load_model(model_size, device=device)
            self._backend = "openai-whisper"

    # ------------------------------------------------------------------
    def transcribe(self, audio_path: str) -> str:
        if self._backend == "faster-whisper":
            return self._transcribe_fw(audio_path)
        return self._transcribe_ow(audio_path)

    # ------------------------------------------------------------------
    def _transcribe_fw(self, audio_path: str) -> str:
        """faster-whisper : 4-10x plus rapide, même précision."""
        segments, _info = self._fw_model.transcribe(
            audio_path,
            language="fr",
            beam_size=1,                  # greedy → latence minimale
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0.0,
            vad_filter=False,             # VAD déjà fait dans voice_bridge
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    # ------------------------------------------------------------------
    def _transcribe_ow(self, audio_path: str) -> str:
        """openai-whisper (fallback)."""
        result = self._ow_model.transcribe(
            audio_path,
            language="fr",
            fp16=self._use_cuda,
            beam_size=1,                  # greedy → latence minimale (CPU & GPU)
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0.0,
        )
        return result.get("text", "").strip()
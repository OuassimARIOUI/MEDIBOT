"""
vision_routes.py — Endpoints Flask pour déporter le traitement vision.

OPTIMISATION : Déporte DeepFace du CPU limité de Pepper vers le serveur.
Le robot envoie les frames, le serveur fait l'analyse et retourne le résultat.

Avantages :
- Libère le CPU de Pepper pour Whisper/Rasa
- Peut utiliser un GPU sur le serveur pour accélérer DeepFace
- Réduit la latence perçue par le robot

Endpoints :
  POST /api/vision/emotion  : Analyse d'émotion sur une image
  POST /api/vision/emergency : Détection d'urgences (respiration/étouffement)
  GET  /api/vision/status   : État du service vision

Auteur: MediBot Team - Optimisation Latence
"""

import os
import sys
import time
import base64
import logging
import numpy as np
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

vision_bp = Blueprint('vision', __name__, url_prefix='/api/vision')

# Import paresseux de DeepFace (chargé au premier appel)
_deepface = None
_deepface_available = None

def _get_deepface():
    """Charge DeepFace de manière paresseuse."""
    global _deepface, _deepface_available
    
    if _deepface_available is False:
        return None
    
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
            _deepface_available = True
            logger.info("DeepFace chargé sur le serveur (OK)")
        except ImportError:
            _deepface_available = False
            logger.warning("DeepFace non disponible sur le serveur")
            return None
    
    return _deepface

# Import paresseux de MediaPipe
_emergency_detector = None

def _get_emergency_detector():
    """Charge EmergencyDetector de manière paresseuse."""
    global _emergency_detector
    
    if _emergency_detector is None:
        try:
            # Ajouter le chemin emotion_detection au PYTHONPATH
            emotion_path = os.path.join(
                os.path.dirname(__file__), '..', 'emotion_detection'
            )
            if emotion_path not in sys.path:
                sys.path.insert(0, emotion_path)
            
            from emergency_detector import EmergencyDetector
            _emergency_detector = EmergencyDetector()
            logger.info("EmergencyDetector chargé sur le serveur (OK)")
        except ImportError as e:
            logger.warning(f"EmergencyDetector non disponible: {e}")
            return None
    
    return _emergency_detector


def _decode_image(image_base64: str) -> np.ndarray:
    """Décode une image base64 en numpy array BGR."""
    import cv2
    
    # Décoder base64
    img_bytes = base64.b64decode(image_base64)
    
    # Convertir en numpy array
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    
    # Décoder JPEG/PNG
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    return img


@vision_bp.route('/emotion', methods=['POST'])
def analyze_emotion():
    """
    Analyse l'émotion sur une image.
    
    Request JSON:
        {
            "image": "<base64_encoded_jpeg>"
        }
    
    Response JSON:
        {
            "success": true,
            "emotion": "happy",
            "confidence": 0.87,
            "all_emotions": {"happy": 0.87, "sad": 0.05, ...},
            "latency_ms": 450
        }
    """
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'image' field in request"
            }), 400
        
        # Décoder l'image
        try:
            img = _decode_image(data['image'])
            if img is None:
                raise ValueError("Image decode failed")
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Image decode error: {e}"
            }), 400
        
        # Charger DeepFace
        df = _get_deepface()
        if df is None:
            return jsonify({
                "success": False,
                "error": "DeepFace not available on server"
            }), 503
        
        # Analyser
        try:
            results = df.analyze(
                img,
                actions=['emotion'],
                enforce_detection=False,
                silent=True
            )
            
            emotions = results[0].get('emotion', {})
            dominant = results[0].get('dominant_emotion', 'unknown')
            confidence = emotions.get(dominant, 0) / 100.0  # Normaliser 0-1
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return jsonify({
                "success": True,
                "emotion": dominant,
                "confidence": confidence,
                "all_emotions": emotions,
                "latency_ms": latency_ms
            })
            
        except Exception as e:
            logger.error(f"DeepFace analysis error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    except Exception as e:
        logger.error(f"Vision endpoint error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@vision_bp.route('/emergency', methods=['POST'])
def detect_emergency():
    """
    Détecte les urgences (respiration, étouffement) sur une image.
    
    Request JSON:
        {
            "image": "<base64_encoded_jpeg>"
        }
    
    Response JSON:
        {
            "success": true,
            "is_emergency": false,
            "reason": null,
            "latency_ms": 85
        }
    """
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'image' field"
            }), 400
        
        # Décoder l'image
        try:
            img = _decode_image(data['image'])
            if img is None:
                raise ValueError("Image decode failed")
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Image decode error: {e}"
            }), 400
        
        # Charger le détecteur
        detector = _get_emergency_detector()
        if detector is None:
            return jsonify({
                "success": False,
                "error": "EmergencyDetector not available"
            }), 503
        
        # Analyser
        try:
            is_emergency, reason = detector.analyze_frame(img)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return jsonify({
                "success": True,
                "is_emergency": is_emergency,
                "reason": reason if is_emergency else None,
                "latency_ms": latency_ms
            })
            
        except Exception as e:
            logger.error(f"Emergency detection error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    except Exception as e:
        logger.error(f"Emergency endpoint error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@vision_bp.route('/status', methods=['GET'])
def vision_status():
    """
    Retourne l'état du service vision.
    
    Response JSON:
        {
            "deepface_available": true,
            "emergency_detector_available": true,
            "gpu_available": false
        }
    """
    import torch
    
    return jsonify({
        "deepface_available": _get_deepface() is not None,
        "emergency_detector_available": _get_emergency_detector() is not None,
        "gpu_available": torch.cuda.is_available() if 'torch' in sys.modules else False,
    })


@vision_bp.route('/analyze', methods=['POST'])
def analyze_full():
    """
    Analyse complète (émotion + urgence) en une seule requête.
    Optimise les allers-retours réseau.
    
    Request JSON:
        {
            "image": "<base64_encoded_jpeg>",
            "analyze_emotion": true,
            "analyze_emergency": true
        }
    
    Response JSON:
        {
            "success": true,
            "emotion": {"detected": true, "value": "happy", "confidence": 0.87},
            "emergency": {"detected": false, "is_emergency": false},
            "latency_ms": 520
        }
    """
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"success": False, "error": "Missing 'image'"}), 400
        
        # Options
        analyze_emotion = data.get('analyze_emotion', True)
        analyze_emergency = data.get('analyze_emergency', True)
        
        # Décoder l'image
        try:
            img = _decode_image(data['image'])
        except Exception as e:
            return jsonify({"success": False, "error": f"Decode: {e}"}), 400
        
        result = {"success": True}
        
        # Emotion
        if analyze_emotion:
            df = _get_deepface()
            if df:
                try:
                    res = df.analyze(img, actions=['emotion'], 
                                    enforce_detection=False, silent=True)
                    result["emotion"] = {
                        "detected": True,
                        "value": res[0].get('dominant_emotion', 'unknown'),
                        "confidence": res[0].get('emotion', {}).get(
                            res[0].get('dominant_emotion', ''), 0) / 100.0
                    }
                except Exception:
                    result["emotion"] = {"detected": False, "error": "analysis_failed"}
            else:
                result["emotion"] = {"detected": False, "error": "unavailable"}
        
        # Emergency
        if analyze_emergency:
            detector = _get_emergency_detector()
            if detector:
                try:
                    is_emerg, reason = detector.analyze_frame(img)
                    result["emergency"] = {
                        "detected": True,
                        "is_emergency": is_emerg,
                        "reason": reason if is_emerg else None
                    }
                except Exception:
                    result["emergency"] = {"detected": False, "error": "analysis_failed"}
            else:
                result["emergency"] = {"detected": False, "error": "unavailable"}
        
        result["latency_ms"] = int((time.time() - start_time) * 1000)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

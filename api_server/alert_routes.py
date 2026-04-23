

from flask import Blueprint, jsonify, request, current_app
import sqlite3
from datetime import datetime
from utils.mail_service import send_alert_notification
from extensions import socketio


# Create Blueprint.
alerts_bp = Blueprint('alerts', __name__)


def get_db_connection():
    """
    Create a database connection to the MediBot SQLite database.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


@alerts_bp.route('', methods=['GET'])
def get_all_alerts():
    """
    GET /api/alerts
    
    Retrieve all alerts from the database.
    
    Query Parameters:
        limit (int): Maximum number of alerts to return (default: 100)
        status (str): Filter by status ('handled', 'unhandled')
    
    Returns:
        JSON: List of alerts with patient information
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        status_filter = request.args.get('status', None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query with JOIN to get patient info
        query = """
            SELECT 
                a.alert_id as id,
                a.patient_id,
                COALESCE(a.alert_type, 'general') as alert_type,
                COALESCE(a.severity, 'medium') as severity,
                a.message,
                a.created_at as timestamp,
                a.handled,
                a.handled_at,
                a.handled_by,
                p.first_name || ' ' || p.last_name as patient_name,
                p.room_number,
                p.age
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.patient_id
            WHERE 1=1
        """
        
        params = []
        
        # Apply status filter
        if status_filter == 'handled':
            query += " AND a.handled = 1"
        elif status_filter == 'unhandled':
            query += " AND a.handled = 0"
        
        # Order by timestamp (most recent first)
        query += " ORDER BY a.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        alerts = []
        for row in rows:
            alerts.append({
                "id": row["id"],
                "patient_id": row["patient_id"],
                "patient_name": row["patient_name"],
                "room_number": row["room_number"],
                "age": row["age"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "message": row["message"],
                "timestamp": row["timestamp"],
                "handled": bool(row["handled"]),
                "handled_at": row["handled_at"],
                "handled_by": row["handled_by"]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "count": len(alerts),
            "alerts": alerts
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@alerts_bp.route('', methods=['POST'])
def create_alert():
    """
    POST /api/alerts

    Create a new alert from the robot or alert system.

    Request Body:
        {
            "patient_id": "PAT001",
            "message": "URGENCE - ...",
            "alert_type": "emergency" | "general" | "call",
            "severity": "low" | "medium" | "high",
            "patient_name": "Nom du patient" (optional),
            "room_number": "203" (optional)
        }

    Returns:
        JSON: Success status and created alert ID
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        patient_id = data.get('patient_id', 'UNKNOWN')
        message = data.get('message') or data.get('reason', 'Alerte sans message')
        alert_type = data.get('alert_type', 'general')
        severity = data.get('severity', 'medium')

        # ── RÈGLE STRICTE : l'ID DOIT respecter le format PATxxx ───────────────
        import re
        if not patient_id or not re.match(r"^PAT\d+$", str(patient_id).strip(), re.IGNORECASE):
            print(f"[ALERTE BLOQUÉE] patient_id invalide ('{patient_id}') — requête refusée.")
            return jsonify({"success": False, "error": "patient_id doit être de la forme PATxxx"}), 400
        patient_id = str(patient_id).strip().upper()
        # ──────────────────────────────────────────────────────────────────────────────────────

        # Support legacy format from emotion_detection/alert_system.py
        if 'priority' in data:
            severity = 'high' if data['priority'] >= 2 else 'medium'
        if 'reason' in data and not data.get('message'):
            message = data['reason']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alerts (patient_id, message, alert_type, severity)
            VALUES (?, ?, ?, ?)
        """, (patient_id, message, alert_type, severity))

        alert_id = cursor.lastrowid
        conn.commit()

        # Récupérer patient_name et room_number pour le payload WebSocket
        cursor.execute("""
            SELECT first_name || ' ' || last_name as patient_name, room_number
            FROM patients WHERE patient_id = ?
        """, (patient_id,))
        prow = cursor.fetchone()
        conn.close()

        patient_name = prow["patient_name"] if prow else None
        room_number = prow["room_number"] if prow else None

        print(f"✓ Alerte #{alert_id} créée: [{severity.upper()}] {message[:80]}")

        # Émettre l'alerte en temps réel via WebSocket
        alert_payload = {
            "id": alert_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "room_number": room_number,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        socketio.emit('new_alert', alert_payload)

        return jsonify({
            "success": True,
            "alert_id": alert_id,
            "message": "Alert created successfully"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@alerts_bp.route('/unhandled', methods=['GET'])
def get_unhandled_alerts():
    """
    GET /api/alerts/unhandled
    
    Retrieve only unhandled (active) alerts.
    This is the primary endpoint for the nurse dashboard.
    
    Returns:
        JSON: List of unhandled alerts
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                a.alert_id as id,
                a.patient_id,
                COALESCE(a.alert_type, 'general') as alert_type,
                COALESCE(a.severity, 'medium') as severity,
                a.message,
                a.created_at as timestamp,
                p.first_name || ' ' || p.last_name as patient_name,
                p.room_number,
                p.age
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.handled = 0
            ORDER BY a.created_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": row["id"],
                "patient_id": row["patient_id"],
                "patient_name": row["patient_name"],
                "room_number": row["room_number"],
                "age": row["age"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "message": row["message"],
                "timestamp": row["timestamp"]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "count": len(alerts),
            "alerts": alerts
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@alerts_bp.route('/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """
    POST /api/alerts/<id>/acknowledge
    
    Mark an alert as handled/acknowledged by a nurse.
    
    Request Body:
        {
            "handled_by": "Nurse Name" (optional)
        }
    
    Returns:
        JSON: Success status and updated alert info
    """
    try:
        # Get request data
        data = request.get_json() or {}
        handled_by = data.get('handled_by', 'Unknown Nurse')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if alert exists
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        alert = cursor.fetchone()
        
        if not alert:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404
        
        # Mark alert as handled (UPDATE instead of DELETE)
        cursor.execute("""
            UPDATE alerts 
            SET handled = 1, 
                handled_at = datetime('now'), 
                handled_by = ?
            WHERE alert_id = ?
        """, (handled_by, alert_id))
        
        conn.commit()
        conn.close()
        
        # Send notification (optional)
        try:
            send_alert_notification(
                alert_id=alert_id,
                status="acknowledged",
                handled_by=handled_by
            )
        except Exception as e:
            print(f"⚠️  Notification failed: {e}")

        # Notifier le dashboard en temps réel
        socketio.emit('alert_acknowledged', {
            "alert_id": alert_id,
            "handled_by": handled_by,
        })

        return jsonify({
            "success": True,
            "message": "Alert acknowledged successfully",
            "alert_id": alert_id,
            "handled_by": handled_by
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@alerts_bp.route('/<int:alert_id>', methods=['GET'])
def get_alert_details(alert_id):
    """
    GET /api/alerts/<id>
    
    Retrieve detailed information about a specific alert.
    
    Returns:
        JSON: Alert details with full patient information
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                a.alert_id as id,
                a.patient_id,
                COALESCE(a.alert_type, 'general') as alert_type,
                COALESCE(a.severity, 'medium') as severity,
                a.message,
                a.created_at as timestamp,
                a.handled,
                a.handled_at,
                a.handled_by,
                p.first_name || ' ' || p.last_name as patient_name,
                p.room_number,
                p.age
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.alert_id = ?
        """
        
        cursor.execute(query, (alert_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404
        
        alert = {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "alert_type": row["alert_type"],
            "severity": row["severity"],
            "message": row["message"],
            "timestamp": row["timestamp"],
            "handled": bool(row["handled"]),
            "handled_at": row["handled_at"],
            "handled_by": row["handled_by"],
            "patient": {
                "name": row["patient_name"],
                "room_number": row["room_number"],
                "age": row["age"]
            }
        }
        
        conn.close()
        
        return jsonify({
            "success": True,
            "alert": alert
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@alerts_bp.route('/delete_all', methods=['DELETE'])
def delete_all_alerts():
    """
    DELETE /api/alerts/delete_all

    Supprime toutes les alertes de la base de données.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alerts")
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "deleted": deleted,
            "message": f"{deleted} alerte(s) supprimée(s)"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@alerts_bp.route('/stats', methods=['GET'])
def get_alert_stats():
    """
    GET /api/alerts/stats
    
    Retrieve alert statistics for dashboard overview.
    
    Returns:
        JSON: Alert statistics (total, unhandled, by severity, etc.)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total alerts
        cursor.execute("SELECT COUNT(*) as count FROM alerts")
        total = cursor.fetchone()["count"]
        
        # Unhandled alerts
        cursor.execute("SELECT COUNT(*) as count FROM alerts WHERE handled = 0")
        unhandled = cursor.fetchone()["count"]
        
        handled = total - unhandled
        
        # Recent alerts (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM alerts 
            WHERE datetime(created_at) >= datetime('now', '-1 day')
        """)
        recent_24h = cursor.fetchone()["count"]
        
        # By severity
        cursor.execute("""
            SELECT COALESCE(severity, 'medium') as sev, COUNT(*) as count
            FROM alerts WHERE handled = 0
            GROUP BY sev
        """)
        by_severity = {row["sev"]: row["count"] for row in cursor.fetchall()}
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_alerts": total,
                "unhandled_alerts": unhandled,
                "handled_alerts": handled,
                "by_severity": by_severity,
                "recent_24h": recent_24h
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

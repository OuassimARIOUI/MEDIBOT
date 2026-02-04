

from flask import Blueprint, jsonify, request, current_app
import sqlite3
from datetime import datetime
from utils.mail_service import send_alert_notification


# Create Blueprint
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
                a.id,
                a.patient_id,
                a.alert_type,
                a.severity,
                a.message,
                a.timestamp,
                a.handled,
                a.handled_at,
                a.handled_by,
                p.name as patient_name,
                p.room_number,
                p.age,
                p.medical_condition
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.id
            WHERE 1=1
        """
        
        params = []
        
        # Apply status filter
        if status_filter == 'handled':
            query += " AND a.handled = 1"
        elif status_filter == 'unhandled':
            query += " AND a.handled = 0"
        
        # Order by timestamp (most recent first)
        query += " ORDER BY a.timestamp DESC LIMIT ?"
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
                "medical_condition": row["medical_condition"],
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
                a.id,
                a.patient_id,
                a.alert_type,
                a.severity,
                a.message,
                a.timestamp,
                p.name as patient_name,
                p.room_number,
                p.age,
                p.medical_condition
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.id
            WHERE a.handled = 0
            ORDER BY a.severity DESC, a.timestamp DESC
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
                "medical_condition": row["medical_condition"],
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
        cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        alert = cursor.fetchone()
        
        if not alert:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404
        
        # Check if already handled
        if alert["handled"]:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Alert already handled",
                "handled_at": alert["handled_at"],
                "handled_by": alert["handled_by"]
            }), 400
        
        # Update alert status
        handled_at = datetime.now().isoformat()
        cursor.execute("""
            UPDATE alerts 
            SET handled = 1, handled_at = ?, handled_by = ?
            WHERE id = ?
        """, (handled_at, handled_by, alert_id))
        
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
        
        return jsonify({
            "success": True,
            "message": "Alert acknowledged successfully",
            "alert_id": alert_id,
            "handled_at": handled_at,
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
                a.*,
                p.name as patient_name,
                p.room_number,
                p.age,
                p.gender,
                p.medical_condition,
                p.admission_date
            FROM alerts a
            LEFT JOIN patients p ON a.patient_id = p.id
            WHERE a.id = ?
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
                "age": row["age"],
                "gender": row["gender"],
                "medical_condition": row["medical_condition"],
                "admission_date": row["admission_date"]
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
        
        # By severity
        cursor.execute("""
            SELECT severity, COUNT(*) as count 
            FROM alerts 
            WHERE handled = 0
            GROUP BY severity
        """)
        severity_counts = {row["severity"]: row["count"] for row in cursor.fetchall()}
        
        # Recent alerts (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM alerts 
            WHERE datetime(timestamp) >= datetime('now', '-1 day')
        """)
        recent_24h = cursor.fetchone()["count"]
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_alerts": total,
                "unhandled_alerts": unhandled,
                "handled_alerts": total - unhandled,
                "by_severity": severity_counts,
                "recent_24h": recent_24h
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

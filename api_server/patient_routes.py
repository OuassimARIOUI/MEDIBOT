
from flask import Blueprint, jsonify, request, current_app
import sqlite3


# Create Blueprint
patients_bp = Blueprint('patients', __name__)


def get_db_connection():
    """
    Create a database connection to the MediBot SQLite database.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@patients_bp.route('', methods=['GET'])
def get_all_patients():
    """
    GET /api/patients
    
    Retrieve all patients from the database.
    
    Query Parameters:
        limit (int): Maximum number of patients to return (default: 50)
        room (str): Filter by room number
    
    Returns:
        JSON: List of patients with basic information
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        room_filter = request.args.get('room', None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                patient_id as id,
                first_name,
                last_name,
                first_name || ' ' || last_name as name,
                age,
                room_number
            FROM patients
            WHERE 1=1
        """
        
        params = []
        
        # Apply room filter
        if room_filter:
            query += " AND room_number = ?"
            params.append(room_filter)
        
        query += " ORDER BY room_number ASC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            patients.append({
                "id": row["id"],
                "name": row["name"],
                "age": row["age"],
                "room_number": row["room_number"]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "count": len(patients),
            "patients": patients
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@patients_bp.route('/<patient_id>', methods=['GET'])
def get_patient_details(patient_id):
    """
    GET /api/patients/<id>
    
    Retrieve detailed information about a specific patient,
    including their current medications.
    
    Returns:
        JSON: Patient details with medication list
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get patient information
        cursor.execute("""
            SELECT 
                patient_id as id,
                first_name,
                last_name,
                first_name || ' ' || last_name as name,
                age,
                room_number
            FROM patients 
            WHERE patient_id = ?
        """, (patient_id,))
        
        patient_row = cursor.fetchone()
        
        if not patient_row:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Patient not found"
            }), 404
        
        # Get patient's medications
        cursor.execute("""
            SELECT 
                medication_id as id,
                medicine_name as name,
                next_time as frequency
            FROM medications
            WHERE patient_id = ?
        """, (patient_id,))
        
        medication_rows = cursor.fetchall()
        
        medications = []
        for med in medication_rows:
            medications.append({
                "id": med["id"],
                "name": med["name"],
                "frequency": med["frequency"]
            })
        
        # Get recent alerts for this patient
        cursor.execute("""
            SELECT 
                alert_id as id,
                'general' as alert_type,
                message,
                created_at as timestamp,
                0 as handled
            FROM alerts
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (patient_id,))
        
        alert_rows = cursor.fetchall()
        
        recent_alerts = []
        for alert in alert_rows:
            recent_alerts.append({
                "id": alert["id"],
                "alert_type": alert["alert_type"],
                "message": alert["message"],
                "timestamp": alert["timestamp"],
                "handled": bool(alert["handled"])
            })
        
        conn.close()
        
        # Build patient details
        patient = {
            "id": patient_row["id"],
            "name": patient_row["name"],
            "age": patient_row["age"],
            "room_number": patient_row["room_number"],
            "medications": medications,
            "recent_alerts": recent_alerts
        }
        
        return jsonify({
            "success": True,
            "patient": patient
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@patients_bp.route('/<patient_id>/medications', methods=['GET'])
def get_patient_medications(patient_id):
    """
    GET /api/patients/<id>/medications
    
    Retrieve only the medications for a specific patient.
    
    Returns:
        JSON: List of medications for the patient
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if patient exists
        cursor.execute("SELECT patient_id FROM patients WHERE patient_id = ?", (patient_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                "success": False,
                "error": "Patient not found"
            }), 404
        
        # Get medications
        cursor.execute("""
            SELECT 
                medication_id as id,
                medicine_name as name,
                next_time as frequency
            FROM medications
            WHERE patient_id = ?
        """, (patient_id,))
        
        rows = cursor.fetchall()
        
        medications = []
        for row in rows:
            medications.append({
                "id": row["id"],
                "name": row["name"],
                "frequency": row["frequency"]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "count": len(medications),
            "medications": medications
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@patients_bp.route('/<patient_id>/alerts', methods=['GET'])
def get_patient_alerts(patient_id):
    """
    GET /api/patients/<id>/alerts
    
    Retrieve all alerts for a specific patient.
    
    Query Parameters:
        limit (int): Maximum number of alerts to return (default: 20)
        status (str): Filter by status ('handled', 'unhandled')
    
    Returns:
        JSON: List of alerts for the patient
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        status_filter = request.args.get('status', None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if patient exists
        cursor.execute("SELECT patient_id, first_name, last_name FROM patients WHERE patient_id = ?", (patient_id,))
        patient = cursor.fetchone()
        
        if not patient:
            conn.close()
            return jsonify({
                "success": False,
                "error": "Patient not found"
            }), 404
        
        # Build query
        query = """
            SELECT 
                alert_id as id,
                'general' as alert_type,
                message,
                created_at as timestamp,
                0 as handled
            FROM alerts
            WHERE patient_id = ?
        """
        
        params = [patient_id]
        
        if status_filter == 'handled':
            query += " AND 0 = 1"  # No handled alerts in this schema
        elif status_filter == 'unhandled':
            query += " AND 1 = 1"  # All alerts are unhandled
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": row["id"],
                "alert_type": row["alert_type"],
                "message": row["message"],
                "timestamp": row["timestamp"],
                "handled": bool(row["handled"])
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "patient_name": f"{patient['first_name']} {patient['last_name']}",
            "count": len(alerts),
            "alerts": alerts
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@patients_bp.route('/stats', methods=['GET'])
def get_patient_stats():
    """
    GET /api/patients/stats
    
    Retrieve patient statistics for dashboard overview.
    
    Returns:
        JSON: Patient statistics
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total patients
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        total_patients = cursor.fetchone()["count"]
        
        # Patients with active alerts
        cursor.execute("""
            SELECT COUNT(DISTINCT patient_id) as count 
            FROM alerts 
            WHERE handled = 0
        """)
        patients_with_alerts = cursor.fetchone()["count"]
        
        # Average age
        cursor.execute("SELECT AVG(age) as avg_age FROM patients")
        avg_age = cursor.fetchone()["avg_age"]
        
        conn.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_patients": total_patients,
                "patients_with_active_alerts": patients_with_alerts,
                "average_age": round(avg_age, 1) if avg_age else 0
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

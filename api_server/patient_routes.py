
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
                id,
                name,
                age,
                gender,
                room_number,
                medical_condition,
                admission_date,
                emergency_contact
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
                "gender": row["gender"],
                "room_number": row["room_number"],
                "medical_condition": row["medical_condition"],
                "admission_date": row["admission_date"],
                "emergency_contact": row["emergency_contact"]
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


@patients_bp.route('/<int:patient_id>', methods=['GET'])
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
            SELECT * FROM patients WHERE id = ?
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
                m.id,
                m.name,
                m.dosage,
                m.frequency,
                m.side_effects,
                m.instructions
            FROM medications m
            WHERE m.id IN (
                SELECT medication_id 
                FROM patient_medications 
                WHERE patient_id = ?
            )
        """, (patient_id,))
        
        medication_rows = cursor.fetchall()
        
        medications = []
        for med in medication_rows:
            medications.append({
                "id": med["id"],
                "name": med["name"],
                "dosage": med["dosage"],
                "frequency": med["frequency"],
                "side_effects": med["side_effects"],
                "instructions": med["instructions"]
            })
        
        # Get recent alerts for this patient
        cursor.execute("""
            SELECT 
                id,
                alert_type,
                severity,
                message,
                timestamp,
                handled
            FROM alerts
            WHERE patient_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (patient_id,))
        
        alert_rows = cursor.fetchall()
        
        recent_alerts = []
        for alert in alert_rows:
            recent_alerts.append({
                "id": alert["id"],
                "alert_type": alert["alert_type"],
                "severity": alert["severity"],
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
            "gender": patient_row["gender"],
            "room_number": patient_row["room_number"],
            "medical_condition": patient_row["medical_condition"],
            "admission_date": patient_row["admission_date"],
            "emergency_contact": patient_row["emergency_contact"],
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


@patients_bp.route('/<int:patient_id>/medications', methods=['GET'])
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
        cursor.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                "success": False,
                "error": "Patient not found"
            }), 404
        
        # Get medications
        cursor.execute("""
            SELECT 
                m.id,
                m.name,
                m.dosage,
                m.frequency,
                m.side_effects,
                m.instructions
            FROM medications m
            WHERE m.id IN (
                SELECT medication_id 
                FROM patient_medications 
                WHERE patient_id = ?
            )
        """, (patient_id,))
        
        rows = cursor.fetchall()
        
        medications = []
        for row in rows:
            medications.append({
                "id": row["id"],
                "name": row["name"],
                "dosage": row["dosage"],
                "frequency": row["frequency"],
                "side_effects": row["side_effects"],
                "instructions": row["instructions"]
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


@patients_bp.route('/<int:patient_id>/alerts', methods=['GET'])
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
        cursor.execute("SELECT id, name FROM patients WHERE id = ?", (patient_id,))
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
                id,
                alert_type,
                severity,
                message,
                timestamp,
                handled,
                handled_at,
                handled_by
            FROM alerts
            WHERE patient_id = ?
        """
        
        params = [patient_id]
        
        if status_filter == 'handled':
            query += " AND handled = 1"
        elif status_filter == 'unhandled':
            query += " AND handled = 0"
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": row["id"],
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
            "patient_id": patient_id,
            "patient_name": patient["name"],
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

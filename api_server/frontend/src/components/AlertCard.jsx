/**
 * AlertCard Component
 * ===================
 * 
 * Displays a single alert with patient information and acknowledge button.
 */

import React, { useState } from 'react';

const AlertCard = ({ alert, onAcknowledge }) => {
  const [isAcknowledging, setIsAcknowledging] = useState(false);

  const handleAcknowledge = async () => {
    setIsAcknowledging(true);
    try {
      await onAcknowledge(alert.id);
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
      alert('Erreur lors de la confirmation de l\'alerte');
    } finally {
      setIsAcknowledging(false);
    }
  };

  // Determine severity class
  const getSeverityClass = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
      case 'high':
        return 'severity-critical';
      case 'medium':
      case 'moderate':
        return 'severity-medium';
      case 'low':
        return 'severity-low';
      default:
        return 'severity-medium';
    }
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return timestamp;
    }
  };

  // Get icon based on alert type
  const getAlertIcon = (alertType) => {
    switch (alertType?.toLowerCase()) {
      case 'emergency':
        return 'fa-solid fa-circle-exclamation';
      case 'pain':
        return 'fa-solid fa-heartbeat';
      case 'medication':
        return 'fa-solid fa-pills';
      case 'fall':
        return 'fa-solid fa-person-falling';
      default:
        return 'fa-solid fa-bell';
    }
  };

  return (
    <div className={`alert-card ${getSeverityClass(alert.severity)}`}>
      <div className="alert-header">
        <div className="alert-icon">
          <i className={getAlertIcon(alert.alert_type)}></i>
        </div>
        <div className="alert-info">
          <h3 className="alert-title">
            {alert.alert_type || 'Alert'}
          </h3>
          <span className={`severity-badge ${getSeverityClass(alert.severity)}`}>
            {alert.severity || 'Medium'}
          </span>
        </div>
      </div>

      <div className="alert-body">
        <div className="patient-info">
          <div className="info-row">
            <span className="info-label">
              <i className="fa-solid fa-user"></i> Patient:
            </span>
            <span className="info-value">{alert.patient_name || 'Inconnu'}</span>
          </div>
          <div className="info-row">
            <span className="info-label">
              <i className="fa-solid fa-door-open"></i> Chambre:
            </span>
            <span className="info-value">{alert.room_number || 'N/A'}</span>
          </div>
          {alert.age && (
            <div className="info-row">
              <span className="info-label">
                <i className="fa-solid fa-calendar"></i> Âge:
              </span>
              <span className="info-value">{alert.age} ans</span>
            </div>
          )}
        </div>

        <div className="alert-message">
          <p>{alert.message}</p>
        </div>

        {alert.medical_condition && (
          <div className="medical-condition">
            <span className="condition-label">
              <i className="fa-solid fa-file-medical"></i> Condition médicale:
            </span>
            <span className="condition-value">{alert.medical_condition}</span>
          </div>
        )}

        <div className="alert-timestamp">
          <i className="fa-solid fa-clock"></i> {formatTime(alert.timestamp)}
        </div>
      </div>

      <div className="alert-footer">
        {!alert.handled ? (
          <button
            className="btn btn-acknowledge"
            onClick={handleAcknowledge}
            disabled={isAcknowledging}
          >
            {isAcknowledging ? (
              <>
                <i className="fa-solid fa-spinner fa-spin"></i> En cours...
              </>
            ) : (
              <>
                <i className="fa-solid fa-check"></i> Prise en charge
              </>
            )}
          </button>
        ) : (
          <div className="alert-handled">
            <span className="handled-badge">
              <i className="fa-solid fa-check-circle"></i> Traité
            </span>
            {alert.handled_by && (
              <span className="handled-by">par {alert.handled_by}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AlertCard;

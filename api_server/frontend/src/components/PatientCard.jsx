/**
 * PatientCard Component
 * =====================
 * 
 * Displays patient information with medications and recent alerts.
 */

import React, { useState } from 'react';

const PatientCard = ({ patient, onViewDetails }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails(patient.id);
    }
  };

  // Count active alerts
  const activeAlertsCount = patient.recent_alerts
    ? patient.recent_alerts.filter(a => !a.handled).length
    : 0;

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('fr-FR');
    } catch {
      return dateString;
    }
  };

  return (
    <div className={`patient-card ${activeAlertsCount > 0 ? 'has-alerts' : ''}`}>
      <div className="patient-header" onClick={toggleExpand}>
        <div className="patient-main-info">
          <h3 className="patient-name">
            {patient.name}
          </h3>
          <span className="room-badge">
            🏥 Chambre {patient.room_number}
          </span>
        </div>
        
        {activeAlertsCount > 0 && (
          <div className="alert-indicator">
            <span className="alert-count">{activeAlertsCount}</span>
            🔔
          </div>
        )}
        
        <button className="expand-btn">
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      <div className="patient-basic-info">
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Âge:</span>
            <span>{patient.age} ans</span>
          </div>
          <div className="info-item">
            <span className="info-label">Genre:</span>
            <span>{patient.gender === 'M' ? 'Homme' : patient.gender === 'F' ? 'Femme' : patient.gender}</span>
          </div>
        </div>
        
        {patient.medical_condition && (
          <div className="medical-condition-box">
            <span className="condition-label">📋 Condition:</span>
            <span>{patient.medical_condition}</span>
          </div>
        )}
      </div>

      {isExpanded && (
        <div className="patient-details">
          {patient.admission_date && (
            <div className="detail-section">
              <strong>Date d'admission:</strong>
              <span>{formatDate(patient.admission_date)}</span>
            </div>
          )}

          {patient.emergency_contact && (
            <div className="detail-section">
              <strong>Contact d'urgence:</strong>
              <span>{patient.emergency_contact}</span>
            </div>
          )}

          {patient.medications && patient.medications.length > 0 && (
            <div className="detail-section medications-section">
              <strong>💊 Médicaments ({patient.medications.length}):</strong>
              <ul className="medication-list">
                {patient.medications.map((med, index) => (
                  <li key={index} className="medication-item">
                    <span className="med-name">{med.name}</span>
                    {med.dosage && (
                      <span className="med-dosage"> - {med.dosage}</span>
                    )}
                    {med.frequency && (
                      <span className="med-frequency"> ({med.frequency})</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {patient.recent_alerts && patient.recent_alerts.length > 0 && (
            <div className="detail-section alerts-section">
              <strong>🔔 Alertes récentes:</strong>
              <ul className="alerts-list">
                {patient.recent_alerts.slice(0, 3).map((alert, index) => (
                  <li key={index} className={`alert-item ${alert.handled ? 'handled' : 'active'}`}>
                    <span className="alert-type">{alert.alert_type}</span>
                    <span className={`alert-status ${alert.handled ? 'handled' : 'active'}`}>
                      {alert.handled ? '✓' : '⚠️'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="patient-actions">
            <button className="btn btn-details" onClick={handleViewDetails}>
              Voir détails complets
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PatientCard;

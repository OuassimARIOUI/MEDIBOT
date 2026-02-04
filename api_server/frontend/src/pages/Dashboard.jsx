/**
 * Dashboard Page
 * ==============
 * 
 * Main dashboard page displaying alerts and patients.
 * Implements auto-refresh polling for real-time updates.
 */

import React, { useState, useEffect } from 'react';
import AlertCard from '../components/AlertCard';
import PatientCard from '../components/PatientCard';
import { 
  getUnhandledAlerts, 
  getAllPatients, 
  acknowledgeAlert,
  getAlertStats,
  getPatientStats
} from '../api';

const Dashboard = () => {
  // State management
  const [alerts, setAlerts] = useState([]);
  const [patients, setPatients] = useState([]);
  const [alertStats, setAlertStats] = useState(null);
  const [patientStats, setPatientStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [activeTab, setActiveTab] = useState('alerts'); // 'alerts' or 'patients'

  // Fetch alerts from API
  const fetchAlerts = async () => {
    try {
      const response = await getUnhandledAlerts();
      if (response.data.success) {
        setAlerts(response.data.alerts);
      }
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError('Erreur lors du chargement des alertes');
    }
  };

  // Fetch patients from API
  const fetchPatients = async () => {
    try {
      const response = await getAllPatients({ limit: 20 });
      if (response.data.success) {
        // Fetch detailed info for each patient (including medications and alerts)
        const patientDetails = await Promise.all(
          response.data.patients.map(async (patient) => {
            try {
              const detailResponse = await fetch(
                `http://localhost:5000/api/patients/${patient.id}`
              );
              const detailData = await detailResponse.json();
              return detailData.success ? detailData.patient : patient;
            } catch {
              return patient;
            }
          })
        );
        setPatients(patientDetails);
      }
    } catch (err) {
      console.error('Error fetching patients:', err);
      setError('Erreur lors du chargement des patients');
    }
  };

  // Fetch statistics
  const fetchStats = async () => {
    try {
      const [alertStatsRes, patientStatsRes] = await Promise.all([
        getAlertStats(),
        getPatientStats()
      ]);
      
      if (alertStatsRes.data.success) {
        setAlertStats(alertStatsRes.data.stats);
      }
      
      if (patientStatsRes.data.success) {
        setPatientStats(patientStatsRes.data.stats);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  // Fetch all data
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        fetchAlerts(),
        fetchPatients(),
        fetchStats()
      ]);
      setLastUpdate(new Date());
    } catch (err) {
      setError('Erreur lors du chargement des données');
    } finally {
      setLoading(false);
    }
  };

  // Handle alert acknowledgment
  const handleAcknowledgeAlert = async (alertId) => {
    try {
      const nurseName = prompt('Votre nom:', 'Infirmier(ère)');
      if (!nurseName) return;

      await acknowledgeAlert(alertId, nurseName);
      
      // Refresh alerts list
      await fetchAlerts();
      await fetchStats();
      
      alert('✓ Alerte prise en charge avec succès');
    } catch (err) {
      console.error('Error acknowledging alert:', err);
      throw err;
    }
  };

  // Handle patient details view
  const handleViewPatientDetails = (patientId) => {
    alert(`Affichage des détails du patient ${patientId} (à implémenter)`);
    // TODO: Implement modal or navigation to patient detail page
  };

  // Initial data load
  useEffect(() => {
    fetchData();
  }, []);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData();
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, []);

  // Format last update time
  const formatLastUpdate = () => {
    return lastUpdate.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  if (loading && alerts.length === 0 && patients.length === 0) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Chargement des données...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* Statistics Bar */}
      <div className="stats-bar">
        <div className="stat-card">
          <div className="stat-icon">🚨</div>
          <div className="stat-content">
            <div className="stat-value">{alertStats?.unhandled_alerts || 0}</div>
            <div className="stat-label">Alertes actives</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">✓</div>
          <div className="stat-content">
            <div className="stat-value">{alertStats?.handled_alerts || 0}</div>
            <div className="stat-label">Alertes traitées</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <div className="stat-value">{patientStats?.total_patients || 0}</div>
            <div className="stat-label">Patients</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon">⚠️</div>
          <div className="stat-content">
            <div className="stat-value">{patientStats?.patients_with_active_alerts || 0}</div>
            <div className="stat-label">Patients avec alertes</div>
          </div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="control-bar">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            🚨 Alertes ({alerts.length})
          </button>
          <button 
            className={`tab ${activeTab === 'patients' ? 'active' : ''}`}
            onClick={() => setActiveTab('patients')}
          >
            👥 Patients ({patients.length})
          </button>
        </div>
        
        <div className="control-actions">
          <div className="last-update">
            Dernière mise à jour: {formatLastUpdate()}
          </div>
          <button className="btn btn-refresh" onClick={fetchData}>
            🔄 Actualiser
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Content */}
      <div className="dashboard-content">
        {activeTab === 'alerts' && (
          <div className="alerts-section">
            <div className="section-header">
              <h2>🚨 Alertes Actives</h2>
              {alerts.length === 0 && (
                <span className="no-alerts-badge">✓ Aucune alerte</span>
              )}
            </div>
            
            {alerts.length > 0 ? (
              <div className="alerts-grid">
                {alerts.map(alert => (
                  <AlertCard 
                    key={alert.id} 
                    alert={alert}
                    onAcknowledge={handleAcknowledgeAlert}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">✓</div>
                <h3>Aucune alerte active</h3>
                <p>Toutes les alertes ont été prises en charge.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'patients' && (
          <div className="patients-section">
            <div className="section-header">
              <h2>👥 Patients</h2>
            </div>
            
            {patients.length > 0 ? (
              <div className="patients-grid">
                {patients.map(patient => (
                  <PatientCard 
                    key={patient.id} 
                    patient={patient}
                    onViewDetails={handleViewPatientDetails}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">👥</div>
                <h3>Aucun patient</h3>
                <p>Aucune donnée patient disponible.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;

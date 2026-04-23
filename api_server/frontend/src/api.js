/**
 * API Service Module
 * ==================
 * 
 * Centralized API client for communicating with the Flask backend.
 * All API calls go through this module for consistency.
 */

import axios from 'axios';

// Base API URL (adjust based on environment)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 10000 // 10 seconds
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);


// ============================================================================
// ALERT ENDPOINTS
// ============================================================================

/**
 * Get all alerts
 * @param {Object} params - Query parameters (limit, status)
 * @returns {Promise} - Alert list
 */
export const getAllAlerts = (params = {}) => {
  return apiClient.get('/alerts', { params });
};

/**
 * Get unhandled alerts only
 * @returns {Promise} - Unhandled alert list
 */
export const getUnhandledAlerts = () => {
  return apiClient.get('/alerts/unhandled');
};

/**
 * Get alert details by ID
 * @param {number} alertId - Alert ID
 * @returns {Promise} - Alert details
 */
export const getAlertDetails = (alertId) => {
  return apiClient.get(`/alerts/${alertId}`);
};

/**
 * Acknowledge an alert
 * @param {number} alertId - Alert ID
 * @param {string} handledBy - Name of the nurse
 * @returns {Promise} - Acknowledgment response
 */
export const acknowledgeAlert = (alertId, handledBy = 'Nurse') => {
  return apiClient.post(`/alerts/${alertId}/acknowledge`, {
    handled_by: handledBy
  });
};

/**
 * Get alert statistics
 * @returns {Promise} - Alert stats
 */
export const getAlertStats = () => {
  return apiClient.get('/alerts/stats');
};

/**
 * Delete all alerts
 * @returns {Promise}
 */
export const deleteAllAlerts = () => {
  return apiClient.delete('/alerts/delete_all');
};


// ============================================================================
// PATIENT ENDPOINTS
// ============================================================================

/**
 * Get all patients
 * @param {Object} params - Query parameters (limit, room)
 * @returns {Promise} - Patient list
 */
export const getAllPatients = (params = {}) => {
  return apiClient.get('/patients', { params });
};

/**
 * Get patient details by ID
 * @param {number} patientId - Patient ID
 * @returns {Promise} - Patient details with medications
 */
export const getPatientDetails = (patientId) => {
  return apiClient.get(`/patients/${patientId}`);
};

/**
 * Get patient medications
 * @param {number} patientId - Patient ID
 * @returns {Promise} - Patient medications
 */
export const getPatientMedications = (patientId) => {
  return apiClient.get(`/patients/${patientId}/medications`);
};

/**
 * Get patient alerts
 * @param {number} patientId - Patient ID
 * @param {Object} params - Query parameters (limit, status)
 * @returns {Promise} - Patient alerts
 */
export const getPatientAlerts = (patientId, params = {}) => {
  return apiClient.get(`/patients/${patientId}/alerts`, { params });
};

/**
 * Get patient statistics
 * @returns {Promise} - Patient stats
 */
export const getPatientStats = () => {
  return apiClient.get('/patients/stats');
};


// ============================================================================
// HEALTH CHECK
// ============================================================================

/**
 * Check API health status
 * @returns {Promise} - Health status
 */
export const checkHealth = () => {
  return apiClient.get('/health');
};


// Export default object with all methods
export default {
  // Alerts
  getAllAlerts,
  getUnhandledAlerts,
  getAlertDetails,
  acknowledgeAlert,
  getAlertStats,
  
  // Patients
  getAllPatients,
  getPatientDetails,
  getPatientMedications,
  getPatientAlerts,
  getPatientStats,
  
  // Health
  checkHealth
};

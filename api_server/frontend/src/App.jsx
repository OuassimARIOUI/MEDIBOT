/**
 * MediBot Dashboard App
 * =====================
 * 
 * Main application component for the nurse dashboard.
 */

import React from 'react';
import Dashboard from './pages/Dashboard';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <i className="fas fa-hospital-user"></i>
            <h1>MediBot Nurse Dashboard</h1>
          </div>
          <p>Système de surveillance des alertes patients</p>
        </div>
      </header>
      
      <main className="app-main">
        <Dashboard />
      </main>
      
      <footer className="app-footer">
        <p>© 2026 MediBot - Projet académique M1 S2</p>
      </footer>
    </div>
  );
}

export default App;

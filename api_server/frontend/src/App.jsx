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
          <h1>🏥 MediBot Nurse Dashboard</h1>
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

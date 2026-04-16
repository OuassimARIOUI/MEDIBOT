-- ==========================
-- DATABASE : medibot.db
-- ==========================

PRAGMA foreign_keys = ON;

-- ---------- PATIENTS ----------
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER,
    room_number TEXT,
    discharge_date TEXT
);

-- ---------- MEDICATIONS ----------
CREATE TABLE IF NOT EXISTS medications (
    medication_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    medicine_name TEXT NOT NULL,
    next_time TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- ---------- ALERTS ----------
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT,
    message TEXT,
    alert_type TEXT DEFAULT 'general',
    severity TEXT DEFAULT 'medium',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    handled INTEGER DEFAULT 0,
    handled_at DATETIME,
    handled_by TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- ---------- EMOTION LOGS ----------
CREATE TABLE IF NOT EXISTS emotion_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    emotion TEXT NOT NULL,
    severity TEXT DEFAULT 'low',
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- ==========================
-- DONNÉES INITIALES
-- ==========================

INSERT OR IGNORE INTO patients (patient_id, first_name, last_name, age, room_number, discharge_date) VALUES
('PAT001', 'Ouassim', 'ARIOUI', 72, '203', '15/06/2026'),
('PAT002', 'Asmaa', 'BOUKRAA', 68, '204', '20/06/2026');

INSERT OR IGNORE INTO medications (patient_id, medicine_name, next_time) VALUES
('PAT001', 'doliprane', '22:00'),
('PAT001', 'insuline', '23:30'),
('PAT002', 'paracétamol', '21:00');
INSERT OR IGNORE INTO alerts (patient_id, message) VALUES
('PAT001', 'Patient PAT001 has missed their medication doliprane.'),
('PAT002', 'Patient PAT002 has a critical alert: High blood pressure detected.');

-- ==========================
-- DATABASE : medibot.db
-- ==========================

-- ---------- PATIENTS ----------
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER,
    room_number TEXT
);

-- ---------- MEDICAMENTS ----------
CREATE TABLE IF NOT EXISTS medications (
    medication_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    medicine_name TEXT NOT NULL,
    next_time TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- ---------- ALERTES ----------
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================
-- DONNÉES FIXES (2 PATIENTS)
-- ==========================

INSERT OR IGNORE INTO patients VALUES
('PAT001', 'Jean', 'Dupont', 72, '203'),
('PAT002', 'Marie', 'Martin', 68, '204');

INSERT OR IGNORE INTO medications (patient_id, medicine_name, next_time) VALUES
('PAT001', 'doliprane', '22:00'),
('PAT001', 'insuline', '23:30'),
('PAT002', 'paracétamol', '21:00');

# ☀️ Arogya Setu — Smart Skin Lens & Wellness Companion

A full-stack multilingual dermatology screening, care guidance, and healthcare locator web application. Arogya Setu combines a 3-stage computer vision skin analyzer, a 6-language neural voice assistant, live GPS OpenStreetMap doctor/pharmacy discovery, and role-based workflows backed by a high-concurrency SQLite (WAL) database.

---

## ✨ Key Features

* **🔍 Smart Skin Lens (3-Stage Vision AI):**
  * **Live Camera & Device Upload:** Capture skin photos directly via a 260×260 reticle viewfinder or upload images from any device.
  * **Background-Masked YCbCr Analysis:** Separates human skin chrominance from room shadows and non-skin objects.
  * **Accurate Triage & Care:** Distinguishes between **Non-Skin Photos**, **Normal/Healthy Skin**, **Mild/Moderate Conditions** (e.g., *Tinea Corporis / Fungal Ringworm*, *Allergic Contact Dermatitis / Mild Eczema* with OTC medicine suggestions), and **High-Severity Lesions** (with immediate specialist referral alerts).
* **🎧 6-Language Neural Voice Assistant:**
  * Full UI translation and natural voice readout in **English (`en-IN`)**, **Kannada (`kn-IN`)**, **Hindi (`hi-IN`)**, **Tamil (`ta-IN`)**, **Telugu (`te-IN`)**, and **Malayalam (`ml-IN`)**.
  * Streams native MP3 speech via `/api/v1/tts` with an offline ISCII-to-Devanagari phonetic fallback and **Listen, Pause, Resume, and Stop** controls.
* **📍 Live GPS Doctor & Pharmacy Locator:**
  * Uses browser Geolocation, OpenStreetMap Nominatim geocoding, and interactive Leaflet maps to find nearby dermatologists, hospitals, and Jan Aushadhi pharmacies for any city or PIN code.
* **🔐 Role-Agnostic Login & Role-Adaptive Workspaces:**
  * Opens in **Guest User Mode** by default with zero login walls.
  * Single unified Sign-In / Create Account modal that dynamically unlocks role-specific tools for **Citizens (`user`)**, **Healthcare Workers (`worker`)**, and **Supervisors (`admin`)**.
* **🗄️ Self-Healing SQLite Database (WAL Mode):**
  * Persistent storage (`backend/arogya_setu.db`) for users, saved skin scans, appointments, and hospital referrals.

---

## 📁 Project Architecture

```text
Arogya Setu/
├── auto_localhost.py                    # Self-localhost orchestrator (Backend :8000 + Frontend :5173)
├── strat_app.bat / start_app.bat        # 1-Click Windows launcher
├── directory.txt                        # Directory structure reference
├── backend/
│   ├── arogya_setu.db                   # Persistent SQLite database (WAL mode)
│   ├── requirements.txt                 # Python backend dependencies
│   └── app/
│       ├── database.py                  # Self-healing SQLite schema, connection & seed data
│       ├── ml_engine.py                 # 6-language 3-Stage Smart Skin Lens classifier
│       └── main.py                      # REST API & Neural TTS server (Port 8000)
└── frontend/
    ├── index.html                       # Frontend application shell
    ├── package.json                     # React 18 & Leaflet dependencies
    └── src/
        ├── api.js                       # REST API client connected to [http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)
        ├── voiceEngine.js               # 6-language UI dictionaries & phonetic bridge
        ├── App.jsx                      # Main React state & audio controller
        └── components/
            ├── HeaderAndNav.jsx         # Header, language selector, voice controls & tabs
            ├── SmartSkinLens.jsx        # 260x260 camera/upload reticle, YCbCr extractor & report
            ├── HomeandJournal.jsx       # Wellness dashboard, 104/108 helplines & scan history
            ├── Appointments.jsx         # Appointment booking + Worker/Admin reschedule & cancel
            ├── NearbyLocator.jsx        # Live GPS & OpenStreetMap doctor/pharmacy finder
            ├── RolePortals.jsx          # Worker hospital referrals & Admin user/worker control
            └── AuthAndProfileModals.jsx # Sign-In, Create Account & Profile management modals

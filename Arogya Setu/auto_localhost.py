import os
import re
import sys
import time
import json
import socket
import random
import sqlite3
import threading
import webbrowser
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
BACKEND_APP_DIR = os.path.join(BACKEND_DIR, "app")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
FRONTEND_SRC_DIR = os.path.join(FRONTEND_DIR, "src")
FRONTEND_COMP_DIR = os.path.join(FRONTEND_SRC_DIR, "components")
DB_PATH = os.path.join(BACKEND_DIR, "arogya_setu.db")

# ==============================================================================
# 1. SEPARATED BACKEND FILES (Written to backend/app/)
# ==============================================================================
DATABASE_PY = r'''import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "arogya_setu.db")

def _ensure_valid_sqlite():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "rb") as f:
                header = f.read(16)
            if len(header) > 0 and header != b"SQLite format 3\x00":
                os.remove(DB_PATH)
        except OSError:
            pass

def get_connection():
    _ensure_valid_sqlite()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn
    except sqlite3.DatabaseError:
        for ext in ("", "-wal", "-shm"):
            p = DB_PATH + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        phone TEXT DEFAULT '',
        locality TEXT DEFAULT '',
        lang TEXT DEFAULT 'en'
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS scans (
        id TEXT PRIMARY KEY,
        owner_username TEXT NOT NULL,
        person TEXT NOT NULL,
        body_part TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        what_was_in_photo TEXT NOT NULL,
        identified_condition TEXT NOT NULL,
        causes TEXT NOT NULL,
        severity TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        helpful_care TEXT NOT NULL
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        patient_username TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        clinic_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        notes TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Confirmed'
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id TEXT PRIMARY KEY,
        patient_name TEXT NOT NULL,
        condition TEXT NOT NULL,
        urgency TEXT NOT NULL,
        hospital TEXT NOT NULL,
        referred_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active'
    );""")

    if cur.execute("SELECT COUNT(*) as c FROM users;").fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, full_name, role, phone, locality, lang) VALUES (?, ?, ?, ?, ?, ?, ?);",
            [
                ("arjun", "user123", "Arjun Rao", "user", "+91 98450 11223", "Bengaluru", "en"),
                ("kavitha", "worker123", "Kavitha Nair (PHC Nurse)", "worker", "+91 94481 22334", "Community Health Center", "kn"),
                ("ramesh", "admin123", "Dr. Ramesh Hegde (Admin)", "admin", "+91 99001 44556", "District Health Directorate", "en")
            ]
        )

    if cur.execute("SELECT COUNT(*) as c FROM scans;").fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            [
                (
                    "SCN-9012", "arjun", "Arjun Rao", "Arm / Forearm", "2026-10-18 09:15 AM",
                    "Skin surface showing a circular ring-shaped scaly patch",
                    "Tinea Corporis (Superficial Fungal Ringworm)",
                    "Dermatophyte fungi thriving in warm sweat and humidity",
                    "MILD", 92,
                    "Clotrimazole 1% Cream, Terbinafine 1% Ointment | Dermatology Advice: Consult a Dermatologist if ringworm persists beyond 10–14 days."
                ),
                (
                    "SCN-9015", "arjun", "Meenakshi S.", "Back / Torso", "2026-10-18 10:05 AM",
                    "Dark irregularly bordered pigmented lesion on skin",
                    "Atypical Pigmented Lesion / Suspected Melanocytic Dysplasia",
                    "Cumulative UV sun exposure or abnormal melanocyte growth",
                    "HIGH", 91,
                    "Urgent Dermatologist Evaluation & Dermoscopy Required Within 24–48 Hours"
                )
            ]
        )

    if cur.execute("SELECT COUNT(*) as c FROM appointments;").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                "APT-3011", "arjun", "Arjun Rao",
                "City Dermatology & Skin Care Clinic", "Dermatology",
                "2026-10-20", "10:30 AM",
                "Follow-up skin check after Smart Skin Lens scan.", "Confirmed"
            )
        )

    if cur.execute("SELECT COUNT(*) as c FROM referrals;").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO referrals VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                "REF-501", "Meenakshi S.",
                "Atypical Pigmented Lesion / Suspected Melanocytic Dysplasia",
                "HIGH — Immediate Dermatologist Biopsy",
                "District General Hospital (Dermatology OPD)",
                "Kavitha Nair (PHC Nurse)", "Active"
            )
        )

    conn.commit()
    conn.close()
'''

ML_ENGINE_PY = r'''REPORT_TRANSLATIONS = {
    "non_skin": {
        "en": {
            "whatWasInPhoto": "Non-skin object, background scene, or everyday item rather than human skin.",
            "identifiedCondition": "No Skin Disease Detected (Non-Skin Photo) — No Referral Needed",
            "causes": "Not applicable — the camera or uploaded photo does not show human skin.",
            "severity": "NONE",
            "helpfulCare": "No referral needed. Point the camera 10–15 cm from the skin in good lighting to scan a skin spot.",
            "dermatologyRecommendation": "No dermatologist visit needed for this image. If you have a skin concern, please capture a clear close-up photo of the affected skin area or book a general dermatology checkup.",
            "specialistType": "General Dermatologist (MD Skin / DVL) — Optional",
            "consultTimeline": "Only if you have physical skin symptoms"
        },
        "kn": {
            "whatWasInPhoto": "ಮಾನವನ ಚರ್ಮದ ಬದಲಾಗಿ ಇತರ ವಸ್ತು ಅಥವಾ ಹಿನ್ನೆಲೆ ಕಾಣಿಸುತ್ತಿದೆ.",
            "identifiedCondition": "ಚರ್ಮದ ರೋಗ ಕಂಡುಬಂದಿಲ್ಲ (ಇದು ಚರ್ಮದ ಫೋಟೋ ಅಲ್ಲ)",
            "causes": "ಅನ್ವಯಿಸುವುದಿಲ್ಲ — ಅಪ್‌ಲೋಡ್ ಮಾಡಿದ ಫೋಟೋದಲ್ಲಿ ಚರ್ಮದ ಭಾಗ ಕಾಣಿಸುತ್ತಿಲ್ಲ.",
            "severity": "NONE",
            "helpfulCare": "ವೈದ್ಯರ ಶಿಫಾರಸು ಅಗತ್ಯವಿಲ್ಲ. ಚರ್ಮದ ತಪಾಸಣೆಗಾಗಿ ಉತ್ತಮ ಬೆಳಕಿನಲ್ಲಿ ಚರ್ಮದ ಹತ್ತಿರ ಫೋಟೋ ತೆಗೆಯಿರಿ.",
            "dermatologyRecommendation": "ಚರ್ಮದ ಸ್ಪಷ್ಟ ಫೋಟೋ ತೆಗೆದು ಮತ್ತೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ ಅಥವಾ ಚರ್ಮದ ಸಮಸ್ಯೆ ಇದ್ದಲ್ಲಿ ಹತ್ತಿರದ ಚರ್ಮರೋಗ ತಜ್ಞರನ್ನು (Dermatologist) ಸಂಪರ್ಕಿಸಿ.",
            "specialistType": "ಚರ್ಮರೋಗ ತಜ್ಞರು (MD Skin / DVL)",
            "consultTimeline": "ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಲ್ಲಿ ಮಾತ್ರ"
        },
        "hi": {
            "whatWasInPhoto": "मानव त्वचा के बजाय कोई वस्तु, दस्तावेज़ या बाहरी दृश्य दिखाई दे रहा है।",
            "identifiedCondition": "कोई त्वचा रोग नहीं मिला (गैर-त्वचा फोटो)",
            "causes": "लागू नहीं — इस फोटो में मानव त्वचा दिखाई नहीं दे रही है।",
            "severity": "NONE",
            "helpfulCare": "किसी रेफरल की आवश्यकता नहीं है। त्वचा की जांच के लिए अच्छी रोशनी में त्वचा के पास से फोटो लें।",
            "dermatologyRecommendation": "कृपया प्रभावित त्वचा की साफ फोटो लें या किसी भी त्वचा संबंधी समस्या के लिए नजदीकी त्वचा विशेषज्ञ (Dermatologist) से परामर्श लें।",
            "specialistType": "त्वचा विशेषज्ञ (MD Skin / DVL)",
            "consultTimeline": "केवल लक्षण होने पर"
        },
        "ta": {
            "whatWasInPhoto": "மனித தோலுக்கு பதிலாக வேறு பொருள் அல்லது பின்னணி தெரிகிறது.",
            "identifiedCondition": "தோல் நோய் எதுவும் கண்டறியப்படவில்லை",
            "causes": "பொருந்தாது — பதிவேற்றிய புகைப்படத்தில் மனித தோல் இல்லை.",
            "severity": "NONE",
            "helpfulCare": "நல்ல வெளிச்சத்தில் தோலில் இருந்து 10–15 செ.மீ தூரத்தில் புகைப்படம் எடுக்கவும்.",
            "dermatologyRecommendation": "பாதிக்கப்பட்ட தோலின் தெளிவான புகைப்படத்தை எடுக்கவும் அல்லது தோல் மருத்துவரை (Dermatologist) அணுகவும்.",
            "specialistType": "தோல் மருத்துவர் (MD Skin / DVL)",
            "consultTimeline": "அறிகுறிகள் இருந்தால் மட்டும்"
        },
        "te": {
            "whatWasInPhoto": "మనిషి చర్మానికి బదులుగా ఏదో వస్తువు లేదా బ్యాక్‌గ్రౌండ్ కనిపిస్తోంది.",
            "identifiedCondition": "చర్మ వ్యాధి కనుగొనబడలేదు (చర్మం ఫోటో కాదు)",
            "causes": "వర్తించదు — ఈ ఫోటోలో మనిషి చర్మం కనిపించడం లేదు.",
            "severity": "NONE",
            "helpfulCare": "మంచి వెలుతురులో చర్మానికి 10–15 సెం.మీ దూరం నుండి ఫోటో తీయండి.",
            "dermatologyRecommendation": "చర్మ సమస్య ఉంటే స్పష్టమైన ఫోటో తీయండి లేదా సమీప చర్మవ్యాధి నిపుణుడిని (Dermatologist) సంప్రదించండి.",
            "specialistType": "చర్మవ్యాధి నిపుణులు (MD Skin / DVL)",
            "consultTimeline": "లక్షణాలు ఉంటేనే"
        },
        "ml": {
            "whatWasInPhoto": "മനുഷ്യ ചർമ്മത്തിന് പകരം മറ്റ് വസ്തുക്കളോ പശ്ചാത്തലമോ ആണ് കാണുന്നത്.",
            "identifiedCondition": "ചർമ്മരോഗം കണ്ടെത്തിയില്ല (ചർമ്മത്തിന്റെ ഫോട്ടോ അല്ല)",
            "causes": "ബാധകമല്ല — ഫോട്ടോയിൽ മനുഷ്യ ചർമ്മം കാണുന്നില്ല.",
            "severity": "NONE",
            "helpfulCare": "നല്ല വെളിച്ചത്തിൽ ചർമ്മത്തിൽ നിന്ന് 10–15 സെ.മീ അകലെ വെച്ച് ഫോട്ടോ എടുക്കുക.",
            "dermatologyRecommendation": "ചർമ്മത്തിൽ എന്തെങ്കിലും ബുദ്ധിമുട്ടുണ്ടെങ്കിൽ അടുത്തുള്ള ചർമ്മരോഗ വിദഗ്ദ്ധനെ (Dermatologist) കാണുക.",
            "specialistType": "ചർമ്മരോഗ വിദഗ്ദ്ധൻ (MD Skin / DVL)",
            "consultTimeline": "ലക്ഷണങ്ങൾ ഉണ്ടെങ്കിൽ മാത്രം"
        }
    },
    "high": {
        "en": {
            "whatWasInPhoto": "Skin surface with a distinct, high-contrast dark or irregular lesion cluster in the target area.",
            "identifiedCondition": "Atypical Pigmented / Ulcerated Lesion — Urgent Dermatology Referral",
            "causes": "Abnormal melanocyte pigment clustering, chronic UV sun damage, or deep localized skin inflammation.",
            "severity": "HIGH",
            "helpfulCare": "Avoid applying strong over-the-counter steroid or bleaching creams. Keep the area protected from direct sunlight.",
            "dermatologyRecommendation": "URGENT DERMATOLOGY RECOMMENDATION: Schedule an immediate in-person consultation with a Certified Dermatologist (MD Dermatology / DVL) for clinical Dermoscopy and biopsy evaluation.",
            "specialistType": "Senior Dermatologist & Dermoscopy Specialist (MD / DVL)",
            "consultTimeline": "Immediate — Within 24 to 48 Hours"
        },
        "kn": {
            "whatWasInPhoto": "ಚರ್ಮದ ಮೇಲೆ ಕಪ್ಪಾದ ಮತ್ತು ಅಸಮವಾದ ಅಂಚುಗಳಿರುವ ಗಂಭೀರ ಕಲೆ ಕಾಣಿಸುತ್ತಿದೆ.",
            "identifiedCondition": "ಅಸಾಮಾನ್ಯ ವರ್ಣದ್ರವ್ಯದ ಗಾಯ (Atypical Lesion) — ತುರ್ತು ವೈದ್ಯರ ಶಿಫಾರಸು",
            "causes": "ಅತಿಯಾದ ಬಿಸಿಲಿನ ಪರಿಣಾಮ (UV ಕಿರಣಗಳು) ಅಥವಾ ಮೆಲನೋಸೈಟ್ ಜೀವಕೋಶಗಳ ಅಸಾಮಾನ್ಯ ಬೆಳವಣಿಗೆ.",
            "severity": "HIGH",
            "helpfulCare": "ಸ್ವಯಂ ಕ್ರೀಮ್ ಅಥವಾ ಮುಲಾಮುಗಳನ್ನು ಹಚ್ಚಬೇಡಿ. ಬಿಸಿಲಿನಿಂದ ರಕ್ಷಿಸಿ.",
            "dermatologyRecommendation": "ತುರ್ತು ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು: ಡರ್ಮೋಸ್ಕೋಪಿ (Dermoscopy) ಮತ್ತು ಸಂಪೂರ್ಣ ತಪಾಸಣೆಗಾಗಿ ತಕ್ಷಣವೇ ತಜ್ಞ ಚರ್ಮರೋಗ ವೈದ್ಯರನ್ನು (MD Dermatology) ಭೇಟಿ ಮಾಡಿ.",
            "specialistType": "ಹಿರಿಯ ಚರ್ಮರೋಗ ತಜ್ಞರು (MD / DVL)",
            "consultTimeline": "ತಕ್ಷಣ — 24 ರಿಂದ 48 ಗಂಟೆಗಳ ಒಳಗೆ"
        },
        "hi": {
            "whatWasInPhoto": "त्वचा पर गहरे रंग का और अनियमित किनारों वाला गंभीर धब्बा या घाव दिख रहा है।",
            "identifiedCondition": "असामान्य रंजित घाव (Atypical Lesion) — तत्काल डॉक्टर रेफरल",
            "causes": "धूप (UV किरणों) का अधिक प्रभाव या मेलानोसाइट कोशिकाओं की असामान्य वृद्धि।",
            "severity": "HIGH",
            "helpfulCare": "बिना डॉक्टर की सलाह के कोई स्टेरॉयड या ब्लीचिंग क्रीम न लगाएं।",
            "dermatologyRecommendation": "तत्काल त्वचा विशेषज्ञ की सिफारिश: डर्मोस्कोपी (Dermoscopy) और विस्तृत जांच के लिए तुरंत नजदीकी त्वचा विशेषज्ञ (MD Dermatologist) से अपॉइंटमेंट लें।",
            "specialistType": "वरिष्ठ त्वचा विशेषज्ञ (MD / DVL)",
            "consultTimeline": "तुरंत — 24 से 48 घंटों के भीतर"
        },
        "ta": {
            "whatWasInPhoto": "தோலில் அடர்ந்த நிறமுடைய ஒழுங்கற்ற விளிம்புகளுடன் கூடிய புண் அல்லது மச்சம் தெரிகிறது.",
            "identifiedCondition": "அசாதாரண நிறமி புண் (Atypical Lesion) — உடனடி மருத்துவர் பரிந்துரை",
            "causes": "அதிக சூரிய ஒளி (UV) பாதிப்பு அல்லது மெலனோசைட் செல்களின் அசாதாரண வளர்ச்சி.",
            "severity": "HIGH",
            "helpfulCare": "சுயமாக ஸ்டீராய்டு க்ரீம்களைப் பயன்படுத்த வேண்டாம்.",
            "dermatologyRecommendation": "உடனடி தோல் மருத்துவர் பரிந்துரை: டெர்மோஸ்கோபி (Dermoscopy) பரிசோதனைக்காக உடனடியாக தோல் சிறப்பு மருத்துவரை (MD Dermatologist) நேரில் சந்திக்கவும்.",
            "specialistType": "முதன்மை தோல் மருத்துவர் (MD / DVL)",
            "consultTimeline": "உடனடியாக — 24 முதல் 48 மணி நேரத்திற்குள்"
        },
        "te": {
            "whatWasInPhoto": "చర్మంపై ముదురు రంగులో, అసమాన అంచులతో ఉన్న మచ్చ లేదా పుండు కనిపిస్తోంది.",
            "identifiedCondition": "అసాధారణ పిగ్మెంటెడ్ లెషన్ — తక్షణ డాక్టర్ రిఫరల్",
            "causes": "అధిక ఎండ (UV కిరణాలు) ప్రభావం లేదా మెలనోసైట్ కణాల అసాధారణ పెరుగుదల.",
            "severity": "HIGH",
            "helpfulCare": "సొంతంగా స్టెరాయిడ్ క్రీములు వాడకండి.",
            "dermatologyRecommendation": "తక్షణ డెర్మటాలజీ సిఫార్సు: డెర్మోస్కోపీ (Dermoscopy) పరీక్ష కోసం వెంటనే చర్మవ్యాధి నిపుణుడిని (MD Dermatologist) సంప్రదించండి.",
            "specialistType": "సీనియర్ చర్మవ్యాధి నిపుణులు (MD / DVL)",
            "consultTimeline": "వెంటనే — 24 నుండి 48 గంటల్లోపు"
        },
        "ml": {
            "whatWasInPhoto": "ചർമ്മത്തിൽ കടുത്ത നിറത്തിലുള്ളതും ക്രമരഹിതമായ അതിരുകളുള്ളതുമായ പാട് കാണപ്പെടുന്നു.",
            "identifiedCondition": "അസാധാരണമായ ചർമ്മ പാട് (Atypical Lesion) — അടിയന്തര ഡോക്ടർ റഫറൽ",
            "causes": "അമിതമായ സൂര്യപ്രകാശം (UV) അല്ലെങ്കിൽ മെലനോസൈറ്റ് കോശങ്ങളുടെ അസാധാരണ വളർച്ച.",
            "severity": "HIGH",
            "helpfulCare": "സ്വയം മരുന്നുകൾ പുരട്ടരുത്.",
            "dermatologyRecommendation": "അടിയന്തര ഡെർമറ്റോളജി ശുപാർശ: ഡെർമോസ്കോപ്പി (Dermoscopy) പരിശോധനയ്ക്കായി ഉടൻ തന്നെ ഒരു ചർമ്മരോഗ വിദഗ്ദ്ധനെ (MD Dermatologist) നേരിൽ കാണുക.",
            "specialistType": "സീനിയർ ഡെർമറ്റോളജിസ്റ്റ് (MD / DVL)",
            "consultTimeline": "ഉടൻ തന്നെ — 24-48 മണിക്കൂറിനുള്ളിൽ"
        }
    },
    "ringworm": {
        "en": {
            "whatWasInPhoto": "Skin patch showing localized reddish inflammation with scaly or circular border texture.",
            "identifiedCondition": "Tinea Corporis (Superficial Fungal Ringworm) — Mild/Moderate",
            "causes": "Caused by dermatophyte fungi thriving in sweat, humid weather, damp clothes, or shared towels.",
            "severity": "MILD",
            "helpfulCare": "Clotrimazole 1% Antifungal Cream (twice daily for 14 days), Terbinafine 1% Ointment, and keep skin dry.",
            "dermatologyRecommendation": "DERMATOLOGY RECOMMENDATION: Consult a Clinical Dermatologist if the ringworm patch spreads, shows pus, or does not clear after 10–14 days of topical antifungal care, so oral antifungals (like Itraconazole) can be prescribed.",
            "specialistType": "Clinical Dermatologist (MD Skin & VD / PHC Medical Officer)",
            "consultTimeline": "Within 7–10 Days (or sooner if itching/spreading increases)"
        },
        "kn": {
            "whatWasInPhoto": "ಚರ್ಮದ ಮೇಲೆ ವೃತ್ತಾಕಾರದ ಕೆಂಪು ಉರಿಯೂತ ಮತ್ತು ಹುರುಪೆಯಂತಹ ಅಂಚು ಕಾಣಿಸುತ್ತಿದೆ.",
            "identifiedCondition": "ಟಿನಿಯಾ ಕಾರ್ಪೊರಿಸ್ (ಶಿಲೀಂಧ್ರ ಹುಳುಕಡ್ಡಿ / Ringworm) — ಸಾಧಾರಣ ಮಟ್ಟ",
            "causes": "ಬೆವರು, ತೇವಾಂಶಯುಕ್ತ ಹವಾಮಾನ ಮತ್ತು ಒದ್ದೆಯಾದ ಬಟ್ಟೆಗಳಿಂದ ಬೆಳೆಯುವ ಶಿಲೀಂಧ್ರ (Fungi) ಸೋಂಕು.",
            "severity": "MILD",
            "helpfulCare": "ಕ್ಲೋಟ್ರಿಮಜೋಲ್ 1% ಕ್ರೀಮ್ (Clotrimazole 1% ದಿನಕ್ಕೆ 2 ಬಾರಿ) ಅಥವಾ ಟರ್ಬಿನಾಫೈನ್ 1% ಮುಲಾಮು ಹಚ್ಚಿ.",
            "dermatologyRecommendation": "ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು: 10–14 ದಿನಗಳಲ್ಲಿ ಹುಳುಕಡ್ಡಿ ಕಡಿಮೆಯಾಗದಿದ್ದರೆ ಅಥವಾ ಹರಡುತ್ತಿದ್ದರೆ, ಸೂಕ್ತ ಮಾತ್ರೆಗಳಿಗಾಗಿ ಚರ್ಮರೋಗ ತಜ್ಞರನ್ನು (Dermatologist) ಭೇಟಿ ಮಾಡಿ.",
            "specialistType": "ಚರ್ಮರೋಗ ತಜ್ಞರು (MD Skin & VD)",
            "consultTimeline": "7 ರಿಂದ 10 ದಿನಗಳಲ್ಲಿ (ಅಥವಾ ಸೋಂಕು ಹೆಚ್ಚಾದಲ್ಲಿ ತಕ್ಷಣ)"
        },
        "hi": {
            "whatWasInPhoto": "त्वचा पर गोल लाल घेरा और हल्की पपड़ीदार सूजन दिखाई दे रही है।",
            "identifiedCondition": "टिनिया कॉर्पोरिस (फंगल दाद / Ringworm) — सामान्य स्तर",
            "causes": "पसीना, नमी, गीले कपड़े या संक्रमित तौलिए के संपर्क से होने वाला फंगल संक्रमण।",
            "severity": "MILD",
            "helpfulCare": "क्लोट्रिमाज़ोल 1% क्रीम (Clotrimazole 1% दिन में दो बार) या टर्बिनाफाइन 1% क्रीम लगाएं और त्वचा को सूखा रखें।",
            "dermatologyRecommendation": "त्वचा विशेषज्ञ की सिफारिश: यदि 10–14 दिनों में दाद ठीक न हो या फैल रहा हो, तो एंटीफंगल गोलियों के लिए नजदीकी त्वचा विशेषज्ञ (Dermatologist) से परामर्श लें।",
            "specialistType": "क्लिनिकल डर्मेटोलॉजिस्ट (MD Skin & VD)",
            "consultTimeline": "7 से 10 दिनों के भीतर (फैलने पर तुरंत)"
        },
        "ta": {
            "whatWasInPhoto": "தோலில் வட்ட வடிவ சிவப்பு நிற தடிப்பு மற்றும் செதில் போன்ற விளிம்பு தெரிகிறது.",
            "identifiedCondition": "டினியா கார்ப்போரிஸ் (படர்தாமரை / Fungal Ringworm) — சாதாரண நிலை",
            "causes": "வியர்வை, ஈரப்பதம் மற்றும் ஈரமான ஆடைகளால் ஏற்படும் பூஞ்சை (Fungal) தொற்று.",
            "severity": "MILD",
            "helpfulCare": "குளோட்ரிமசோல் 1% க்ரீம் (Clotrimazole 1% தினமும் 2 முறை) அல்லது டெர்பினாஃபைன் 1% க்ரீம் தடவவும்.",
            "dermatologyRecommendation": "தோல் மருத்துவர் பரிந்துரை: 10–14 நாட்களில் குணமாகவில்லை என்றால் அல்லது பரவினால் தோல் மருத்துவரை (Dermatologist) அணுகி ஆலோசனை பெறவும்.",
            "specialistType": "தோல் மருத்துவர் (MD Skin & VD)",
            "consultTimeline": "7–10 நாட்களுக்குள்"
        },
        "te": {
            "whatWasInPhoto": "చర్మంపై గుండ్రని ఎర్రటి వలయం మరియు పొలుసుల వంటి అంచు కనిపిస్తోంది.",
            "identifiedCondition": "టినియా కార్పోరిస్ (ఫంగల్ తామర / Ringworm) — సాధారణ స్థాయి",
            "causes": "చెమట, తేమ వాతావరణం మరియు తడి దుస్తుల వల్ల కలిగే ఫంగల్ ఇన్ఫెక్షన్.",
            "severity": "MILD",
            "helpfulCare": "క్లోట్రిమజోల్ 1% క్రీమ్ (Clotrimazole 1% రోజుకు రెండుసార్లు) లేదా టెర్బినాఫైన్ 1% ఆయింట్‌మెంట్ రాయండి.",
            "dermatologyRecommendation": "డెర్మటాలజీ సిఫార్సు: 10–14 రోజుల్లో తామర తగ్గకపోయినా లేదా వ్యాపిస్తున్నా చర్మవ్యాధి నిపుణుడిని (Dermatologist) సంప్రదించండి.",
            "specialistType": "క్లినికల్ డెర్మటాలజిస్ట్ (MD Skin & VD)",
            "consultTimeline": "7–10 రోజుల్లోపు"
        },
        "ml": {
            "whatWasInPhoto": "ചർമ്മത്തിൽ വൃത്താകൃതിയിലുള്ള ചുവന്ന തടിപ്പും ശൽക്കങ്ങളുള്ള വക്കുകളും കാണപ്പെടുന്നു.",
            "identifiedCondition": "ടിനിയ കോർപ്പോറിസ് (വട്ടച്ചൊറി / Fungal Ringworm) — സാധാരണ നില",
            "causes": "വിയർപ്പ്, ഈർപ്പം, നനഞ്ഞ വസ്ത്രങ്ങൾ എന്നിവയിലൂടെ പടരുന്ന ഫംഗസ് അണുബാധ.",
            "severity": "MILD",
            "helpfulCare": "ക്ലോട്രിമസോൾ 1% ക്രീം (Clotrimazole 1% ദിവസവും 2 തവണ) അല്ലെങ്കിൽ ടെർബിനാഫൈൻ 1% ഓയിന്റ്മെന്റ് പുരട്ടുക.",
            "dermatologyRecommendation": "ഡെർമറ്റോളജി ശുപാർശ: 10–14 ദിവസത്തിനുള്ളിൽ ഭേദമായില്ലെങ്കിൽ ഒരു ചർമ്മരോഗ വിദഗ്ദ്ധനെ (Dermatologist) സമീപിക്കുക.",
            "specialistType": "ക്ലിനിക്കൽ ഡെർമറ്റോളജിസ്റ്റ് (MD Skin & VD)",
            "consultTimeline": "7–10 ദിവസത്തിനുള്ളിൽ"
        }
    },
    "eczema": {
        "en": {
            "whatWasInPhoto": "Skin surface showing localized redness, rash spots, or mild surface irritation.",
            "identifiedCondition": "Allergic Contact Dermatitis / Mild Eczema Rash",
            "causes": "Triggered by skin sensitivity to harsh soaps, sweat retention, dust, insect bite, or dry skin barrier.",
            "severity": "MILD",
            "helpfulCare": "Calamine Soothing Lotion (2–3 times daily), Hydrocortisone 1% Mild Cream (for 3–5 days), and Cetirizine 10 mg tablet at night for itching.",
            "dermatologyRecommendation": "DERMATOLOGY RECOMMENDATION: Visit a Dermatologist for patch testing and barrier-repair therapy if redness, oozing, or itching continues beyond 5–7 days.",
            "specialistType": "Allergy & Clinical Dermatologist (MD Skin / DVL)",
            "consultTimeline": "Within 5–7 Days if rash persists"
        },
        "kn": {
            "whatWasInPhoto": "ಚರ್ಮದ ಮೇಲೆ ಸ್ಥಳೀಯ ಕೆಂಪು ಕಲೆಗಳು, ಸಣ್ಣ ದದ್ದು ಅಥವಾ ತುರಿಕೆಯ ಕಿರಿಕಿರಿ ಕಾಣಿಸುತ್ತಿದೆ.",
            "identifiedCondition": "ಅಲರ್ಜಿಕ್ ಕಾಂಟ್ಯಾಕ್ಟ್ ಡರ್ಮಟೈಟಿಸ್ / ಸೌಮ್ಯ ಎಕ್ಸಿಮಾ ದದ್ದು (Mild Eczema)",
            "causes": "ಗಡಸು ಸಾಬೂನು, ಬೆವರು, ಧೂಳು, ಕೀಟ ಕಡಿತ ಅಥವಾ ಒಣ ಚರ್ಮದ ಅಲರ್ಜಿಯಿಂದ ಉಂಟಾಗುತ್ತದೆ.",
            "severity": "MILD",
            "helpfulCare": "ಕ್ಯಾಲಮೈನ್ ಲೋಷನ್ (Calamine Lotion ದಿನಕ್ಕೆ 2–3 ಬಾರಿ), ಹೈಡ್ರೋಕಾರ್ಟಿಸೋನ್ 1% ಕ್ರೀಮ್ ಮತ್ತು ತುರಿಕೆಗೆ ರಾತ್ರಿ ಸಿಟ್ರಿಜಿನ್ 10 mg ಮಾತ್ರೆ.",
            "dermatologyRecommendation": "ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು: ತುರಿಕೆ ಅಥವಾ ಕೆಂಪು ದದ್ದು 5–7 ದಿನಗಳ ನಂತರವೂ ಮುಂದುವರಿದರೆ ಅಲರ್ಜಿ ಪರೀಕ್ಷೆಗಾಗಿ ಚರ್ಮರೋಗ ತಜ್ಞರನ್ನು (Dermatologist) ಭೇಟಿ ಮಾಡಿ.",
            "specialistType": "ಅಲರ್ಜಿ ಮತ್ತು ಚರ್ಮರೋಗ ತಜ್ಞರು (MD Skin / DVL)",
            "consultTimeline": "5 ರಿಂದ 7 ದಿನಗಳಲ್ಲಿ (ದದ್ದು ಕಡಿಮೆಯಾಗದಿದ್ದರೆ)"
        },
        "hi": {
            "whatWasInPhoto": "त्वचा पर हल्की लालिमा, छोटे दाने या सतही जलन दिखाई दे रही है।",
            "identifiedCondition": "एलर्जिक कॉन्टैक्ट डर्मेटाइटिस / हल्का एक्जिमा रैश (Mild Eczema)",
            "causes": "तेज साबुन, पसीना, धूल, कीड़े के काटने या रूखी त्वचा की एलर्जी के कारण होता है।",
            "severity": "MILD",
            "helpfulCare": "कैलामाइन लोशन (Calamine दिन में 2–3 बार), हाइड्रोकोर्टिसोन 1% क्रीम और खुजली के लिए रात में सिट्रिज़िन 10 mg टैबलेट।",
            "dermatologyRecommendation": "त्वचा विशेषज्ञ की सिफारिश: यदि खुजली या लाल चकत्ते 5–7 दिनों में कम न हों, तो एलर्जी जांच के लिए त्वचा विशेषज्ञ (Dermatologist) को दिखाएं।",
            "specialistType": "एलर्जी एवं त्वचा विशेषज्ञ (MD Skin / DVL)",
            "consultTimeline": "5 से 7 दिनों के भीतर"
        },
        "ta": {
            "whatWasInPhoto": "தோலில் லேசான சிவப்பு நிற தடிப்பு, அரிப்பு அல்லது எரிச்சல் தெரிகிறது.",
            "identifiedCondition": "ஒவ்வாமை தோல் அழற்சி / லேசான எக்ஸிமா (Mild Eczema)",
            "causes": "சோப்பு, வியர்வை, தூசி, பூச்சி கடி அல்லது வறண்ட தோல் ஒவ்வாமையால் ஏற்படுகிறது.",
            "severity": "MILD",
            "helpfulCare": "காலமைன் லோஷன் (Calamine தினமும் 2–3 முறை), ஹைட்ரோகார்டிசோன் 1% க்ரீம் மற்றும் அரிப்புக்கு சிட்ரிசின் 10 mg மாத்திரை.",
            "dermatologyRecommendation": "தோல் மருத்துவர் பரிந்துரை: 5–7 நாட்களுக்குப் பிறகும் அரிப்பு அல்லது தடிப்பு தொடர்ந்தால் தோல் மருத்துவரை (Dermatologist) அணுகவும்.",
            "specialistType": "ஒவ்வாமை & தோல் மருத்துவர் (MD Skin / DVL)",
            "consultTimeline": "5–7 நாட்களுக்குள்"
        },
        "te": {
            "whatWasInPhoto": "చర్మంపై స్వల్ప ఎరుపు, చిన్న దద్దుర్లు లేదా దురద లక్షణాలు కనిపిస్తున్నాయి.",
            "identifiedCondition": "అలెర్జిక్ కాంటాక్ట్ డెర్మటైటిస్ / స్వల్ప ఎగ్జిమా దద్దుర్లు (Mild Eczema)",
            "causes": "ఘాటైన సబ్బులు, చెమట, దుమ్ము, పురుగుల కాటు లేదా పొడి చర్మం అలెర్జీ వల్ల కలుగుతుంది.",
            "severity": "MILD",
            "helpfulCare": "కాలమైన్ లోషన్ (Calamine రోజుకు 2–3 సార్లు), హైడ్రోకార్టిసోన్ 1% క్రీమ్ మరియు దురద తగ్గడానికి రాత్రి సిట్రిజిన్ 10 mg మాత్ర.",
            "dermatologyRecommendation": "డెర్మటాలజీ సిఫార్సు: 5–7 రోజుల్లో దురద లేదా ఎరుపు తగ్గకపోతే అలెర్జీ పరీక్ష కోసం చర్మవ్యాధి నిపుణుడిని (Dermatologist) సంప్రదించండి.",
            "specialistType": "అలెర్జీ & చర్మవ్యాధి నిపుణులు (MD Skin / DVL)",
            "consultTimeline": "5–7 రోజుల్లోపు"
        },
        "ml": {
            "whatWasInPhoto": "ചർമ്മത്തിൽ നേരിയ ചുവപ്പ്, തടിപ്പ് അല്ലെങ്കിൽ ചൊറിച്ചിൽ കാണപ്പെടുന്നു.",
            "identifiedCondition": "അലർജിക് കോൺടാക്റ്റ് ഡെർമറ്റൈറ്റിസ് / നേരിയ എക്സിമ (Mild Eczema)",
            "causes": "സോപ്പ്, വിയർപ്പ്, പൊടി, പ്രാണികളുടെ കടി അല്ലെങ്കിൽ വരണ്ട ചർമ്മത്തിലെ അലർജി കാരണം ഉണ്ടാകുന്നു.",
            "severity": "MILD",
            "helpfulCare": "കലാമൈൻ ലോഷൻ (Calamine ദിവസവും 2–3 തവണ), ഹൈഡ്രോകോർട്ടിസോൺ 1% ക്രീം, ചൊറിച്ചിലിന് രാത്രി സിട്രിസിൻ 10 mg ഗുളിക.",
            "dermatologyRecommendation": "ഡെർമറ്റോളജി ശുപാർശ: 5–7 ദിവസത്തിനുള്ളിൽ ചൊറിച്ചിലോ തടിപ്പോ മാറിയില്ലെങ്കിൽ ചർമ്മരോഗ വിദഗ്ദ്ധനെ (Dermatologist) കാണുക.",
            "specialistType": "അലർജി & ചർമ്മരോഗ വിദഗ്ദ്ധൻ (MD Skin / DVL)",
            "consultTimeline": "5–7 ദിവസത്തിനുള്ളിൽ"
        }
    },
    "healthy": {
        "en": {
            "whatWasInPhoto": "Clear, even-toned human skin with normal healthy texture and no focal rash, ring, or lesion.",
            "identifiedCondition": "Normal / Healthy Skin — No Urgent Referral Needed",
            "causes": "Healthy, intact skin barrier with no signs of fungal infection, rash, or abnormal lesion.",
            "severity": "HEALTHY",
            "helpfulCare": "No medication needed. Maintain daily hygiene, use a gentle ceramide moisturizer, and apply SPF 30+ sunscreen outdoors.",
            "dermatologyRecommendation": "DERMATOLOGY RECOMMENDATION: No urgent medical visit is required. For preventive skin wellness or personalized skincare, you may schedule a routine checkup with a nearby Dermatologist.",
            "specialistType": "Preventive & Cosmetic Dermatologist (Optional)",
            "consultTimeline": "Routine / Annual Preventive Checkup"
        },
        "kn": {
            "whatWasInPhoto": "ಯಾವುದೇ ದದ್ದು, ಕಲೆ ಅಥವಾ ಸೋಂಕಿಲ್ಲದ ಸ್ಪಷ್ಟ ಮತ್ತು ಆರೋಗ್ಯಕರ ಚರ್ಮ ಕಾಣಿಸುತ್ತಿದೆ.",
            "identifiedCondition": "ಸಾಮಾನ್ಯ / ಆರೋಗ್ಯಕರ ಚರ್ಮ — ತುರ್ತು ಶಿಫಾರಸು ಅಗತ್ಯವಿಲ್ಲ",
            "causes": "ನಿಮ್ಮ ಚರ್ಮವು ಆರೋಗ್ಯಕರವಾಗಿದ್ದು ಯಾವುದೇ ಶಿಲೀಂಧ್ರ ಅಥವಾ ಅಲರ್ಜಿ ಲಕ್ಷಣಗಳಿಲ್ಲ.",
            "severity": "HEALTHY",
            "helpfulCare": "ಯಾವುದೇ ಔಷಧಿ ಅಗತ್ಯವಿಲ್ಲ. ಪ್ರತಿದಿನ ಸೌಮ್ಯವಾದ ಮಾಯಿಶ್ಚರೈಸರ್ ಮತ್ತು ಸನ್‌ಸ್ಕ್ರೀನ್ ಬಳಸಿ.",
            "dermatologyRecommendation": "ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು: ತುರ್ತು ವೈದ್ಯರ ಭೇಟಿ ಅಗತ್ಯವಿಲ್ಲ. ಸಾಮಾನ್ಯ ಚರ್ಮದ ಆರೈಕೆ ಅಥವಾ ಸಲಹೆಗಾಗಿ ನೀವು ಚರ್ಮರೋಗ ತಜ್ಞರನ್ನು ಸಂಪರ್ಕಿಸಬಹುದು.",
            "specialistType": "ಚರ್ಮರೋಗ ತಜ್ಞರು (ಐಚ್ಛಿಕ / ಸಾಮಾನ್ಯ ತಪಾಸಣೆ)",
            "consultTimeline": "ಸಾಮಾನ್ಯ ತಪಾಸಣೆ (ಅಗತ್ಯವಿದ್ದಲ್ಲಿ)"
        },
        "hi": {
            "whatWasInPhoto": "बिना किसी दाने, दाद या धब्बे के साफ और स्वस्थ मानव त्वचा दिखाई दे रही है।",
            "identifiedCondition": "सामान्य / स्वस्थ त्वचा — किसी तत्काल रेफरल की आवश्यकता नहीं",
            "causes": "आपकी त्वचा पूरी तरह स्वस्थ है और किसी संक्रमण या एलर्जी का कोई संकेत नहीं है।",
            "severity": "HEALTHY",
            "helpfulCare": "किसी दवा की आवश्यकता नहीं है। रोजाना हल्का मॉइस्चराइज़र और धूप में सनस्क्रीन लगाएं।",
            "dermatologyRecommendation": "त्वचा विशेषज्ञ की सिफारिश: किसी तत्काल जांच की आवश्यकता नहीं है। सामान्य त्वचा देखभाल के लिए आप नजदीकी त्वचा विशेषज्ञ से परामर्श ले सकते हैं।",
            "specialistType": "त्वचा विशेषज्ञ (वैकल्पिक / सामान्य जांच)",
            "consultTimeline": "सामान्य निवारक जांच"
        },
        "ta": {
            "whatWasInPhoto": "எந்தவொரு தடிப்பு அல்லது புண்ணும் இல்லாத தெளிவான மற்றும் ஆரோக்கியமான தோல் தெரிகிறது.",
            "identifiedCondition": "சாதாரண / ஆரோக்கியமான தோல் — உடனடி பரிந்துரை தேவையில்லை",
            "causes": "உங்கள் தோல் ஆரோக்கியமாக உள்ளது; தொற்று அல்லது ஒவ்வாமை அறிகுறிகள் எதுவும் இல்லை.",
            "severity": "HEALTHY",
            "helpfulCare": "மருந்து தேவையில்லை. தினமும் மாய்ஸ்சரைசர் மற்றும் சன்ஸ்கிரீன் பயன்படுத்தவும்.",
            "dermatologyRecommendation": "தோல் மருத்துவர் பரிந்துரை: உடனடி மருத்துவ ஆலோசனை தேவையில்லை. வழக்கமான தோல் பராமரிப்புக்கு தோல் மருத்துவரை அணுகலாம்.",
            "specialistType": "தோல் மருத்துவர் (வழக்கமான பரிசோதனை)",
            "consultTimeline": "வழக்கமான பரிசோதனை"
        },
        "te": {
            "whatWasInPhoto": "ఎటువంటి దద్దుర్లు లేదా మచ్చలు లేని స్పష్టమైన మరియు ఆరోగ్యకరమైన చర్మం కనిపిస్తోంది.",
            "identifiedCondition": "సాధారణ / ఆరోగ్యకరమైన చర్మం — తక్షణ రిఫరల్ అవసరం లేదు",
            "causes": "మీ చర్మం ఆరోగ్యంగా ఉంది, ఎటువంటి ఫంగల్ ఇన్ఫెక్షన్ లేదా అలెర్జీ లక్షణాలు లేవు.",
            "severity": "HEALTHY",
            "helpfulCare": "ఎటువంటి మందులు అవసరం లేదు. రోజూ మాయిశ్చరైజర్ మరియు సన్‌స్క్రీన్ వాడండి.",
            "dermatologyRecommendation": "డెర్మటాలజీ సిఫార్సు: అత్యవసర డాక్టర్ సంప్రదింపు అవసరం లేదు. సాధారణ చర్మ సంరక్షణ కోసం డెర్మటాలజిస్ట్‌ను సంప్రదించవచ్చు.",
            "specialistType": "చర్మవ్యాధి నిపుణులు (సాధారణ పరీక్ష)",
            "consultTimeline": "సాధారణ పరీక్ష"
        },
        "ml": {
            "whatWasInPhoto": "പാടുകളോ തടിപ്പുകളോ ഇല്ലാത്ത വ്യക്തവും ആരോഗ്യകരവുമായ ചർമ്മം കാണപ്പെടുന്നു.",
            "identifiedCondition": "സാധാരണ / ആരോഗ്യമുള്ള ചർമ്മം — അടിയന്തര റഫറൽ ആവശ്യമില്ല",
            "causes": "നിങ്ങളുടെ ചർമ്മം പൂർണ്ണ ആരോഗ്യമുള്ളതാണ്; അണുബാധയുടെ ലക്ഷണങ്ങളൊന്നുമില്ല.",
            "severity": "HEALTHY",
            "helpfulCare": "മരുന്നുകൾ ആവശ്യമില്ല. ദിവസവും മോയ്സ്ചറൈസറും സൺസ്ക്രീനും ഉപയോഗിക്കുക.",
            "dermatologyRecommendation": "ഡെർമറ്റോളജി ശുപാർശ: അടിയന്തരമായി ഡോക്ടറെ കാണേണ്ടതില്ല. സാധാരണ ചർമ്മ സംരക്ഷണത്തിനായി ഡെർമറ്റോളജിസ്റ്റിനെ സമീപിക്കാവുന്നതാണ്.",
            "specialistType": "ഡെർമറ്റോളജിസ്റ്റ് (സാധാരണ പരിശോധന)",
            "consultTimeline": "സാധാരണ പരിശോധന"
        }
    }
}

def analyze_skin_metrics(metrics: dict, lang: str = "en") -> dict:
    lang_code = lang if lang in ("en", "kn", "hi", "ta", "te", "ml") else "en"
    skin_ratio = float(metrics.get("skinRatio", 0.0))
    artificial_ratio = float(metrics.get("artificialRatio", 0.0))
    lesion_spot_ratio = float(metrics.get("lesionSpotRatio", 0.0))
    red_inflammation = float(metrics.get("redInflammation", 0.0))
    dark_lesion_contrast = float(metrics.get("darkLesionContrast", 0.0))
    scaly_edge_score = float(metrics.get("scalyEdgeScore", 0.0))
    color_asymmetry = float(metrics.get("colorAsymmetry", 0.0))

    if skin_ratio < 0.22 or artificial_ratio > 0.45:
        res = dict(REPORT_TRANSLATIONS["non_skin"][lang_code])
        res["confidence"] = 96
        return res

    if (dark_lesion_contrast >= 26.0 and lesion_spot_ratio >= 0.035 and color_asymmetry >= 14.0) or (
        red_inflammation >= 24.0 and dark_lesion_contrast >= 20.0 and scaly_edge_score >= 18.0
    ):
        res = dict(REPORT_TRANSLATIONS["high"][lang_code])
        res["confidence"] = 93
        return res

    if (red_inflammation >= 10.5 and scaly_edge_score >= 11.5) or (
        lesion_spot_ratio >= 0.06 and scaly_edge_score >= 14.0
    ):
        res = dict(REPORT_TRANSLATIONS["ringworm"][lang_code])
        res["confidence"] = 92
        return res

    if red_inflammation >= 8.0 or lesion_spot_ratio >= 0.045 or dark_lesion_contrast >= 15.0:
        res = dict(REPORT_TRANSLATIONS["eczema"][lang_code])
        res["confidence"] = 91
        return res

    res = dict(REPORT_TRANSLATIONS["healthy"][lang_code])
    res["confidence"] = 95
    return res
'''

MAIN_PY = r'''import json
import re
import random
import sqlite3
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from database import get_connection, init_db
from ml_engine import analyze_skin_metrics

init_db()
TTS_MEMORY_CACHE = {}

def split_tts_chunks(text: str, max_len: int = 175):
    sentences = re.split(r"(?<=[.!?।|,:;])\s+", text.strip())
    chunks = []
    current = ""
    for s in sentences:
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_len:
            current = f"{current} {s}".strip()
        else:
            if current:
                chunks.append(current)
            if len(s) <= max_len:
                current = s
            else:
                for i in range(0, len(s), max_len):
                    chunks.append(s[i : i + max_len])
                current = ""
    if current:
        chunks.append(current)
    return chunks or [text[:max_len]]

def fetch_neural_tts_mp3(text: str, lang: str) -> bytes:
    tl_map = {"en": "en-IN", "kn": "kn", "hi": "hi", "ta": "ta", "te": "te", "ml": "ml"}
    tl = tl_map.get(lang, "en-IN")
    cache_key = f"{tl}:{text}"
    if cache_key in TTS_MEMORY_CACHE:
        return TTS_MEMORY_CACHE[cache_key]

    chunks = split_tts_chunks(text)
    audio_bytes = bytearray()
    for chunk in chunks:
        q = urllib.parse.quote(chunk)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={tl}&q={q}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://translate.google.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            audio_bytes.extend(resp.read())

    final_mp3 = bytes(audio_bytes)
    if len(TTS_MEMORY_CACHE) < 200:
        TTS_MEMORY_CACHE[cache_key] = final_mp3
    return final_mp3

class ArogyaAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

    def do_OPTIONS(self):
        self._send({"ok": True}, 200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/v1/health":
            return self._send({"status": "Connected", "db": "SQLite WAL"})

        if path == "/api/v1/tts":
            qs = parse_qs(parsed.query)
            text = (qs.get("text", [""])[0] or "").strip()
            lang = (qs.get("lang", ["en"])[0] or "en").strip()
            if not text:
                return self._send({"error": "Empty text"}, 400)
            try:
                mp3_data = fetch_neural_tts_mp3(text, lang)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(mp3_data)))
                self.end_headers()
                self.wfile.write(mp3_data)
                return
            except Exception as e:
                return self._send({"error": str(e)}, 502)

        if path == "/api/v1/state":
            conn = get_connection()
            users = [dict(r) for r in conn.execute("SELECT id, username, full_name as fullName, role, phone, locality, lang FROM users ORDER BY id ASC;").fetchall()]
            scans = [{
                "id": r["id"], "ownerUsername": r["owner_username"], "person": r["person"],
                "bodyPart": r["body_part"], "timestamp": r["timestamp"],
                "whatWasInPhoto": r["what_was_in_photo"], "identifiedCondition": r["identified_condition"],
                "causes": r["causes"], "severity": r["severity"], "confidence": r["confidence"],
                "helpfulCare": r["helpful_care"]
            } for r in conn.execute("SELECT * FROM scans ORDER BY rowid DESC;").fetchall()]
            appointments = [{
                "id": r["id"], "patientUsername": r["patient_username"], "patientName": r["patient_name"],
                "clinicName": r["clinic_name"], "specialty": r["specialty"], "date": r["date"],
                "time": r["time"], "notes": r["notes"], "status": r["status"]
            } for r in conn.execute("SELECT * FROM appointments ORDER BY rowid DESC;").fetchall()]
            referrals = [{
                "id": r["id"], "patientName": r["patient_name"], "condition": r["condition"],
                "urgency": r["urgency"], "hospital": r["hospital"], "referredBy": r["referred_by"],
                "status": r["status"]
            } for r in conn.execute("SELECT * FROM referrals ORDER BY rowid DESC;").fetchall()]
            conn.close()
            return self._send({"users": users, "scans": scans, "appointments": appointments, "referrals": referrals})

        return self._send({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        b = self._body()
        conn = get_connection()
        cur = conn.cursor()

        if path == "/api/v1/auth/login":
            row = cur.execute(
                "SELECT id, username, full_name as fullName, role, phone, locality, lang FROM users WHERE LOWER(username)=? AND password=?;",
                (b.get("username", "").strip().lower(), b.get("password", ""))
            ).fetchone()
            conn.close()
            return self._send({"user": dict(row)}, 200) if row else self._send({"error": "Invalid username or password."}, 401)

        if path == "/api/v1/auth/register":
            code = b.get("regCode", "").strip().upper()
            role = "worker" if code == "PHC2026" else ("admin" if code == "ADMIN2026" else "user")
            try:
                cur.execute(
                    "INSERT INTO users (username, password, full_name, role, phone, locality, lang) VALUES (?, ?, ?, ?, ?, ?, ?);",
                    (b.get("username", "").strip(), b.get("password", "").strip(), b.get("fullName", "").strip(), role, b.get("phone", "+91 9876543210"), b.get("locality", "Your Current Area"), b.get("lang", "en"))
                )
                conn.commit()
                uid = cur.lastrowid
                row = cur.execute("SELECT id, username, full_name as fullName, role, phone, locality, lang FROM users WHERE id=?;", (uid,)).fetchone()
                conn.close()
                return self._send({"user": dict(row)}, 200)
            except sqlite3.IntegrityError:
                conn.close()
                return self._send({"error": "Username already exists."}, 400)

        if path == "/api/v1/scans/analyze":
            lang = b.get("lang", "en")
            report = analyze_skin_metrics(b.get("metrics", {}), lang=lang)
            sid = f"SCN-{random.randint(1000, 9999)}"
            combined_care = f"{report['helpfulCare']} | {report.get('dermatologyRecommendation', '')}"
            cur.execute(
                "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (sid, b.get("ownerUsername", "guest"), b.get("person", "Self / Family Member"), b.get("bodyPart", "Arm / Forearm"), b.get("timestamp", "Just now"), report["whatWasInPhoto"], report["identifiedCondition"], report["causes"], report["severity"], int(report["confidence"]), combined_care)
            )
            conn.commit()
            conn.close()
            return self._send({"id": sid, "report": report})

        if path == "/api/v1/appointments":
            aid = f"APT-{random.randint(1000, 9999)}"
            cur.execute(
                "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (aid, b.get("patientUsername", "guest"), b.get("patientName", "Guest Patient"), b.get("clinicName", "Nearby Dermatology & Skin Care Clinic"), b.get("specialty", "Dermatology (Skin Specialist)"), b.get("date", "2026-10-22"), b.get("time", "10:30 AM"), b.get("notes", "Requesting skin checkup after Smart Skin Lens scan."), "Confirmed")
            )
            conn.commit()
            conn.close()
            return self._send({"id": aid, "ok": True})

        if path == "/api/v1/referrals":
            rid = f"REF-{random.randint(100, 999)}"
            cur.execute(
                "INSERT INTO referrals VALUES (?, ?, ?, ?, ?, ?, ?);",
                (rid, b.get("patientName", ""), b.get("condition", ""), b.get("urgency", "HIGH — Specialist Consult"), b.get("hospital", ""), b.get("referredBy", "Healthcare Worker"), "Active")
            )
            conn.commit()
            conn.close()
            return self._send({"id": rid, "ok": True})

        conn.close()
        return self._send({"error": "Route not found"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        b = self._body()
        conn = get_connection()
        cur = conn.cursor()

        if path.startswith("/api/v1/users/"):
            uid = int(path.split("/")[-1])
            if "role" in b and len(b) == 1:
                cur.execute("UPDATE users SET role=? WHERE id=?;", (b["role"], uid))
            else:
                cur.execute("UPDATE users SET full_name=?, phone=?, locality=?, lang=? WHERE id=?;", (b.get("fullName"), b.get("phone"), b.get("locality"), b.get("lang", "en"), uid))
                if b.get("password"):
                    cur.execute("UPDATE users SET password=? WHERE id=?;", (b["password"], uid))
            conn.commit()
            row = cur.execute("SELECT id, username, full_name as fullName, role, phone, locality, lang FROM users WHERE id=?;", (uid,)).fetchone()
            conn.close()
            return self._send({"user": dict(row)})

        if path.startswith("/api/v1/appointments/"):
            aid = path.split("/")[-1]
            cur.execute("UPDATE appointments SET date=?, time=?, notes=?, status=? WHERE id=?;", (b.get("date"), b.get("time"), b.get("notes"), b.get("status"), aid))
            conn.commit()
            conn.close()
            return self._send({"ok": True})

        conn.close()
        return self._send({"error": "Not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        conn = get_connection()
        cur = conn.cursor()
        if path.startswith("/api/v1/users/"):
            cur.execute("DELETE FROM users WHERE id=?;", (int(path.split("/")[-1]),))
            conn.commit()
            conn.close()
            return self._send({"ok": True})
        if path.startswith("/api/v1/referrals/"):
            cur.execute("DELETE FROM referrals WHERE id=?;", (path.split("/")[-1],))
            conn.commit()
            conn.close()
            return self._send({"ok": True})
        conn.close()
        return self._send({"error": "Not found"}, 404)
'''

# ==============================================================================
# 2. SEPARATED FRONTEND FILES (Written to frontend/ and frontend/src/)
# ==============================================================================
INDEX_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Arogya Setu — Your Friendly Everyday Skin & Wellness Companion</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body class="bg-[#FFFBF2]">
  <div id="root"></div>
  <script src="/src/api.js"></script>
  <script src="/src/voiceEngine.js"></script>
  <script type="text/babel" src="/src/app_bundle.jsx"></script>
</body>
</html>
'''

API_JS = r'''window.API_BASE = "http://127.0.0.1:8000/api/v1";

window.ArogyaAPI = {
  async getState() {
    const res = await fetch(`${window.API_BASE}/state`);
    if (!res.ok) throw new Error("Backend offline");
    return res.json();
  },
  async login(payload) {
    const res = await fetch(`${window.API_BASE}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return { ok: res.ok, data: await res.json() };
  },
  async register(payload) {
    const res = await fetch(`${window.API_BASE}/auth/register`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return { ok: res.ok, data: await res.json() };
  },
  async analyzeScan(payload) {
    const res = await fetch(`${window.API_BASE}/scans/analyze`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return res.json();
  },
  async createAppointment(payload) {
    return fetch(`${window.API_BASE}/appointments`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async updateAppointment(id, payload) {
    return fetch(`${window.API_BASE}/appointments/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async createReferral(payload) {
    return fetch(`${window.API_BASE}/referrals`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async deleteReferral(id) {
    return fetch(`${window.API_BASE}/referrals/${id}`, { method: "DELETE" });
  },
  async updateUser(id, payload) {
    const res = await fetch(`${window.API_BASE}/users/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return res.json();
  },
  async deleteUser(id) {
    return fetch(`${window.API_BASE}/users/${id}`, { method: "DELETE" });
  }
};
'''

VOICE_ENGINE_JS = r'''window.LANGUAGES = [
  { code: "en", display: "English (India)", locale: "en-IN" },
  { code: "kn", display: "ಕನ್ನಡ (Kannada)", locale: "kn-IN" },
  { code: "hi", display: "हिन्दी (Hindi)", locale: "hi-IN" },
  { code: "ta", display: "தமிழ் (Tamil)", locale: "ta-IN" },
  { code: "te", display: "తెలుగు (Telugu)", locale: "te-IN" },
  { code: "ml", display: "മലയാളം (Malayalam)", locale: "ml-IN" }
];

window.TRANSLATIONS = {
  en: {
    appName: "Arogya Setu",
    appTagline: "Your Friendly Everyday Skin & Wellness Companion",
    guestBadge: "Guest User (Not Signed In)",
    listenBtn: "Listen",
    pauseBtn: "Pause",
    resumeBtn: "Resume",
    voiceTourBtn: "Voice Tour",
    connectedBadge: "Connected",
    signInBtn: "Sign In",
    createAccountBtn: "Create Account",
    manageProfileBtn: "Manage Profile / Sign Out",
    tabLens: "Smart Skin Lens",
    tabJournal: "Home & Journal",
    tabAppointments: "Appointments",
    tabDoctors: "Nearby Doctors",
    tabPharmacies: "Nearby Pharmacies",
    tabReferrals: "Hospital Referrals",
    tabAdmin: "Admin Control",
    bannerText: "Namaste! Welcome to Arogya Setu. Smart Skin Lens tells you what is in your photo, identifies whether your skin is healthy or has a specific condition, explains what causes it, rates its severity, and provides a Dermatology Specialist Recommendation.",
    hearStepsVoice: "Step 1: Enter who this check is for and select the body area. Step 2: Click Open Live Camera and press Snap Photo Now, or click Upload from Device. Step 3: Tap Scan Photo with Smart Skin Lens to hear the condition, its causes, medicines, and Dermatology Recommendation.",
    voiceTourText: "Welcome to the Arogya Setu Voice Tour. Use Smart Skin Lens to scan any skin spot, Home and Journal to review saved scans and call 104 or 108, Appointments to book a dermatologist, and Nearby Doctors or Nearby Pharmacies to find care via live GPS.",
    companionBadge: "Instant Single-Voice Companion",
    snapOrUploadTitle: "Snap or Upload a Photo",
    hearStepsBtn: "Hear Steps",
    whoForLabel: "Who is this check for?",
    whoForDefault: "Self / Family Member",
    bodyAreaLabel: "Where on the body?",
    bodyAreas: ["Arm / Forearm", "Face / Neck", "Hand / Palm", "Leg / Foot", "Back / Torso"],
    consentText: "I agree to scan this photo with Smart Skin Lens to identify what is in the photo, check for any skin condition, its causes, severity, and receive a Dermatology Recommendation.",
    reticleInstruction: "Use your live camera to snap a photo or upload an image from your phone or computer.",
    reticleTitle: "Live Camera or Upload Photo",
    openCameraBtn: "Open Live Camera",
    snapNowBtn: "Snap Photo Now",
    closeBtn: "Close",
    uploadDeviceBtn: "Upload from Device",
    scanBtn: "Scan Photo with Smart Skin Lens",
    scanningBtn: "Analyzing Photo...",
    reportTitle: "Smart Skin Lens Report",
    readyBadge: "Ready to Scan Your Photo",
    readyDesc: "Open your live camera and click 'Snap Photo Now', or upload any image from your device, then tap 'Scan Photo with Smart Skin Lens'.",
    identifiedLabel: "Identified Condition",
    whatInPhotoLabel: "What Was in Photo",
    causesLabel: "What Causes This Condition",
    highAlertLabel: "Urgent Dermatology Specialist Recommendation",
    dermRecLabel: "Dermatology Specialist Recommendation",
    specialistBadgeLabel: "Recommended Specialist",
    helpfulCareLabel: "Helpful Care / Common Medicine",
    greetingPrefix: "Namaste",
    guestFriend: "Guest Friend",
    heroDesc: "View your saved Smart Skin Lens scans, manage doctor appointments, or call 104 / 108 health helplines.",
    kpiSavedScans: "Saved Skin Scans",
    kpiStoredJournal: "Stored in Journal",
    kpiHighAlerts: "High-Severity Alerts",
    kpiDoctorAdvised: "Doctor Visit Advised",
    kpiHelpline: "Health Helpline",
    kpiDial104: "Dial 104",
    kpiFreeAdvice: "Free Medical Advice",
    kpiEmergency: "Emergency Care",
    kpiDial108: "Dial 108",
    kpiAmbulance: "24/7 Ambulance",
    savedScansTitle: "Saved Smart Skin Lens Scans",
    colScanId: "Scan ID",
    colPerson: "Person",
    colWhatInPhoto: "What Was in Photo",
    colCondition: "Identified Condition",
    colCauses: "Causes",
    colSeverity: "Severity",
    colCare: "Helpful Care & Dermatology Advice",
    bookAptTitle: "Book Dermatologist Appointment",
    patientNameLabel: "Patient Name",
    clinicNameLabel: "Clinic / Hospital Name",
    specialtyLabel: "Specialty",
    specialties: ["Dermatology (Skin Specialist)", "General Medicine (OPD)", "Allergy & Immunology", "Pediatrics"],
    prefDateLabel: "Preferred Date",
    prefTimeLabel: "Preferred Time",
    notesLabel: "Notes for Doctor",
    requestAptBtn: "Request Appointment",
    rescheduleBtn: "Reschedule / Edit Notes",
    confirmBtn: "Confirm",
    cancelAptBtn: "Cancel Appointment",
    saveBtn: "Save",
    nearbyDoctorsTitle: "Nearby Dermatologists",
    nearbyPharmaciesTitle: "Nearby Pharmacies",
    currentAreaDefault: "Your Current Area",
    locatorSubtitle: "Live GPS & OpenStreetMap search for nearby Dermatologists, Clinics & Pharmacies.",
    useGpsBtn: "Use My Live GPS Location",
    searchPlaceholder: "Enter any city, area, or PIN code...",
    searchCityBtn: "Search Any City / PIN",
    mapHeader: "Live Nearby Doctors & Pharmacies Map",
    callFacilityBtn: "Call Facility",
    openRouteBtn: "Open Map Route",
    bookVisitHereBtn: "Book Visit Here →",
    signInModalTitle: "Sign In to Arogya Setu",
    createProfileModalTitle: "Create Your Personal Wellness Profile",
    authModalSub: "Sign in with your username and password to access your designated tools.",
    fullNameLabel: "Full Name",
    usernameLabel: "Username",
    passwordLabel: "Password",
    phoneLabel: "Phone Number",
    localityLabel: "Your City / Locality",
    staffCodeLabel: "Staff Designation Code (Optional)",
    signOutBtn: "Sign Out"
  },
  kn: {
    appName: "ಆರೋಗ್ಯ ಸೇತು",
    appTagline: "ನಿಮ್ಮ ದೈನಂದಿನ ಚರ್ಮ ಮತ್ತು ಆರೋಗ್ಯ ಸಂಗಾತಿ",
    guestBadge: "ಅತಿಥಿ ಬಳಕೆದಾರ (ಲಾಗಿನ್ ಆಗಿಲ್ಲ)",
    listenBtn: "ಆಲಿಸಿ",
    pauseBtn: "ವಿರಾಮ",
    resumeBtn: "ಮುಂದುವರಿಸಿ",
    voiceTourBtn: "ಧ್ವನಿ ಮಾರ್ಗದರ್ಶಿ",
    connectedBadge: "ಸಂಪರ್ಕಿತವಾಗಿದೆ",
    signInBtn: "ಲಾಗಿನ್",
    createAccountBtn: "ಖಾತೆ ತೆರೆಯಿರಿ",
    manageProfileBtn: "ಪ್ರೊಫೈಲ್ / ಲಾಗ್ ಔಟ್",
    tabLens: "ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್",
    tabJournal: "ಮುಖಪುಟ ಮತ್ತು ವರದಿಗಳು",
    tabAppointments: "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗಳು",
    tabDoctors: "ಹತ್ತಿರದ ವೈದ್ಯರು",
    tabPharmacies: "ಹತ್ತಿರದ ಫಾರ್ಮಸಿಗಳು",
    tabReferrals: "ಆಸ್ಪತ್ರೆ ಶಿಫಾರಸುಗಳು",
    tabAdmin: "ಅಡ್ಮಿನ್ ನಿಯಂತ್ರಣ",
    bannerText: "ನಮಸ್ಕಾರ! ಆರೋಗ್ಯ ಸೇತುಗೆ ಸ್ವಾಗತ. ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್ ನಿಮ್ಮ ಫೋಟೋದಲ್ಲಿ ಏನಿದೆ ಎಂದು ತಿಳಿಸುತ್ತದೆ, ಚರ್ಮದ ರೋಗ, ಅದರ ಕಾರಣ, ತೀವ್ರತೆ ಮತ್ತು ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸನ್ನು ನೀಡುತ್ತದೆ.",
    hearStepsVoice: "ಹಂತ 1: ಹೆಸರು ಮತ್ತು ದೇಹದ ಭಾಗವನ್ನು ಆಯ್ಕೆಮಾಡಿ. ಹಂತ 2: ಲೈವ್ ಕ್ಯಾಮೆರಾ ತೆರೆದು ಫೋಟೋ ತೆಗೆಯಿರಿ ಅಥವಾ ಸಾಧನದಿಂದ ಫೋಟೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. ಹಂತ 3: ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್ ಬಟನ್ ಒತ್ತಿರಿ.",
    voiceTourText: "ಆರೋಗ್ಯ ಸೇತು ಧ್ವನಿ ಮಾರ್ಗದರ್ಶಿಗೆ ಸ್ವಾಗತ. ಚರ್ಮದ ತಪಾಸಣೆ, ಉಳಿಸಿದ ವರದಿಗಳು, ವೈದ್ಯರ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಮತ್ತು ಹತ್ತಿರದ ಫಾರ್ಮಸಿಗಳನ್ನು ನೀವು ಇಲ್ಲಿ ಸುಲಭವಾಗಿ ಬಳಸಬಹುದು.",
    companionBadge: "ತಕ್ಷಣದ ಧ್ವನಿ ಸಹಾಯಕ",
    snapOrUploadTitle: "ಫೋಟೋ ತೆಗೆಯಿರಿ ಅಥವಾ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
    hearStepsBtn: "ಹಂತಗಳನ್ನು ಆಲಿಸಿ",
    whoForLabel: "ಈ ತಪಾಸಣೆ ಯಾರಿಗಾಗಿ?",
    whoForDefault: "ಸ್ವಂತ / ಕುಟುಂಬ ಸದಸ್ಯರು",
    bodyAreaLabel: "ದೇಹದ ಯಾವ ಭಾಗದಲ್ಲಿ?",
    bodyAreas: ["ತೋಳು / ಮುಂಗೈ", "ಮುಖ / ಕತ್ತು", "ಕೈ / ಹಸ್ತ", "ಕಾಲು / ಪಾದ", "ಬೆನ್ನು / ದೇಹ"],
    consentText: "ಫೋಟೋದಲ್ಲಿ ಏನಿದೆ ಎಂದು ಗುರುತಿಸಲು, ಚರ್ಮದ ಸಮಸ್ಯೆ, ಕಾರಣ ಮತ್ತು ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸನ್ನು ಪಡೆಯಲು ನಾನು ಒಪ್ಪುತ್ತೇನೆ.",
    reticleInstruction: "ಫೋಟೋ ತೆಗೆಯಲು ಲೈವ್ ಕ್ಯಾಮೆರಾ ಬಳಸಿ ಅಥವಾ ನಿಮ್ಮ ಫೋನ್/ಕಂಪ್ಯೂಟರ್‌ನಿಂದ ಚಿತ್ರವನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
    reticleTitle: "ಲೈವ್ ಕ್ಯಾಮೆರಾ ಅಥವಾ ಫೋಟೋ ಅಪ್‌ಲೋಡ್",
    openCameraBtn: "ಲೈವ್ ಕ್ಯಾಮೆರಾ ತೆರೆಯಿರಿ",
    snapNowBtn: "ಈಗ ಫೋಟೋ ತೆಗೆಯಿರಿ",
    closeBtn: "ಮುಚ್ಚಿ",
    uploadDeviceBtn: "ಸಾಧನದಿಂದ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
    scanBtn: "ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್ ಮೂಲಕ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ",
    scanningBtn: "ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ...",
    reportTitle: "ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್ ವರದಿ",
    readyBadge: "ಸ್ಕ್ಯಾನ್ ಮಾಡಲು ಸಿದ್ಧವಾಗಿದೆ",
    readyDesc: "ಲೈವ್ ಕ್ಯಾಮೆರಾ ತೆರೆದು ಫೋಟೋ ತೆಗೆಯಿರಿ ಅಥವಾ ನಿಮ್ಮ ಸಾಧನದಿಂದ ಫೋಟೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ, ನಂತರ ಸ್ಕ್ಯಾನ್ ಬಟನ್ ಒತ್ತಿರಿ.",
    identifiedLabel: "ಗುರುತಿಸಲಾದ ಸ್ಥಿತಿ",
    whatInPhotoLabel: "ಫೋಟೋದಲ್ಲಿ ಏನು ಕಂಡುಬಂದಿದೆ",
    causesLabel: "ಈ ಸ್ಥಿತಿಗೆ ಮುಖ್ಯ ಕಾರಣಗಳು",
    highAlertLabel: "ತುರ್ತು ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು",
    dermRecLabel: "ಚರ್ಮರೋಗ ತಜ್ಞರ ಶಿಫಾರಸು (Dermatology Recommendation)",
    specialistBadgeLabel: "ಶಿಫಾರಸು ಮಾಡಲಾದ ತಜ್ಞರು",
    helpfulCareLabel: "ಸಹಾಯಕ ಆರೈಕೆ / ಸಾಮಾನ್ಯ ಔಷಧಿ",
    greetingPrefix: "ನಮಸ್ಕಾರ",
    guestFriend: "ಅತಿಥಿ ಮಿತ್ರರೇ",
    heroDesc: "ನಿಮ್ಮ ಉಳಿಸಿದ ಚರ್ಮದ ಸ್ಕ್ಯಾನ್ ವರದಿಗಳನ್ನು ನೋಡಿ, ವೈದ್ಯರ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕ್ ಮಾಡಿ ಅಥವಾ 104 / 108 ಸಹಾಯವಾಣಿಗೆ ಕರೆ ಮಾಡಿ.",
    kpiSavedScans: "ಉಳಿಸಿದ ಸ್ಕ್ಯಾನ್‌ಗಳು",
    kpiStoredJournal: "ಜರ್ನಲ್‌ನಲ್ಲಿ ಸಂಗ್ರಹಿಸಲಾಗಿದೆ",
    kpiHighAlerts: "ಹೆಚ್ಚಿನ ತೀವ್ರತೆಯ ಎಚ್ಚರಿಕೆ",
    kpiDoctorAdvised: "ವೈದ್ಯರ ಭೇಟಿ ಸೂಚಿಸಲಾಗಿದೆ",
    kpiHelpline: "ಆರೋಗ್ಯ ಸಹಾಯವಾಣಿ",
    kpiDial104: "104 ಕ್ಕೆ ಕರೆ ಮಾಡಿ",
    kpiFreeAdvice: "ಉಚಿತ ವೈದ್ಯಕೀಯ ಸಲಹೆ",
    kpiEmergency: "ತುರ್ತು ಚಿಕಿತ್ಸೆ",
    kpiDial108: "108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ",
    kpiAmbulance: "24/7 ಆಂಬ್ಯುಲೆನ್ಸ್",
    savedScansTitle: "ಉಳಿಸಿದ ಸ್ಮಾರ್ಟ್ ಸ್ಕಿನ್ ಲೆನ್ಸ್ ಸ್ಕ್ಯಾನ್‌ಗಳು",
    colScanId: "ಸ್ಕ್ಯಾನ್ ID",
    colPerson: "ವ್ಯಕ್ತಿ",
    colWhatInPhoto: "ಫೋಟೋದಲ್ಲಿ ಏನಿತ್ತು",
    colCondition: "ಗುರುತಿಸಲಾದ ರೋಗ",
    colCauses: "ಕಾರಣಗಳು",
    colSeverity: "ತೀವ್ರತೆ",
    colCare: "ಸಹಾಯಕ ಆರೈಕೆ & ವೈದ್ಯರ ಶಿಫಾರಸು",
    bookAptTitle: "ಚರ್ಮರೋಗ ತಜ್ಞರ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕ್ ಮಾಡಿ",
    patientNameLabel: "ರೋಗಿಯ ಹೆಸರು",
    clinicNameLabel: "ಕ್ಲಿನಿಕ್ / ಆಸ್ಪತ್ರೆಯ ಹೆಸರು",
    specialtyLabel: "ವಿಭಾಗ",
    specialties: ["ಚರ್ಮರೋಗ ತಜ್ಞರು (Dermatology)", "ಸಾಮಾನ್ಯ ವೈದ್ಯಕೀಯ (OPD)", "ಅಲರ್ಜಿ ವಿಭಾಗ", "ಮಕ್ಕಳ ತಜ್ಞರು"],
    prefDateLabel: "ದಿನಾಂಕ",
    prefTimeLabel: "ಸಮಯ",
    notesLabel: "ವೈದ್ಯರಿಗೆ ಟಿಪ್ಪಣಿ",
    requestAptBtn: "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ವಿನಂತಿಸಿ",
    rescheduleBtn: "ದಿನಾಂಕ / ಸಮಯ ಬದಲಿಸಿ",
    confirmBtn: "ದೃಢೀಕರಿಸಿ",
    cancelAptBtn: "ರದ್ದುಮಾಡಿ",
    saveBtn: "ಉಳಿಸಿ",
    nearbyDoctorsTitle: "ಹತ್ತಿರದ ಚರ್ಮರೋಗ ತಜ್ಞರು",
    nearbyPharmaciesTitle: "ಹತ್ತಿರದ ಫಾರ್ಮಸಿಗಳು",
    currentAreaDefault: "ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಪ್ರದೇಶ",
    locatorSubtitle: "ಹತ್ತಿರದ ಚರ್ಮರೋಗ ತಜ್ಞರು, ಆಸ್ಪತ್ರೆ ಮತ್ತು ಮೆಡಿಕಲ್ ಶಾಪ್‌ಗಳಿಗಾಗಿ ಲೈವ್ ಜಿಪಿಎಸ್ ಹುಡುಕಾಟ.",
    useGpsBtn: "ನನ್ನ ಲೈವ್ GPS ಸ್ಥಳ ಬಳಸಿ",
    searchPlaceholder: "ಯಾವುದೇ ನಗರ, ಪ್ರದೇಶ ಅಥವಾ ಪಿನ್ ಕೋಡ್ ನಮೂದಿಸಿ...",
    searchCityBtn: "ನಗರ / ಪಿನ್ ಹುಡುಕಿ",
    mapHeader: "ಲೈವ್ ಹತ್ತಿರದ ವೈದ್ಯರು ಮತ್ತು ಫಾರ್ಮಸಿ ನಕ್ಷೆ",
    callFacilityBtn: "ಕರೆ ಮಾಡಿ",
    openRouteBtn: "ಮಾರ್ಗ ತೆರೆಯಿರಿ",
    bookVisitHereBtn: "ಇಲ್ಲಿ ಬುಕ್ ಮಾಡಿ →",
    signInModalTitle: "ಆರೋಗ್ಯ ಸೇತುಗೆ ಲಾಗಿನ್ ಮಾಡಿ",
    createProfileModalTitle: "ನಿಮ್ಮ ಹೊಸ ಖಾತೆಯನ್ನು ರಚಿಸಿ",
    authModalSub: "ನಿಮ್ಮ ಬಳಕೆದಾರ ಹೆಸರು ಮತ್ತು ಪಾಸ್‌ವರ್ಡ್ ಮೂಲಕ ಲಾಗಿನ್ ಮಾಡಿ.",
    fullNameLabel: "ಪೂರ್ಣ ಹೆಸರು",
    usernameLabel: "ಬಳಕೆದಾರ ಹೆಸರು (Username)",
    passwordLabel: "ಪಾಸ್‌ವರ್ಡ್ (Password)",
    phoneLabel: "ಫೋನ್ ಸಂಖ್ಯೆ",
    localityLabel: "ನಿಮ್ಮ ನಗರ / ಊರು",
    staffCodeLabel: "ಸಿಬ್ಬಂದಿ ಕೋಡ್ (PHC2026 / ADMIN2026)",
    signOutBtn: "ಲಾಗ್ ಔಟ್"
  },
  hi: {
    appName: "आरोग्य सेतु",
    appTagline: "आपका दैनिक त्वचा और स्वास्थ्य साथी",
    guestBadge: "अतिथि उपयोगकर्ता (लॉगिन नहीं है)",
    listenBtn: "सुनें",
    pauseBtn: "रोकें",
    resumeBtn: "जारी रखें",
    voiceTourBtn: "वॉइस टूर",
    connectedBadge: "कनेक्टेड",
    signInBtn: "लॉगिन करें",
    createAccountBtn: "खाता बनाएं",
    manageProfileBtn: "प्रोफ़ाइल / लॉग आउट",
    tabLens: "स्मार्ट स्किन लेंस",
    tabJournal: "होम और जर्नल",
    tabAppointments: "अपॉइंटमेंट",
    tabDoctors: "नजदीकी डॉक्टर",
    tabPharmacies: "नजदीकी फार्मेसी",
    tabReferrals: "अस्पताल रेफरल",
    tabAdmin: "एडमिन कंट्रोल",
    bannerText: "नमस्ते! आरोग्य सेतु में आपका स्वागत है। स्मार्ट स्किन लेंस बताता है कि आपकी फोटो में क्या है, त्वचा रोग का कारण क्या है, और त्वचा विशेषज्ञ (Dermatologist) की सिफारिश प्रदान करता है।",
    hearStepsVoice: "चरण 1: नाम और शरीर का हिस्सा चुनें। चरण 2: लाइव कैमरा खोलें या डिवाइस से फोटो अपलोड करें। चरण 3: स्मार्ट स्किन लेंस से स्कैन करें पर क्लिक करें।",
    voiceTourText: "आरोग्य सेतु वॉइस टूर में आपका स्वागत है। यहाँ आप त्वचा की जांच, सेव किए गए स्कैन, डॉक्टर अपॉइंटमेंट और जीपीएस से नजदीकी मेडिकल स्टोर खोज सकते हैं।",
    companionBadge: "त्वरित वॉइस सहायक",
    snapOrUploadTitle: "फोटो लें या अपलोड करें",
    hearStepsBtn: "चरण सुनें",
    whoForLabel: "यह जांच किसके लिए है?",
    whoForDefault: "स्वयं / परिवार के सदस्य",
    bodyAreaLabel: "शरीर के किस हिस्से पर?",
    bodyAreas: ["बांह / कलाई", "चेहरा / गर्दन", "हाथ / हथेली", "पैर / पंजा", "पीठ / धड़"],
    consentText: "मैं स्मार्ट स्किन लेंस से इस फोटो की जांच करने, बीमारी का कारण और त्वचा विशेषज्ञ की सलाह जानने के लिए सहमत हूँ।",
    reticleInstruction: "फोटो लेने के लिए लाइव कैमरा खोलें या अपने फोन/कंप्यूटर से फोटो अपलोड करें।",
    reticleTitle: "लाइव कैमरा या फोटो अपलोड",
    openCameraBtn: "लाइव कैमरा खोलें",
    snapNowBtn: "अभी फोटो लें",
    closeBtn: "बंद करें",
    uploadDeviceBtn: "डिवाइस से अपलोड करें",
    scanBtn: "स्मार्ट स्किन लेंस से फोटो स्कैन करें",
    scanningBtn: "फोटो की जांच हो रही है...",
    reportTitle: "स्मार्ट स्किन लेंस रिपोर्ट",
    readyBadge: "स्कैन के लिए तैयार",
    readyDesc: "लाइव कैमरा खोलकर 'अभी फोटो लें' पर क्लिक करें या डिवाइस से फोटो अपलोड करें, फिर स्कैन बटन दबाएं।",
    identifiedLabel: "पहचानी गई स्थिति",
    whatInPhotoLabel: "फोटो में क्या दिखा",
    causesLabel: "इस समस्या का मुख्य कारण",
    highAlertLabel: "तत्काल त्वचा विशेषज्ञ (Dermatologist) की सिफारिश",
    dermRecLabel: "त्वचा विशेषज्ञ की सिफारिश (Dermatology Recommendation)",
    specialistBadgeLabel: "अनुशंसित विशेषज्ञ",
    helpfulCareLabel: "सहायक देखभाल / सामान्य दवाइयाँ",
    greetingPrefix: "नमस्ते",
    guestFriend: "अतिथि मित्र",
    heroDesc: "अपने सेव किए गए स्किन स्कैन देखें, डॉक्टर अपॉइंटमेंट प्रबंधित करें, या 104 / 108 स्वास्थ्य हेल्पलाइन पर कॉल करें।",
    kpiSavedScans: "सेव किए गए स्कैन",
    kpiStoredJournal: "जर्नल में सुरक्षित",
    kpiHighAlerts: "उच्च गंभीरता अलर्ट",
    kpiDoctorAdvised: "डॉक्टर की सलाह आवश्यक",
    kpiHelpline: "स्वास्थ्य हेल्पलाइन",
    kpiDial104: "104 डायल करें",
    kpiFreeAdvice: "मुफ्त चिकित्सा सलाह",
    kpiEmergency: "आपातकालीन सेवा",
    kpiDial108: "108 डायल करें",
    kpiAmbulance: "24/7 एम्बुलेंस",
    savedScansTitle: "सेव किए गए स्मार्ट स्किन लेंस स्कैन",
    colScanId: "स्कैन ID",
    colPerson: "व्यक्ति",
    colWhatInPhoto: "फोटो में क्या था",
    colCondition: "पहचानी गई बीमारी",
    colCauses: "कारण",
    colSeverity: "गंभीरता",
    colCare: "उपचार एवं त्वचा विशेषज्ञ सलाह",
    bookAptTitle: "त्वचा विशेषज्ञ अपॉइंटमेंट बुक करें",
    patientNameLabel: "मरीज का नाम",
    clinicNameLabel: "क्लिनिक / अस्पताल का नाम",
    specialtyLabel: "विशेषज्ञता",
    specialties: ["त्वचा विशेषज्ञ (Dermatology)", "सामान्य चिकित्सा (OPD)", "एलर्जी विशेषज्ञ", "बाल रोग विशेषज्ञ"],
    prefDateLabel: "पसंदीदा तारीख",
    prefTimeLabel: "पसंदीदा समय",
    notesLabel: "डॉक्टर के लिए विवरण",
    requestAptBtn: "अपॉइंटमेंट बुक करें",
    rescheduleBtn: "तारीख / समय बदलें",
    confirmBtn: "कन्फर्म करें",
    cancelAptBtn: "रद्द करें",
    saveBtn: "सेव करें",
    nearbyDoctorsTitle: "नजदीकी त्वचा विशेषज्ञ",
    nearbyPharmaciesTitle: "नजदीकी फार्मेसी",
    currentAreaDefault: "आपका वर्तमान क्षेत्र",
    locatorSubtitle: "नजदीकी त्वचा विशेषज्ञ, क्लिनिक और मेडिकल स्टोर के लिए लाइव GPS खोज।",
    useGpsBtn: "मेरी लाइव GPS लोकेशन चुनें",
    searchPlaceholder: "कोई भी शहर, क्षेत्र या पिन कोड दर्ज करें...",
    searchCityBtn: "शहर / पिन खोजें",
    mapHeader: "लाइव नजदीकी डॉक्टर और फार्मेसी मैप",
    callFacilityBtn: "कॉल करें",
    openRouteBtn: "मैप रास्ता देखें",
    bookVisitHereBtn: "यहाँ अपॉइंटमेंट लें →",
    signInModalTitle: "आरोग्य सेतु में लॉगिन करें",
    createProfileModalTitle: "अपना नया स्वास्थ्य खाता बनाएं",
    authModalSub: "अपने यूजरनेम और पासवर्ड से लॉगिन करें।",
    fullNameLabel: "पूरा नाम",
    usernameLabel: "यूजरनेम (Username)",
    passwordLabel: "पासवर्ड (Password)",
    phoneLabel: "फ़ोन नंबर",
    localityLabel: "आपका शहर / क्षेत्र",
    staffCodeLabel: "स्टाफ कोड (PHC2026 / ADMIN2026)",
    signOutBtn: "लॉग आउट"
  },
  ta: {
    appName: "ஆரோக்கிய சேது",
    appTagline: "உங்கள் தினசரி தோல் மற்றும் ஆரோக்கிய துணைவன்",
    guestBadge: "விருந்தினர் (உள்நுழையவில்லை)",
    listenBtn: "கேளுங்கள்",
    pauseBtn: "இடைநிறுத்து",
    resumeBtn: "தொடரவும்",
    voiceTourBtn: "குரல் வழிகாட்டி",
    connectedBadge: "இணைக்கப்பட்டுள்ளது",
    signInBtn: "உள்நுழைய",
    createAccountBtn: "கணக்கு தொடங்கு",
    manageProfileBtn: "சுயவிவரம் / வெளியேறு",
    tabLens: "ஸ்மார்ட் ஸ்கின் லென்ஸ்",
    tabJournal: "முகப்பு & பதிவேடு",
    tabAppointments: "அப்பாயின்ட்மென்ட்",
    tabDoctors: "அருகிலுள்ள மருத்துவர்கள்",
    tabPharmacies: "அருகிலுள்ள மருந்தகங்கள்",
    tabReferrals: "மருத்துவமனை பரிந்துரை",
    tabAdmin: "அட்மின் கட்டுப்பாடு",
    bannerText: "வணக்கம்! ஆரோக்கிய சேதுவிற்கு வரவேற்கிறோம். ஸ்மார்ட் ஸ்கின் லென்ஸ் உங்கள் புகைப்படத்தை ஆய்வு செய்து தோல் நோய், காரணம் மற்றும் தோல் மருத்துவர் பரிந்துரையை வழங்குகிறது.",
    hearStepsVoice: "படி 1: பெயர் மற்றும் உடல் பகுதியைத் தேர்ந்தெடுக்கவும். படி 2: நேரடி கேமரா அல்லது புகைப்படத்தை பதிவேற்றவும். படி 3: ஸ்மார்ட் ஸ்கின் லென்ஸ் பொத்தானை அழுத்தவும்.",
    voiceTourText: "ஆரோக்கிய சேது குரல் வழிகாட்டிக்கு வரவேற்கிறோம்.",
    companionBadge: "உடனடி குரல் உதவி",
    snapOrUploadTitle: "புகைப்படம் எடுக்கவும் அல்லது பதிவேற்றவும்",
    hearStepsBtn: "வழிமுறைகளைக் கேள்",
    whoForLabel: "இந்த பரிசோதனை யாருக்காக?",
    whoForDefault: "சுயம் / குடும்ப உறுப்பினர்",
    bodyAreaLabel: "உடலின் எந்தப் பகுதியில்?",
    bodyAreas: ["கை / முன்கை", "முகம் / கழுத்து", "உள்ளங்கை", "கால் / பாதம்", "முதுகு / உடல்"],
    consentText: "புகைப்படத்தை ஆய்வு செய்து தோல் நிலை, காரணம் மற்றும் தோல் மருத்துவர் பரிந்துரையை அறிய சம்மதிக்கிறேன்.",
    reticleInstruction: "நேரடி கேமரா மூலம் புகைப்படம் எடுக்கவும் அல்லது உங்கள் தொலைபேசியில் இருந்து பதிவேற்றவும்.",
    reticleTitle: "நேரடி கேமரா / புகைப்படம்",
    openCameraBtn: "நேரடி கேமராவைத் திற",
    snapNowBtn: "புகைப்படம் எடு",
    closeBtn: "மூடு",
    uploadDeviceBtn: "சாதனத்திலிருந்து பதிவேற்று",
    scanBtn: "ஸ்மார்ட் ஸ்கின் லென்ஸ் மூலம் ஸ்கேன் செய்",
    scanningBtn: "ஆய்வு செய்யப்படுகிறது...",
    reportTitle: "ஸ்மார்ட் ஸ்கின் லென்ஸ் அறிக்கை",
    readyBadge: "ஸ்கேன் செய்ய தயார்",
    readyDesc: "கேமராவைத் திறந்து புகைப்படம் எடுக்கவும் அல்லது பதிவேற்றவும், பின்னர் ஸ்கேன் பொத்தானை அழுத்தவும்.",
    identifiedLabel: "கண்டறியப்பட்ட நிலை",
    whatInPhotoLabel: "புகைப்படத்தில் தெரிவது",
    causesLabel: "இதற்கான காரணங்கள்",
    highAlertLabel: "உடனடி தோல் மருத்துவர் பரிந்துரை",
    dermRecLabel: "தோல் மருத்துவர் பரிந்துரை (Dermatology Recommendation)",
    specialistBadgeLabel: "பரிந்துரைக்கப்பட்ட நிபுணர்",
    helpfulCareLabel: "பராமரிப்பு / சாதாரண மருந்துகள்",
    greetingPrefix: "வணக்கம்",
    guestFriend: "விருந்தினர் நண்பரே",
    heroDesc: "உங்கள் சேமித்த தோல் ஸ்கேன்களைப் பார்க்கவும், மருத்துவர் அப்பாயின்ட்மென்ட் பதிவு செய்யவும் அல்லது 104 / 108 ஐ அழைக்கவும்.",
    kpiSavedScans: "சேமித்த ஸ்கேன்கள்",
    kpiStoredJournal: "பதிவேட்டில் உள்ளது",
    kpiHighAlerts: "அதிக தீவிர எச்சரிக்கை",
    kpiDoctorAdvised: "மருத்துவர் ஆலோசனை தேவை",
    kpiHelpline: "சுகாதார உதவி எண்",
    kpiDial104: "104 ஐ அழைக்கவும்",
    kpiFreeAdvice: "இலவச மருத்துவ ஆலோசனை",
    kpiEmergency: "அவசர உதவி",
    kpiDial108: "108 ஐ அழைக்கவும்",
    kpiAmbulance: "24/7 ஆம்புலன்ஸ்",
    savedScansTitle: "சேமித்த ஸ்மார்ட் ஸ்கின் லென்ஸ் ஸ்கேன்கள்",
    colScanId: "ஸ்கேன் எண்",
    colPerson: "நபர்",
    colWhatInPhoto: "புகைப்பட விவரம்",
    colCondition: "கண்டறியப்பட்ட நோய்",
    colCauses: "காரணங்கள்",
    colSeverity: "தீவிரம்",
    colCare: "மருந்து & மருத்துவர் பரிந்துரை",
    bookAptTitle: "தோல் மருத்துவர் அப்பாயின்ட்மென்ட்",
    patientNameLabel: "நோயாளியின் பெயர்",
    clinicNameLabel: "மருத்துவமனை பெயர்",
    specialtyLabel: "பிரிவு",
    specialties: ["தோல் மருத்துவர் (Dermatology)", "பொது மருத்துவம் (OPD)", "ஒவ்வாமை பிரிவு", "குழந்தைகள் நலம்"],
    prefDateLabel: "தேதி",
    prefTimeLabel: "நேரம்",
    notesLabel: "மருத்துவருக்கான குறிப்பு",
    requestAptBtn: "அப்பாயின்ட்மென்ட் கோருங்கள்",
    rescheduleBtn: "தேதி / நேரம் மாற்று",
    confirmBtn: "உறுதி செய்",
    cancelAptBtn: "ரத்து செய்",
    saveBtn: "சேமி",
    nearbyDoctorsTitle: "அருகிலுள்ள தோல் மருத்துவர்கள்",
    nearbyPharmaciesTitle: "அருகிலுள்ள மருந்தகங்கள்",
    currentAreaDefault: "உங்கள் தற்போதைய பகுதி",
    locatorSubtitle: "அருகிலுள்ள தோல் மருத்துவர்கள் மற்றும் மருந்தகங்களுக்கான நேரடி ஜிபிஎஸ் தேடல்.",
    useGpsBtn: "எனது நேரடி GPS இருப்பிடம்",
    searchPlaceholder: "நகரம் அல்லது பின்கோடு உள்ளிடவும்...",
    searchCityBtn: "நகரம் / பின்கோடு தேடு",
    mapHeader: "அருகிலுள்ள மருத்துவர்கள் & மருந்தக வரைபடம்",
    callFacilityBtn: "அழைக்கவும்",
    openRouteBtn: "வழித்தடம்",
    bookVisitHereBtn: "இங்கே முன்பதிவு செய் →",
    signInModalTitle: "ஆரோக்கிய சேது உள்நுழைவு",
    createProfileModalTitle: "புதிய கணக்கை உருவாக்கவும்",
    authModalSub: "பயனர்பெயர் மற்றும் கடவுச்சொல் மூலம் உள்நுழையவும்.",
    fullNameLabel: "முழு பெயர்",
    usernameLabel: "பயனர்பெயர் (Username)",
    passwordLabel: "கடவுச்சொல் (Password)",
    phoneLabel: "தொலைபேசி எண்",
    localityLabel: "உங்கள் ஊர் / நகரம்",
    staffCodeLabel: "பணியாளர் குறியீடு (PHC2026 / ADMIN2026)",
    signOutBtn: "வெளியேறு"
  },
  te: {
    appName: "ఆరోగ్య సేతు",
    appTagline: "మీ రోజువారీ చర్మ మరియు ఆరోగ్య నేస్తం",
    guestBadge: "అతిథి వినియోగదారు (లాగిన్ అవ్వలేదు)",
    listenBtn: "వినండి",
    pauseBtn: "ఆపండి",
    resumeBtn: "కొనసాగించు",
    voiceTourBtn: "వాయిస్ టూర్",
    connectedBadge: "కనెక్ట్ చేయబడింది",
    signInBtn: "లాగిన్",
    createAccountBtn: "ఖాతా తెరవండి",
    manageProfileBtn: "ప్రొఫైల్ / లాగ్ అవుట్",
    tabLens: "స్మార్ట్ స్కిన్ లెన్స్",
    tabJournal: "హోమ్ & జర్నల్",
    tabAppointments: "అపాయింట్‌మెంట్లు",
    tabDoctors: "సమీప డాక్టర్లు",
    tabPharmacies: "సమీప ఫార్మసీలు",
    tabReferrals: "ఆసుపత్రి రిఫరల్స్",
    tabAdmin: "అడ్మిన్ కంట్రోల్",
    bannerText: "నమస్కారం! ఆరోగ్య సేతుకు స్వాగతం. స్మార్ట్ స్కిన్ లెన్స్ మీ ఫోటోలో ఏముందో గుర్తించి, చర్మ సమస్య, కారణాలు మరియు డెర్మటాలజీ నిపుణుల సిఫార్సును అందిస్తుంది.",
    hearStepsVoice: "దశ 1: పేరు మరియు శరీర భాగాన్ని ఎంచుకోండి. దశ 2: లైవ్ కెమెరా లేదా ఫోటోను అప్‌లోడ్ చేయండి. దశ 3: స్కాన్ బటన్‌పై క్లిక్ చేయండి.",
    voiceTourText: "ఆరోగ్య సేతు వాయిస్ టూర్‌కు స్వాగతం.",
    companionBadge: "తక్షణ వాయిస్ సహాయకుడు",
    snapOrUploadTitle: "ఫోటో తీయండి లేదా అప్‌లోడ్ చేయండి",
    hearStepsBtn: "దశలు వినండి",
    whoForLabel: "ఈ పరీక్ష ఎవరి కోసం?",
    whoForDefault: "స్వయం / కుటుంబ సభ్యులు",
    bodyAreaLabel: "శరీరంపై ఏ భాగంలో?",
    bodyAreas: ["చేయి / ముంజేయి", "ముఖం / మెడ", "అరచేయి", "కాలు / పాదం", "వీపు / శరీరం"],
    consentText: "ఫోటోను స్కాన్ చేసి చర్మ సమస్య, కారణాలు మరియు డెర్మటాలజీ సిఫార్సు తెలుసుకోవడానికి నేను అంగీకరిస్తున్నాను.",
    reticleInstruction: "లైవ్ కెమెరాతో ఫోటో తీయండి లేదా మీ ఫోన్/కంప్యూటర్ నుండి ఫోటో అప్‌లోడ్ చేయండి.",
    reticleTitle: "లైవ్ కెమెరా లేదా ఫోటో అప్‌లోడ్",
    openCameraBtn: "లైవ్ కెమెరా తెరవండి",
    snapNowBtn: "ఇప్పుడే ఫోటో తీయండి",
    closeBtn: "మూసివేయి",
    uploadDeviceBtn: "డివైస్ నుండి అప్‌లోడ్",
    scanBtn: "స్మార్ట్ స్కిన్ లెన్స్‌తో స్కాన్ చేయండి",
    scanningBtn: "పరిశీలిస్తోంది...",
    reportTitle: "స్మార్ట్ స్కిన్ లెన్స్ రిపోర్ట్",
    readyBadge: "స్కాన్ చేయడానికి సిద్ధం",
    readyDesc: "లైవ్ కెమెరా తెరిచి ఫోటో తీయండి లేదా ఫోటో అప్‌లోడ్ చేసి స్కాన్ బటన్ నొక్కండి.",
    identifiedLabel: "గుర్తించబడిన స్థితి",
    whatInPhotoLabel: "ఫోటోలో ఏమి కనిపించింది",
    causesLabel: "దీనికి ప్రధాన కారణాలు",
    highAlertLabel: "తక్షణ డెర్మటాలజీ నిపుణుల సిఫార్సు",
    dermRecLabel: "డెర్మటాలజీ నిపుణుల సిఫార్సు (Dermatology Recommendation)",
    specialistBadgeLabel: "సిఫార్సు చేయబడిన నిపుణులు",
    helpfulCareLabel: "సహాయక సంరక్షణ / సాధారణ మందులు",
    greetingPrefix: "నమస్కారం",
    guestFriend: "అతిథి మిత్రమా",
    heroDesc: "మీ సేవ్ చేసిన స్కిన్ స్కాన్‌లను చూడండి, డాక్టర్ అపాయింట్‌మెంట్లు బుక్ చేయండి లేదా 104 / 108 కి కాల్ చేయండి.",
    kpiSavedScans: "సేవ్ చేసిన స్కాన్‌లు",
    kpiStoredJournal: "జర్నల్‌లో నిల్వ చేయబడింది",
    kpiHighAlerts: "అధిక తీవ్రత హెచ్చరికలు",
    kpiDoctorAdvised: "డాక్టర్ సంప్రదింపు అవసరం",
    kpiHelpline: "ఆరోగ్య హెల్ప్‌లైన్",
    kpiDial104: "104 కి కాల్ చేయండి",
    kpiFreeAdvice: "ఉచిత వైద్య సలహా",
    kpiEmergency: "అత్యవసర సేవ",
    kpiDial108: "108 కి కాల్ చేయండి",
    kpiAmbulance: "24/7 అంబులెన్స్",
    savedScansTitle: "సేవ్ చేసిన స్మార్ట్ స్కిన్ లెన్స్ స్కాన్‌లు",
    colScanId: "స్కాన్ ID",
    colPerson: "వ్యక్తి",
    colWhatInPhoto: "ఫోటోలో ఏముంది",
    colCondition: "గుర్తించిన వ్యాధి",
    colCauses: "కారణాలు",
    colSeverity: "తీవ్రత",
    colCare: "మందులు & డాక్టర్ సిఫార్సు",
    bookAptTitle: "డెర్మటాలజిస్ట్ అపాయింట్‌మెంట్ బుక్ చేయండి",
    patientNameLabel: "రోగి పేరు",
    clinicNameLabel: "క్లినిక్ / ఆసుపత్రి పేరు",
    specialtyLabel: "విభాగం",
    specialties: ["చర్మవ్యాధి నిపుణులు (Dermatology)", "జనరల్ మెడిసిన్ (OPD)", "అలెర్జీ విభాగం", "పిల్లల వైద్యులు"],
    prefDateLabel: "తేదీ",
    prefTimeLabel: "సమయం",
    notesLabel: "డాక్టర్ కోసం వివరాలు",
    requestAptBtn: "అపాయింట్‌మెంట్ బుక్ చేయండి",
    rescheduleBtn: "తేదీ / సమయం మార్చండి",
    confirmBtn: "నిర్ధారించండి",
    cancelAptBtn: "రద్దు చేయండి",
    saveBtn: "సేవ్",
    nearbyDoctorsTitle: "సమీప చర్మవ్యాధి నిపుణులు",
    nearbyPharmaciesTitle: "సమీప ఫార్మసీలు",
    currentAreaDefault: "మీ ప్రస్తుత ప్రాంతం",
    locatorSubtitle: "సమీప చర్మవ్యాధి నిపుణులు మరియు మెడికల్ షాపుల కోసం లైవ్ GPS శోధన.",
    useGpsBtn: "నా లైవ్ GPS లొకేషన్ వాడండి",
    searchPlaceholder: "ఏదైనా నగరం లేదా పిన్ కోడ్ నమోదు చేయండి...",
    searchCityBtn: "నగరం / పిన్ వెతకండి",
    mapHeader: "లైవ్ సమీప డాక్టర్లు & ఫార్మసీ మ్యాప్",
    callFacilityBtn: "కాల్ చేయండి",
    openRouteBtn: "మ్యాప్ రూట్",
    bookVisitHereBtn: "ఇక్కడ బుక్ చేయండి →",
    signInModalTitle: "ఆరోగ్య సేతు లాగిన్",
    createProfileModalTitle: "కొత్త ఖాతాను సృష్టించండి",
    authModalSub: "మీ యూజర్‌నేమ్ మరియు పాస్‌వర్డ్‌తో లాగిన్ అవ్వండి.",
    fullNameLabel: "పూర్తి పేరు",
    usernameLabel: "యూజర్‌నేమ్ (Username)",
    passwordLabel: "పాస్‌వర్డ్ (Password)",
    phoneLabel: "ఫోన్ నంబర్",
    localityLabel: "మీ నగరం / ప్రాంతం",
    staffCodeLabel: "స్టాఫ్ కోడ్ (PHC2026 / ADMIN2026)",
    signOutBtn: "లాగ్ అవుట్"
  },
  ml: {
    appName: "ആരോഗ്യ സേതു",
    appTagline: "നിങ്ങളുടെ ദൈനംദിന ചർമ്മ-ആരോഗ്യ സഹായി",
    guestBadge: "അതിഥി ഉപയോക്താവ് (ലോഗിൻ ചെയ്തിട്ടില്ല)",
    listenBtn: "കേൾക്കുക",
    pauseBtn: "നിർത്തുക",
    resumeBtn: "തുടരുക",
    voiceTourBtn: "വോയ്സ് ടൂർ",
    connectedBadge: "കണക്റ്റഡ്",
    signInBtn: "ലോഗിൻ",
    createAccountBtn: "അക്കൗണ്ട് തുടങ്ങുക",
    manageProfileBtn: "പ്രൊഫൈൽ / ലോഗ് ഔട്ട്",
    tabLens: "സ്മാർട്ട് സ്കിൻ ലെൻസ്",
    tabJournal: "ഹോം & ജേണൽ",
    tabAppointments: "അപ്പോയിന്റ്മെന്റുകൾ",
    tabDoctors: "സമീപത്തുള്ള ഡോക്ടർമാർ",
    tabPharmacies: "സമീപത്തുള്ള ഫാർമസികൾ",
    tabReferrals: "ആശുപത്രി റഫറലുകൾ",
    tabAdmin: "അഡ്മിൻ നിയന്ത്രണം",
    bannerText: "നമസ്കാരം! ആരോഗ്യ സേതുവിലേക്ക് സ്വാഗതം. സ്മാർട്ട് സ്കിൻ ലെൻസ് നിങ്ങളുടെ ഫോട്ടോ പരിശോധിച്ച് ചർമ്മരോഗം, കാരണം, ഡെർമറ്റോളജി ശുപാർശ എന്നിവ വ്യക്തമാക്കുന്നു.",
    hearStepsVoice: "ഘട്ടം 1: പേരും ശരീരഭാഗവും തിരഞ്ഞെടുക്കുക. ഘട്ടം 2: ക്യാമറ വഴിയോ ഫോണിൽ നിന്നോ ഫോട്ടോ നൽകുക. ഘട്ടം 3: സ്കാൻ ബട്ടൺ അമർത്തുക.",
    voiceTourText: "ആരോഗ്യ സേതു വോയ്സ് ടൂറിലേക്ക് സ്വാഗതം.",
    companionBadge: "വോയ്സ് അസിസ്റ്റന്റ്",
    snapOrUploadTitle: "ഫോട്ടോ എടുക്കുക അല്ലെങ്കിൽ അപ്‌ലോഡ് ചെയ്യുക",
    hearStepsBtn: "ഘട്ടങ്ങൾ കേൾക്കുക",
    whoForLabel: "ഈ പരിശോധന ആർക്കുവേണ്ടിയാണ്?",
    whoForDefault: "സ്വയം / കുടുംബാംഗം",
    bodyAreaLabel: "ശരീരത്തിന്റെ ഏത് ഭാഗത്ത്?",
    bodyAreas: ["കൈ / മണിബന്ധം", "മുഖം / കഴുത്ത്", "ഉള്ളംകൈ", "കാൽ / പാദം", "പുറം / ശരീരം"],
    consentText: "ഫോട്ടോ പരിശോധിച്ച് ചർമ്മരോഗം, കാരണം, ഡെർമറ്റോളജി ശുപാർശ എന്നിവ അറിയാൻ ഞാൻ സമ്മതിക്കുന്നു.",
    reticleInstruction: "ലൈവ് ക്യാമറ ഉപയോഗിച്ച് ഫോട്ടോ എടുക്കുക അല്ലെങ്കിൽ ഫോണിൽ നിന്ന് അപ്‌ലോഡ് ചെയ്യുക.",
    reticleTitle: "ലൈവ് ക്യാമറ / ഫോട്ടോ അപ്‌ലോഡ്",
    openCameraBtn: "ലൈവ് ക്യാമറ തുറക്കുക",
    snapNowBtn: "ഇപ്പോൾ ഫോട്ടോ എടുക്കുക",
    closeBtn: "അടയ്ക്കുക",
    uploadDeviceBtn: "ഉപകരണത്തിൽ നിന്ന് അപ്‌ലോഡ്",
    scanBtn: "സ്മാർട്ട് സ്കിൻ ലെൻസ് വഴി സ്കാൻ ചെയ്യുക",
    scanningBtn: "പരിശോധിക്കുന്നു...",
    reportTitle: "സ്മാർട്ട് സ്കിൻ ലെൻസ് റിപ്പോർട്ട്",
    readyBadge: "സ്കാൻ ചെയ്യാൻ തയ്യാർ",
    readyDesc: "ലൈവ് ക്യാമറ തുറന്ന് ഫോട്ടോ എടുക്കുക അല്ലെങ്കിൽ അപ്‌ലോഡ് ചെയ്ത ശേഷം സ്കാൻ ബട്ടൺ അമർത്തുക.",
    identifiedLabel: "കണ്ടെത്തിയ അവസ്ഥ",
    whatInPhotoLabel: "ഫോട്ടോയിൽ കാണുന്നത്",
    causesLabel: "പ്രധാന കാരണങ്ങൾ",
    highAlertLabel: "അടിയന്തര ഡെർമറ്റോളജി ശുപാർശ",
    dermRecLabel: "ഡെർമറ്റോളജി വിദഗ്ദ്ധ ശുപാർശ (Dermatology Recommendation)",
    specialistBadgeLabel: "ശുപാർശ ചെയ്യുന്ന വിദഗ്ദ്ധൻ",
    helpfulCareLabel: "പരിചരണം / സാധാരണ മരുന്നുകൾ",
    greetingPrefix: "നമസ്കാരം",
    guestFriend: "സുഹൃത്തേ",
    heroDesc: "നിങ്ങളുടെ സ്കിൻ സ്കാനുകൾ കാണുക, ഡോക്ടർ അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക അല്ലെങ്കിൽ 104 / 108 ഹെൽപ്‌ലൈനിൽ വിളിക്കുക.",
    kpiSavedScans: "സേവ് ചെയ്ത സ്കാനുകൾ",
    kpiStoredJournal: "ജേണലിൽ സൂക്ഷിച്ചു",
    kpiHighAlerts: "ഉയർന്ന തീവ്രത മുന്നറിയിപ്പ്",
    kpiDoctorAdvised: "ഡോക്ടറെ കാണുക",
    kpiHelpline: "ഹെൽത്ത് ഹെൽപ്‌ലൈൻ",
    kpiDial104: "104 വിളിക്കുക",
    kpiFreeAdvice: "സൗജന്യ വൈദ്യോപദേശം",
    kpiEmergency: "അടിയന്തര സഹായം",
    kpiDial108: "108 വിളിക്കുക",
    kpiAmbulance: "24/7 ആംബുലൻസ്",
    savedScansTitle: "സേവ് ചെയ്ത സ്മാർട്ട് സ്കിൻ ലെൻസ് സ്കാനുകൾ",
    colScanId: "സ്കാൻ ID",
    colPerson: "വ്യക്തി",
    colWhatInPhoto: "ഫോട്ടോ വിവരണം",
    colCondition: "കണ്ടെത്തിയ രോഗം",
    colCauses: "കാരണങ്ങൾ",
    colSeverity: "തീവ്രത",
    colCare: "മരുന്നുകളും ഡോക്ടർ ശുപാർശയും",
    bookAptTitle: "ഡെർമറ്റോളജിസ്റ്റ് അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക",
    patientNameLabel: "രോഗിയുടെ പേര്",
    clinicNameLabel: "ക്ലിനിക് / ആശുപത്രി പേര്",
    specialtyLabel: "വിഭാഗം",
    specialties: ["ചർമ്മരോഗ വിദഗ്ദ്ധൻ (Dermatology)", "ജനറൽ മെഡിസിൻ (OPD)", "അലർജി വിഭാഗം", "ശിശുരോഗ വിഭാഗം"],
    prefDateLabel: "തീയതി",
    prefTimeLabel: "സമയം",
    notesLabel: "ഡോക്ടർക്കുള്ള കുറിപ്പ്",
    requestAptBtn: "അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക",
    rescheduleBtn: "തീയതി / സമയം മാറ്റുക",
    confirmBtn: "സ്ഥിരീകരിക്കുക",
    cancelAptBtn: "റദ്ദാക്കുക",
    saveBtn: "സേവ്",
    nearbyDoctorsTitle: "സമീപത്തുള്ള ചർമ്മരോഗ വിദഗ്ദ്ധർ",
    nearbyPharmaciesTitle: "സമീപത്തുള്ള ഫാർമസികൾ",
    currentAreaDefault: "നിങ്ങളുടെ പ്രദേശം",
    locatorSubtitle: "സമീപത്തുള്ള ഡോക്ടർമാരെയും ഫാർമസികളെയും കണ്ടെത്താൻ ലൈവ് GPS ഉപയോഗിക്കുക.",
    useGpsBtn: "എന്റെ ലൈവ് GPS ലൊക്കേഷൻ",
    searchPlaceholder: "നഗരം അല്ലെങ്കിൽ പിൻകോഡ് നൽകുക...",
    searchCityBtn: "നഗരം / പിൻ തിരയുക",
    mapHeader: "സമീപത്തുള്ള ഡോക്ടർമാരുടെയും ഫാർമസികളുടെയും മാപ്പ്",
    callFacilityBtn: "വിളിക്കുക",
    openRouteBtn: "മാപ്പ് റൂട്ട്",
    bookVisitHereBtn: "ഇവിടെ ബുക്ക് ചെയ്യുക →",
    signInModalTitle: "ആരോഗ്യ സേതു ലോഗിൻ",
    createProfileModalTitle: "പുതിയ അക്കൗണ്ട് നിർമ്മിക്കുക",
    authModalSub: "നിങ്ങളുടെ യൂസർനെയിമും പാസ്‌വേഡും നൽകി ലോഗിൻ ചെയ്യുക.",
    fullNameLabel: "പൂർണ്ണ നാമം",
    usernameLabel: "യൂസർനെയിം (Username)",
    passwordLabel: "പാസ്‌വേഡ് (Password)",
    phoneLabel: "ഫോൺ നമ്പർ",
    localityLabel: "നിങ്ങളുടെ നഗരം / സ്ഥലം",
    staffCodeLabel: "സ്റ്റാഫ് കോഡ് (PHC2026 / ADMIN2026)",
    signOutBtn: "ലോഗ് ഔട്ട്"
  }
};

window.indicToDevanagariPhonetic = function (text) {
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code >= 0x0C80 && code <= 0x0CFF) out += String.fromCharCode(code - 0x0380);
    else if (code >= 0x0C00 && code <= 0x0C7F) out += String.fromCharCode(code - 0x0300);
    else if (code >= 0x0D00 && code <= 0x0D7F) out += String.fromCharCode(code - 0x0400);
    else if (code >= 0x0B80 && code <= 0x0BFF) out += String.fromCharCode(code - 0x0280);
    else out += text[i];
  }
  return out;
};
'''

HEADER_JSX = r'''window.HeaderAndNav = function ({
  lang, setLang, activeTab, setActiveTab, currentUser, backendOnline,
  voiceState, speakText, pauseVoice, resumeVoice, stopVoice,
  openSignIn, openCreateAccount, openProfileModal
}) {
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;
  const tabs = [
    { id: "lens", icon: "📷", label: tr.tabLens, roles: ["guest", "user", "worker", "admin"] },
    { id: "journal", icon: "♡", label: tr.tabJournal, roles: ["guest", "user", "worker", "admin"] },
    { id: "appointments", icon: "📅", label: tr.tabAppointments, roles: ["guest", "user", "worker", "admin"] },
    { id: "doctors", icon: "🩺", label: tr.tabDoctors, roles: ["guest", "user", "worker", "admin"] },
    { id: "pharmacies", icon: "💊", label: tr.tabPharmacies, roles: ["guest", "user", "worker", "admin"] },
    { id: "referrals", icon: "🧭", label: tr.tabReferrals, roles: ["worker", "admin"] },
    { id: "admin", icon: "🛡️", label: tr.tabAdmin, roles: ["admin"] }
  ];
  const userRole = currentUser ? currentUser.role : "guest";

  return (
    <>
      <header className="bg-[#FFFDF9] border-b border-amber-200/80 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center text-white text-xl shadow-sm">
              ☀️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-extrabold text-stone-900 tracking-tight">{tr.appName}</span>
                {!currentUser ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-100 border border-amber-300 text-[11px] font-bold text-amber-900">
                    {tr.guestBadge}
                  </span>
                ) : (
                  <button
                    onClick={openProfileModal}
                    className="px-2.5 py-0.5 rounded-full bg-emerald-100 border border-emerald-300 text-[11px] font-bold text-emerald-900 hover:bg-emerald-200 transition"
                  >
                    👤 {currentUser.fullName} ({currentUser.role.toUpperCase()})
                  </button>
                )}
              </div>
              <p className="text-[11px] text-stone-500">{tr.appTagline}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={lang}
              onChange={(e) => {
                const next = e.target.value;
                setLang(next);
                const nextPack = window.TRANSLATIONS[next] || window.TRANSLATIONS.en;
                speakText(nextPack.bannerText, next);
              }}
              className="px-3 py-1.5 rounded-full border border-amber-300 bg-[#FFF9EB] text-xs font-bold text-stone-800 cursor-pointer focus:outline-none"
            >
              {window.LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.display}</option>
              ))}
            </select>

            {voiceState === "idle" && (
              <button
                onClick={() => speakText(tr.bannerText, lang)}
                className="px-3.5 py-1.5 rounded-full bg-[#0D9488] hover:bg-[#0F766E] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm"
              >
                <span>▷</span> {tr.listenBtn}
              </button>
            )}
            {voiceState === "playing" && (
              <div className="flex items-center gap-1">
                <button onClick={pauseVoice} className="px-3 py-1.5 rounded-full bg-amber-500 text-white text-xs font-bold">
                  ⏸ {tr.pauseBtn}
                </button>
                <button onClick={stopVoice} className="px-2.5 py-1.5 rounded-full bg-rose-600 text-white text-xs font-bold">⏹</button>
              </div>
            )}
            {voiceState === "paused" && (
              <div className="flex items-center gap-1">
                <button onClick={resumeVoice} className="px-3 py-1.5 rounded-full bg-emerald-600 text-white text-xs font-bold">
                  ▷ {tr.resumeBtn}
                </button>
                <button onClick={stopVoice} className="px-2.5 py-1.5 rounded-full bg-rose-600 text-white text-xs font-bold">⏹</button>
              </div>
            )}

            <button
              onClick={() => speakText(tr.voiceTourText, lang)}
              className="px-3 py-1.5 rounded-full bg-[#FFF9EB] hover:bg-amber-100 border border-amber-300 text-amber-950 text-xs font-bold flex items-center gap-1"
            >
              <span>🎧</span> {tr.voiceTourBtn}
            </button>

            <span className="px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold flex items-center gap-1">
              <span>🛜</span> {backendOnline ? tr.connectedBadge : "Local"}
            </span>

            {!currentUser ? (
              <>
                <button onClick={openSignIn} className="px-3.5 py-1.5 rounded-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-bold shadow-sm">
                  → {tr.signInBtn}
                </button>
                <button onClick={openCreateAccount} className="px-3.5 py-1.5 rounded-full bg-[#292524] hover:bg-stone-800 text-white text-xs font-bold shadow-sm">
                  👤+ {tr.createAccountBtn}
                </button>
              </>
            ) : (
              <button onClick={openProfileModal} className="px-3.5 py-1.5 rounded-full bg-[#292524] hover:bg-stone-800 text-white text-xs font-bold shadow-sm">
                ⚙️ {tr.manageProfileBtn}
              </button>
            )}
          </div>
        </div>

        <div className="border-t border-amber-100 bg-[#FFFDF9]">
          <div className="max-w-6xl mx-auto px-4 py-2 flex items-center gap-2 overflow-x-auto">
            {tabs.filter((t) => t.roles.includes(userRole)).map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`px-4 py-1.5 rounded-full text-xs font-bold flex items-center gap-1.5 whitespace-nowrap transition ${
                  activeTab === t.id ? "bg-[#F97316] text-white shadow-sm" : "text-stone-700 hover:bg-amber-50"
                }`}
              >
                <span>{t.icon}</span> {t.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 mt-5">
        <div className="bg-white rounded-2xl border border-amber-200/90 px-5 py-3.5 flex flex-wrap items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center gap-3.5 flex-1 min-w-[260px]">
            <div className="w-9 h-9 rounded-full bg-amber-100 border border-amber-300 flex items-center justify-center text-amber-800 text-lg shrink-0">
              😊
            </div>
            <p className="text-xs sm:text-[13px] text-stone-700 leading-relaxed font-medium">{tr.bannerText}</p>
          </div>
          <button
            onClick={() => speakText(tr.bannerText, lang)}
            className="px-4 py-2 rounded-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shrink-0"
          >
            <span>▷</span> {tr.listenBtn}
          </button>
        </div>
      </div>
    </>
  );
};
'''

SMART_SKIN_LENS_JSX = r'''window.SmartSkinLens = function ({
  lang, currentUser, speakText, onScanCompleted, goToAppointments, goToDoctors
}) {
  const { useState, useRef, useEffect } = React;
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;

  const [personName, setPersonName] = useState(tr.whoForDefault);
  const [bodyPart, setBodyPart] = useState(tr.bodyAreas[0]);
  const [consent, setConsent] = useState(true);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [hasImage, setHasImage] = useState(false);
  const [previewDataUrl, setPreviewDataUrl] = useState(null);
  const [report, setReport] = useState(null);
  const [scanning, setScanning] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    setPersonName(tr.whoForDefault);
    setBodyPart(tr.bodyAreas[0]);
  }, [lang]);

  const extractMetrics = (canvas) => {
    const ctx = canvas.getContext("2d");
    const w = canvas.width, h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;

    let totalPixels = 0, skinPixels = 0, artificialPixels = 0;
    const skinLuma = [], skinCr = [], skinRG = [], centerPixels = [];
    let edgeAccum = 0, skinEdgeCount = 0;

    for (let y = 4; y < h - 4; y += 2) {
      for (let x = 4; x < w - 4; x += 2) {
        const idx = (y * w + x) * 4;
        const r = data[idx], g = data[idx + 1], b = data[idx + 2];
        totalPixels++;

        const Y = 0.299 * r + 0.587 * g + 0.114 * b;
        const Cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b;
        const Cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b;
        const rgDiff = r - g;

        const isSkin = Y > 32 && Y < 245 && Cr >= 130 && Cr <= 188 && Cb >= 72 && Cb <= 138 && r > b;
        const isArtificial = (b > r + 20 && b > g + 10) || (g > r + 20 && g > b + 15) || (Math.abs(r - g) < 5 && Math.abs(g - b) < 5 && (Y < 28 || Y > 242));
        if (isArtificial) artificialPixels++;

        const dx = (x - w / 2) / (w / 2), dy = (y - h / 2) / (h / 2);
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (isSkin) {
          skinPixels++;
          skinLuma.push(Y);
          skinCr.push(Cr);
          skinRG.push(rgDiff);
        }

        if (dist <= 0.58 && !isArtificial && Y > 15 && Y < 242) {
          const idxRight = (y * w + (x + 2)) * 4;
          const idxDown = ((y + 2) * w + x) * 4;
          const grad = (Math.abs(r - data[idxRight]) + Math.abs(g - data[idxRight + 1]) + Math.abs(r - data[idxDown]) + Math.abs(g - data[idxDown + 1])) * 0.25;
          centerPixels.push({ Y, Cr, rgDiff, grad });
          edgeAccum += grad;
          skinEdgeCount++;
        }
      }
    }

    const skinRatio = skinPixels / Math.max(1, totalPixels);
    const artificialRatio = artificialPixels / Math.max(1, totalPixels);

    if (skinPixels < 30 || centerPixels.length < 20) {
      return { skinRatio, artificialRatio, lesionSpotRatio: 0, redInflammation: 0, darkLesionContrast: 0, scalyEdgeScore: 0, colorAsymmetry: 0 };
    }

    const percentile = (arr, p) => {
      if (!arr.length) return 0;
      const sorted = [...arr].sort((a, b) => a - b);
      return sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor(sorted.length * p)))];
    };

    const baseLuma = percentile(skinLuma, 0.65);
    const baseCr = percentile(skinCr, 0.35);
    const baseRG = percentile(skinRG, 0.35);

    let abnormalSpotPixels = 0, redDiffSum = 0, redCount = 0, darkDiffSum = 0, darkCount = 0, crVarSum = 0;

    for (let i = 0; i < centerPixels.length; i++) {
      const px = centerPixels[i];
      const lumaDrop = baseLuma - px.Y;
      const crSpike = Math.max(px.Cr - baseCr, (px.rgDiff - baseRG) * 0.85);
      const absRedExcess = Math.max(0, px.Cr - 154, (px.rgDiff - 42) * 0.8);
      const effectiveRed = Math.max(crSpike, absRedExcess);

      if (effectiveRed > 6.5 || (lumaDrop > 28.0 && px.grad > 6.0)) abnormalSpotPixels++;
      if (effectiveRed > 4.0) { redDiffSum += effectiveRed; redCount++; }
      if (lumaDrop > 22.0 && px.grad > 5.0) { darkDiffSum += lumaDrop; darkCount++; }
      crVarSum += Math.pow(px.Cr - baseCr, 2) + Math.pow((px.Y - baseLuma) * 0.35, 2);
    }

    const lesionSpotRatio = abnormalSpotPixels / Math.max(1, centerPixels.length);
    const redFraction = redCount / Math.max(1, centerPixels.length);
    const darkFraction = darkCount / Math.max(1, centerPixels.length);

    const redInflammation = redFraction >= 0.04 ? (redDiffSum / redCount) * (0.8 + redFraction * 2.5) : 0;
    const darkLesionContrast = darkFraction >= 0.035 && darkFraction <= 0.65 ? (darkDiffSum / darkCount) * (0.75 + darkFraction * 2.2) : 0;
    const scalyEdgeScore = edgeAccum / Math.max(1, skinEdgeCount);
    const colorAsymmetry = Math.sqrt(crVarSum / Math.max(1, centerPixels.length)) * 1.45;

    return { skinRatio, artificialRatio, lesionSpotRatio, redInflammation, darkLesionContrast, scalyEdgeScore, colorAsymmetry };
  };

  const openLiveCamera = async () => {
    try {
      setCameraOpen(true);
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 520 }, height: { ideal: 520 } }, audio: false });
      streamRef.current = stream;
      setTimeout(() => { if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); } }, 80);
    } catch (e) {
      setCameraOpen(false);
      alert("Could not access camera.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    setCameraOpen(false);
  };

  const snapFromCamera = () => {
    const video = videoRef.current, canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = 260; canvas.height = 260;
    canvas.getContext("2d").drawImage(video, 0, 0, 260, 260);
    setPreviewDataUrl(canvas.toDataURL("image/jpeg", 0.92));
    setHasImage(true);
    stopCamera();
  };

  const handleUploadFile = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    stopCamera();
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current;
        canvas.width = 260; canvas.height = 260;
        canvas.getContext("2d").drawImage(img, 0, 0, 260, 260);
        setPreviewDataUrl(ev.target.result);
        setHasImage(true);
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  };

  const triggerScan = async () => {
    if (!consent || !hasImage || !canvasRef.current) return;
    setScanning(true);
    const metrics = extractMetrics(canvasRef.current);
    try {
      const resp = await window.ArogyaAPI.analyzeScan({
        ownerUsername: currentUser ? currentUser.username : "guest",
        person: personName || tr.whoForDefault,
        bodyPart,
        timestamp: new Date().toLocaleString(),
        lang,
        metrics
      });
      if (resp && resp.report) {
        setReport(resp.report);
        onScanCompleted();
        speakText(
          `${resp.report.identifiedCondition}. ${resp.report.whatWasInPhoto}. ${resp.report.causes}. ${resp.report.helpfulCare}. ${resp.report.dermatologyRecommendation || ""}`,
          lang
        );
      }
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 mt-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
      <canvas ref={canvasRef} width="260" height="260" className="hidden" />

      <div className="lg:col-span-6 bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="inline-block px-2.5 py-0.5 rounded-full bg-amber-100 text-[10px] font-extrabold text-amber-900 uppercase tracking-wider">
              {tr.companionBadge}
            </span>
            <h2 className="text-xl font-extrabold text-stone-900 mt-1">{tr.snapOrUploadTitle}</h2>
          </div>
          <button onClick={() => speakText(tr.hearStepsVoice, lang)} className="px-3.5 py-1.5 rounded-full border border-teal-300 bg-teal-50/60 hover:bg-teal-100 text-teal-900 text-xs font-bold flex items-center gap-1.5">
            <span>🔊</span> {tr.hearStepsBtn}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold text-stone-600 mb-1">{tr.whoForLabel}</label>
            <input type="text" value={personName} onChange={(e) => setPersonName(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800" />
          </div>
          <div>
            <label className="block text-xs font-bold text-stone-600 mb-1">{tr.bodyAreaLabel}</label>
            <select value={bodyPart} onChange={(e) => setBodyPart(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800 bg-white">
              {tr.bodyAreas.map((area, i) => <option key={i} value={area}>{area}</option>)}
            </select>
          </div>
        </div>

        <label className="flex items-start gap-2.5 p-3.5 rounded-2xl bg-[#FFFDF7] border border-amber-200 cursor-pointer">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 accent-amber-600 w-4 h-4 rounded" />
          <span className="text-xs text-stone-700 leading-relaxed">{tr.consentText}</span>
        </label>

        <div className="p-5 rounded-2xl border border-dashed border-amber-300 bg-[#FFFDF9] flex flex-col items-center text-center space-y-4">
          <p className="text-xs text-stone-600">{tr.reticleInstruction}</p>
          <div className="w-[260px] h-[260px] rounded-2xl border-2 border-[#D97706] bg-[#FFFBEB] relative flex items-center justify-center overflow-hidden shadow-inner">
            {cameraOpen ? (
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
            ) : previewDataUrl ? (
              <img src={previewDataUrl} alt="Skin preview" className="w-full h-full object-cover" />
            ) : (
              <div className="w-48 h-48 rounded-full border border-dashed border-amber-400 flex items-center justify-center">
                <div className="w-36 h-36 rounded-full border border-dashed border-amber-300 flex flex-col items-center justify-center px-3">
                  <span className="text-xs font-extrabold text-amber-900">{tr.reticleTitle}</span>
                  <span className="text-[10px] text-amber-700 mt-0.5">{tr.tabLens} (260×260)</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
            {!cameraOpen ? (
              <button type="button" onClick={openLiveCamera} className="px-4 py-2 rounded-full bg-[#0D9488] hover:bg-[#0F766E] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm">
                <span>📷</span> {tr.openCameraBtn}
              </button>
            ) : (
              <>
                <button type="button" onClick={snapFromCamera} className="px-4 py-2 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm">
                  <span>📸</span> {tr.snapNowBtn}
                </button>
                <button type="button" onClick={stopCamera} className="px-3.5 py-2 rounded-full bg-rose-600 text-white text-xs font-bold">
                  ✖ {tr.closeBtn}
                </button>
              </>
            )}
            <label className="px-4 py-2 rounded-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm cursor-pointer">
              <span>↑</span> {tr.uploadDeviceBtn}
              <input type="file" accept="image/*" onChange={handleUploadFile} className="hidden" />
            </label>
          </div>
        </div>

        <button type="button" onClick={triggerScan} disabled={scanning} className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-[#F6C478] via-[#F7A889] to-[#F493A4] hover:from-[#F59E0B] hover:to-[#F43F5E] text-white font-extrabold text-xs sm:text-sm shadow-sm transition flex items-center justify-center gap-2">
          <span>✨</span> {scanning ? tr.scanningBtn : tr.scanBtn}
        </button>
      </div>

      <div className="lg:col-span-6 bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm">
        <h3 className="text-lg font-extrabold text-stone-900 mb-4">{tr.reportTitle}</h3>
        {!report ? (
          <div className="p-10 rounded-2xl border border-dashed border-amber-300 bg-[#FFFDF9] flex flex-col items-center justify-center text-center space-y-3 min-h-[260px]">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 flex items-center justify-center text-amber-800 text-xl">👁️</div>
            <span className="px-3 py-1 rounded-full bg-amber-100 text-[10px] font-extrabold text-amber-900 uppercase tracking-wider">{tr.readyBadge}</span>
            <p className="text-xs text-stone-600 max-w-sm leading-relaxed">{tr.readyDesc}</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-[#FFFBEB] border border-amber-200 flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-[10px] font-extrabold uppercase text-amber-800">{tr.identifiedLabel}</span>
                <h4 className="text-base font-extrabold text-stone-900">{report.identifiedCondition}</h4>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-extrabold ${report.severity === "HIGH" ? "bg-rose-100 text-rose-800" : report.severity === "MILD" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-800"}`}>
                  {report.severity} ({report.confidence}%)
                </span>
                <button
                  onClick={() => speakText(`${report.identifiedCondition}. ${report.whatWasInPhoto}. ${report.causes}. ${report.helpfulCare}. ${report.dermatologyRecommendation || ""}`, lang)}
                  className="px-3 py-1 rounded-full bg-[#0D9488] text-white text-xs font-bold"
                >
                  ▷ {tr.listenBtn}
                </button>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-xs font-extrabold text-stone-700">📷 {tr.whatInPhotoLabel}</span>
              <p className="text-xs text-stone-700 leading-relaxed">{report.whatWasInPhoto}</p>
            </div>

            <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-xs font-extrabold text-stone-700">🧬 {tr.causesLabel}</span>
              <p className="text-xs text-stone-700 leading-relaxed">{report.causes}</p>
            </div>

            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-950 space-y-1.5">
              <span className="text-xs font-extrabold block">💊 {tr.helpfulCareLabel}</span>
              <p className="text-xs leading-relaxed font-semibold">{report.helpfulCare}</p>
            </div>

            {/* Dedicated Dermatology Specialist Recommendation Box */}
            <div className={`p-4 rounded-2xl border-2 space-y-3 ${
              report.severity === "HIGH"
                ? "bg-rose-50 border-rose-300 text-rose-950"
                : "bg-[#FFF9EB] border-amber-300 text-stone-900"
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-extrabold flex items-center gap-1.5">
                  <span>🩺</span> {report.severity === "HIGH" ? tr.highAlertLabel : tr.dermRecLabel}
                </span>
                {report.consultTimeline && (
                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${
                    report.severity === "HIGH" ? "bg-rose-200 text-rose-900" : "bg-amber-200 text-amber-950"
                  }`}>
                    ⏱️ {report.consultTimeline}
                  </span>
                )}
              </div>

              <p className="text-xs leading-relaxed font-semibold">
                {report.dermatologyRecommendation}
              </p>

              {report.specialistType && (
                <div className="text-[11px] font-bold text-teal-900 bg-white/90 px-3 py-1.5 rounded-xl border border-amber-200">
                  👨‍⚕️ {tr.specialistBadgeLabel}: <span className="font-extrabold">{report.specialistType}</span>
                </div>
              )}

              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={goToAppointments}
                  className={`px-4 py-2 rounded-full text-white text-xs font-extrabold shadow-sm ${
                    report.severity === "HIGH" ? "bg-rose-700 hover:bg-rose-800" : "bg-[#0D9488] hover:bg-[#0F766E]"
                  }`}
                >
                  📅 {tr.bookAptTitle}
                </button>
                <button
                  onClick={goToDoctors}
                  className="px-4 py-2 rounded-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-extrabold shadow-sm"
                >
                  🩺 {tr.nearbyDoctorsTitle}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
'''

HOME_JOURNAL_JSX = r'''window.HomeAndJournal = function ({ lang, scans, currentUser, goToSkinLens }) {
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;
  const highSeverityCount = scans.filter((s) => s.severity === "HIGH").length;

  return (
    <div className="max-w-6xl mx-auto px-4 mt-5 space-y-5">
      <div className="rounded-3xl bg-gradient-to-r from-[#F59E0B] via-[#F97316] to-[#F43F5E] p-7 text-white flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div className="space-y-1.5">
          <span className="inline-block px-3 py-0.5 rounded-full bg-white/20 text-[10px] font-extrabold uppercase tracking-wider">
            {currentUser ? `${currentUser.role.toUpperCase()}` : tr.guestBadge}
          </span>
          <h2 className="text-2xl font-extrabold">
            {tr.greetingPrefix}, {currentUser ? currentUser.fullName : tr.guestFriend}!
          </h2>
          <p className="text-xs text-white/90">{tr.heroDesc}</p>
        </div>
        <button onClick={goToSkinLens} className="px-5 py-2.5 rounded-full bg-white text-stone-900 hover:bg-amber-50 text-xs font-extrabold flex items-center gap-1.5 shadow">
          <span>📷</span> {tr.tabLens}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-amber-200 p-5 space-y-1 shadow-sm">
          <span className="text-[10px] font-extrabold text-stone-500 uppercase">{tr.kpiSavedScans}</span>
          <div className="text-3xl font-extrabold text-stone-900">{scans.length}</div>
          <span className="text-xs font-bold text-teal-700 block">{tr.kpiStoredJournal}</span>
        </div>
        <div className="bg-white rounded-2xl border border-rose-200 p-5 space-y-1 shadow-sm">
          <span className="text-[10px] font-extrabold text-rose-800 uppercase">{tr.kpiHighAlerts}</span>
          <div className="text-3xl font-extrabold text-rose-600">{highSeverityCount}</div>
          <span className="text-xs font-bold text-rose-700 block">{tr.kpiDoctorAdvised}</span>
        </div>
        <a href="tel:104" className="bg-[#F0FDF9] rounded-2xl border border-teal-200 p-5 flex items-center justify-between shadow-sm hover:bg-teal-50 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-teal-900 uppercase">{tr.kpiHelpline}</span>
            <div className="text-2xl font-extrabold text-teal-700">{tr.kpiDial104}</div>
            <span className="text-xs font-bold text-teal-700 block">{tr.kpiFreeAdvice}</span>
          </div>
          <span className="text-2xl text-teal-700">📞</span>
        </a>
        <a href="tel:108" className="bg-[#FFF5F5] rounded-2xl border border-rose-200 p-5 flex items-center justify-between shadow-sm hover:bg-rose-50 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-rose-900 uppercase">{tr.kpiEmergency}</span>
            <div className="text-2xl font-extrabold text-rose-600">{tr.kpiDial108}</div>
            <span className="text-xs font-bold text-rose-700 block">{tr.kpiAmbulance}</span>
          </div>
          <span className="text-2xl text-rose-600">📞</span>
        </a>
      </div>

      <div className="bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm">
        <h3 className="text-base font-extrabold text-stone-900 mb-4">{tr.savedScansTitle} ({scans.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#FFF9EB] text-stone-600 uppercase text-[10px] font-extrabold border-b border-amber-200">
                <th className="py-3 px-3 rounded-l-xl">{tr.colScanId}</th>
                <th className="py-3 px-3">{tr.colPerson}</th>
                <th className="py-3 px-3">{tr.colWhatInPhoto}</th>
                <th className="py-3 px-3">{tr.colCondition}</th>
                <th className="py-3 px-3">{tr.colCauses}</th>
                <th className="py-3 px-3">{tr.colSeverity}</th>
                <th className="py-3 px-3 rounded-r-xl">{tr.colCare}</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => (
                <tr key={s.id} className="border-b border-stone-100 hover:bg-amber-50/30">
                  <td className="py-3.5 px-3 font-extrabold text-stone-900">{s.id}</td>
                  <td className="py-3.5 px-3 text-stone-700">{s.person}</td>
                  <td className="py-3.5 px-3 text-stone-600 max-w-[200px]">{s.whatWasInPhoto}</td>
                  <td className="py-3.5 px-3 font-bold text-teal-900 max-w-[200px]">{s.identifiedCondition}</td>
                  <td className="py-3.5 px-3 text-stone-600 max-w-[200px]">{s.causes}</td>
                  <td className="py-3.5 px-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${s.severity === "HIGH" ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-800"}`}>
                      {s.severity}
                    </span>
                  </td>
                  <td className="py-3.5 px-3 text-stone-700 max-w-[240px]">{s.helpfulCare}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
'''

APPOINTMENTS_JSX = r'''window.Appointments = function ({ lang, appointments, currentUser, prefilledClinic, onRefresh }) {
  const { useState, useEffect } = React;
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;

  const [patientName, setPatientName] = useState(currentUser ? currentUser.fullName : "Guest Patient");
  const [clinicName, setClinicName] = useState(prefilledClinic || "Nearby Dermatology & Skin Care Clinic");
  const [specialty, setSpecialty] = useState(tr.specialties[0]);
  const [date, setDate] = useState("2026-10-22");
  const [time, setTime] = useState("10:30 AM");
  const [notes, setNotes] = useState("Requesting skin checkup after Smart Skin Lens scan.");

  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ date: "", time: "", notes: "", status: "" });

  useEffect(() => { if (prefilledClinic) setClinicName(prefilledClinic); }, [prefilledClinic]);
  useEffect(() => { setSpecialty(tr.specialties[0]); }, [lang]);

  const submitAppointment = async (e) => {
    e.preventDefault();
    await window.ArogyaAPI.createAppointment({
      patientUsername: currentUser ? currentUser.username : "guest",
      patientName, clinicName, specialty, date, time, notes
    });
    await onRefresh();
  };

  const canManage = currentUser && (currentUser.role === "worker" || currentUser.role === "admin");

  return (
    <div className="max-w-6xl mx-auto px-4 mt-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
      <form onSubmit={submitAppointment} className="lg:col-span-5 bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm space-y-3.5">
        <h2 className="text-lg font-extrabold text-stone-900 flex items-center gap-2"><span>📅</span> {tr.bookAptTitle}</h2>
        <div>
          <label className="block text-xs font-bold text-stone-600 mb-1">{tr.patientNameLabel}</label>
          <input type="text" required value={patientName} onChange={(e) => setPatientName(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800" />
        </div>
        <div>
          <label className="block text-xs font-bold text-stone-600 mb-1">{tr.clinicNameLabel}</label>
          <input type="text" required value={clinicName} onChange={(e) => setClinicName(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800" />
        </div>
        <div>
          <label className="block text-xs font-bold text-stone-600 mb-1">{tr.specialtyLabel}</label>
          <select value={specialty} onChange={(e) => setSpecialty(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800 bg-white">
            {tr.specialties.map((s, i) => <option key={i} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold text-stone-600 mb-1">{tr.prefDateLabel}</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-full px-3 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800" />
          </div>
          <div>
            <label className="block text-xs font-bold text-stone-600 mb-1">{tr.prefTimeLabel}</label>
            <input type="text" value={time} onChange={(e) => setTime(e.target.value)} className="w-full px-3 py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-800" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold text-stone-600 mb-1">{tr.notesLabel}</label>
          <textarea rows="3" value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border border-stone-200 text-xs text-stone-800" />
        </div>
        <button type="submit" className="w-full py-3 rounded-xl bg-[#0D9488] hover:bg-[#0F766E] text-white font-extrabold text-xs shadow-sm transition">
          {tr.requestAptBtn}
        </button>
      </form>

      <div className="lg:col-span-7 bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm space-y-4">
        <h3 className="text-lg font-extrabold text-stone-900">{tr.tabAppointments} ({appointments.length})</h3>
        <div className="space-y-3">
          {appointments.map((apt) => (
            <div key={apt.id} className="p-4 rounded-2xl border border-stone-200 bg-[#FFFDF9] space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-extrabold text-xs text-stone-900">{apt.id}</span>
                <span className="px-2.5 py-0.5 rounded-full bg-teal-100 text-teal-900 text-[11px] font-bold">{apt.patientName}</span>
                <span className="px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 text-[11px] font-bold">📅 {apt.date} • 🕒 {apt.time}</span>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${apt.status === "Cancelled" ? "bg-rose-100 text-rose-800" : "bg-emerald-100 text-emerald-800"}`}>{apt.status}</span>
              </div>
              <div className="text-xs font-extrabold text-stone-800">🏥 {apt.clinicName} ({apt.specialty})</div>
              <div className="text-xs text-stone-600">📝 {apt.notes}</div>
              {canManage && (
                <div className="pt-2 border-t border-stone-200 flex flex-wrap gap-2">
                  {editingId === apt.id ? (
                    <div className="w-full grid grid-cols-1 sm:grid-cols-4 gap-2">
                      <input type="date" value={editForm.date} onChange={(e) => setEditForm({ ...editForm, date: e.target.value })} className="px-2 py-1 rounded border text-xs" />
                      <input type="text" value={editForm.time} onChange={(e) => setEditForm({ ...editForm, time: e.target.value })} className="px-2 py-1 rounded border text-xs" />
                      <input type="text" value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} className="px-2 py-1 rounded border text-xs" />
                      <button onClick={async () => { await window.ArogyaAPI.updateAppointment(apt.id, editForm); setEditingId(null); await onRefresh(); }} className="px-3 py-1 rounded bg-emerald-600 text-white text-xs font-bold">{tr.saveBtn}</button>
                    </div>
                  ) : (
                    <>
                      <button onClick={() => { setEditingId(apt.id); setEditForm({ date: apt.date, time: apt.time, notes: apt.notes, status: apt.status }); }} className="px-3 py-1 rounded-full bg-amber-100 text-amber-900 text-xs font-bold">✏️ {tr.rescheduleBtn}</button>
                      <button onClick={async () => { await window.ArogyaAPI.updateAppointment(apt.id, { ...apt, status: "Confirmed" }); await onRefresh(); }} className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 text-xs font-bold">✔ {tr.confirmBtn}</button>
                      <button onClick={async () => { await window.ArogyaAPI.updateAppointment(apt.id, { ...apt, status: "Cancelled" }); await onRefresh(); }} className="px-3 py-1 rounded-full bg-rose-100 text-rose-800 text-xs font-bold">✖ {tr.cancelAptBtn}</button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
'''

NEARBY_LOCATOR_JSX = r'''window.NearbyLocator = function ({ lang, mode, onBookVisitHere }) {
  const { useState, useEffect, useRef } = React;
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;

  const [areaName, setAreaName] = useState(tr.currentAreaDefault);
  const [searchInput, setSearchInput] = useState("");
  const [coords, setCoords] = useState({ lat: 12.9716, lng: 77.5946 });
  const [items, setItems] = useState([]);

  const mapBoxRef = useRef(null);
  const leafletRef = useRef(null);
  const layerRef = useRef(null);

  const buildDefaultCards = (area, lat, lng) => {
    if (mode === "doctors") {
      return [
        { id: "d1", title: `${area} Skin & Dermatology Specialist Centre`, distance: "1.1 km", subtitle: "Dermatology Clinic • Dermatology & Skin Care", address: `Main Arterial Road, ${area}`, phone: "+91-80-22221104", lat: lat + 0.006, lng: lng + 0.005 },
        { id: "d2", title: `${area} District General Hospital (Dermatology OPD)`, distance: "1.8 km", subtitle: "Government Hospital • Dermatology & General Medicine", address: `Hospital Road, ${area}`, phone: "104", lat: lat - 0.006, lng: lng + 0.007 }
      ];
    }
    return [
      { id: "p1", title: `Pradhan Mantri Janaushadhi Kendra — ${area}`, distance: "0.8 km", subtitle: "Jan Aushadhi Pharmacy • Affordable Generic Skin Creams, Antifungals & Medicines", address: `Near Main Market Circle, ${area}`, phone: "1800-180-8080", lat: lat + 0.004, lng: lng - 0.005 },
      { id: "p2", title: `${area} 24x7 Care & Wellness Pharmacy`, distance: "1.3 km", subtitle: "Medical Store • Dermatological Ointments, Lotions & Prescriptions", address: `Station Road, ${area}`, phone: "+91-80-22225566", lat: lat - 0.005, lng: lng - 0.004 }
    ];
  };

  useEffect(() => { setItems(buildDefaultCards(areaName, coords.lat, coords.lng)); }, [mode, areaName, coords]);

  useEffect(() => {
    if (!mapBoxRef.current || typeof L === "undefined") return;
    if (!leafletRef.current) {
      leafletRef.current = L.map(mapBoxRef.current).setView([coords.lat, coords.lng], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap Live GPS" }).addTo(leafletRef.current);
      layerRef.current = L.layerGroup().addTo(leafletRef.current);
    } else {
      leafletRef.current.setView([coords.lat, coords.lng], 13);
    }
    if (layerRef.current) {
      layerRef.current.clearLayers();
      items.forEach((it) => L.marker([it.lat, it.lng]).addTo(layerRef.current).bindPopup(`<b>${it.title}</b><br/>${it.subtitle}<br/>📞 ${it.phone}`));
    }
  }, [coords, items, mode]);

  const useLiveGps = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude, longitude } = pos.coords;
      let detected = tr.currentAreaDefault;
      try {
        const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`);
        const d = await r.json();
        detected = d.address?.city || d.address?.town || d.address?.suburb || d.address?.county || detected;
      } catch (e) {}
      setAreaName(detected);
      setCoords({ lat: latitude, lng: longitude });
    });
  };

  const searchCityOrPin = async (e) => {
    e.preventDefault();
    if (!searchInput.trim()) return;
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchInput)}&limit=1`);
      const arr = await r.json();
      if (arr && arr.length > 0) {
        setAreaName(arr[0].display_name.split(",")[0]);
        setCoords({ lat: parseFloat(arr[0].lat), lng: parseFloat(arr[0].lon) });
      } else {
        setAreaName(searchInput.trim());
      }
    } catch (e) {
      setAreaName(searchInput.trim());
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 mt-5 space-y-5">
      <div className="bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-extrabold text-stone-900">
              {mode === "doctors" ? tr.nearbyDoctorsTitle : tr.nearbyPharmaciesTitle} — <span className="text-[#0D9488]">{areaName}</span>
            </h2>
            <p className="text-xs text-stone-500">{tr.locatorSubtitle}</p>
          </div>
          <button onClick={useLiveGps} className="px-4 py-2 rounded-full bg-[#0D9488] hover:bg-[#0F766E] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm">
            <span>📍</span> {tr.useGpsBtn}
          </button>
        </div>
        <form onSubmit={searchCityOrPin} className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder={tr.searchPlaceholder} className="md:col-span-8 px-4 py-2.5 rounded-full border border-stone-200 text-xs text-stone-800" />
          <button type="submit" className="md:col-span-4 py-2.5 rounded-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-extrabold flex items-center justify-center gap-1.5 shadow-sm">
            <span>🔍</span> {tr.searchCityBtn}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-3xl border border-amber-200/90 p-5 shadow-sm space-y-2.5">
        <div className="flex items-center justify-between text-[11px] font-bold text-stone-600 px-1">
          <span>🗺️ {tr.mapHeader}</span>
          <span>© OpenStreetMap Live GPS</span>
        </div>
        <div ref={mapBoxRef} className="w-full h-64 rounded-2xl bg-stone-100 border border-stone-200" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {items.map((item) => (
          <div key={item.id} className="bg-white rounded-3xl border border-amber-200/90 p-6 shadow-sm space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-extrabold text-stone-900">{item.title}</h3>
              <span className="px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 text-[11px] font-extrabold shrink-0">{item.distance}</span>
            </div>
            <div className="text-xs font-bold text-[#0D9488]">{item.subtitle}</div>
            <div className="text-xs text-stone-600">📍 {item.address}</div>
            <div className="text-xs font-bold text-stone-800">📞 <a href={`tel:${item.phone}`} className="text-[#0D9488] underline">{item.phone}</a></div>
            <div className="pt-2 border-t border-stone-100 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <a href={`tel:${item.phone}`} className="px-3.5 py-1.5 rounded-full bg-[#0D9488] hover:bg-[#0F766E] text-white text-xs font-bold flex items-center gap-1"><span>📞</span> {tr.callFacilityBtn}</a>
                <a href={`https://www.openstreetmap.org/?mlat=${item.lat}&mlon=${item.lng}#map=15/${item.lat}/${item.lng}`} target="_blank" rel="noreferrer" className="px-3.5 py-1.5 rounded-full bg-[#292524] hover:bg-stone-800 text-white text-xs font-bold flex items-center gap-1"><span>🧭</span> {tr.openRouteBtn}</a>
              </div>
              {mode === "doctors" && (
                <button onClick={() => onBookVisitHere(item.title)} className="px-3.5 py-1.5 rounded-full bg-[#FFF9EB] hover:bg-amber-100 border border-amber-300 text-amber-950 text-xs font-extrabold">
                  {tr.bookVisitHereBtn}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
'''

ROLE_PORTALS_JSX = r'''window.RolePortals = function ({ mode, users, referrals, currentUser, onRefresh }) {
  const { useState } = React;
  const [refForm, setRefForm] = useState({
    patientName: "",
    condition: "",
    urgency: "HIGH — Immediate Dermatologist Consult",
    hospital: "District General Hospital (Dermatology OPD)"
  });

  if (mode === "referrals") {
    return (
      <div className="max-w-6xl mx-auto px-4 mt-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!refForm.patientName.trim()) return;
            await window.ArogyaAPI.createReferral({ ...refForm, referredBy: currentUser ? currentUser.fullName : "Healthcare Worker" });
            setRefForm({ patientName: "", condition: "", urgency: "HIGH — Immediate Dermatologist Consult", hospital: "District General Hospital (Dermatology OPD)" });
            await onRefresh();
          }}
          className="lg:col-span-5 bg-white rounded-3xl border border-amber-200 p-6 shadow-sm space-y-3"
        >
          <h3 className="text-lg font-extrabold text-stone-900">🧭 Create Specialist Referral</h3>
          <input type="text" required placeholder="Patient Full Name" value={refForm.patientName} onChange={(e) => setRefForm({ ...refForm, patientName: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs font-bold" />
          <input type="text" required placeholder="Identified Skin Condition" value={refForm.condition} onChange={(e) => setRefForm({ ...refForm, condition: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs font-bold" />
          <input type="text" required placeholder="Receiving Hospital" value={refForm.hospital} onChange={(e) => setRefForm({ ...refForm, hospital: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs font-bold" />
          <button className="w-full py-2.5 rounded-xl bg-[#F97316] text-white text-xs font-extrabold">Issue Hospital Referral</button>
        </form>

        <div className="lg:col-span-7 bg-white rounded-3xl border border-amber-200 p-6 shadow-sm space-y-3">
          <h3 className="text-lg font-extrabold text-stone-900">Active Hospital Referrals ({referrals.length})</h3>
          {referrals.map((r) => (
            <div key={r.id} className="p-4 rounded-2xl border bg-[#FFFDF9] flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-stone-500">{r.id} • Referred by {r.referredBy}</span>
                <h4 className="font-extrabold text-stone-900">{r.patientName} — {r.condition}</h4>
                <p className="text-xs text-stone-600">🏥 {r.hospital} | Urgency: {r.urgency}</p>
              </div>
              <button onClick={async () => { await window.ArogyaAPI.deleteReferral(r.id); await onRefresh(); }} className="px-3 py-1 rounded-full bg-rose-100 text-rose-800 text-xs font-bold">Remove</button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 mt-5">
      <div className="bg-white rounded-3xl border border-amber-200 p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-extrabold text-stone-900">🛡️ Admin Control — Manage & Remove Users and Workers</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#FFF9EB] border-b border-amber-200 text-stone-600 uppercase text-[10px] font-extrabold">
                <th className="py-3 px-3">Username</th>
                <th className="py-3 px-3">Full Name</th>
                <th className="py-3 px-3">Designation Role</th>
                <th className="py-3 px-3">Phone & Locality</th>
                <th className="py-3 px-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-stone-100">
                  <td className="py-3 px-3 font-extrabold">{u.username}</td>
                  <td className="py-3 px-3">{u.fullName}</td>
                  <td className="py-3 px-3">
                    <select value={u.role} onChange={async (e) => { await window.ArogyaAPI.updateUser(u.id, { role: e.target.value }); await onRefresh(); }} className="px-2.5 py-1 rounded-lg border bg-stone-50 font-bold">
                      <option value="user">user</option>
                      <option value="worker">worker</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="py-3 px-3">{u.phone} • {u.locality}</td>
                  <td className="py-3 px-3">
                    {currentUser && u.id !== currentUser.id ? (
                      <button onClick={async () => { await window.ArogyaAPI.deleteUser(u.id); await onRefresh(); }} className="px-3 py-1 rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold">
                        🗑️ Remove {u.role === "worker" ? "Worker" : "User"}
                      </button>
                    ) : <span className="text-stone-400 font-bold">Active Admin</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
'''

AUTH_MODALS_JSX = r'''window.AuthAndProfileModals = function ({
  showAuthModal, setShowAuthModal, authMode, setAuthMode,
  currentUser, setCurrentUser, showProfileModal, setShowProfileModal, lang, onSuccessRefresh
}) {
  const { useState, useEffect } = React;
  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;

  const [form, setForm] = useState({ fullName: "", username: "", password: "", phone: "", locality: "", regCode: "" });
  const [error, setError] = useState("");
  const [profileForm, setProfileForm] = useState({ fullName: "", phone: "", locality: "", password: "" });

  useEffect(() => {
    if (currentUser) {
      setProfileForm({ fullName: currentUser.fullName || "", phone: currentUser.phone || "", locality: currentUser.locality || "", password: "" });
    }
  }, [currentUser, showProfileModal]);

  const submitAuth = async (e) => {
    e.preventDefault();
    setError("");
    const resp = authMode === "login"
      ? await window.ArogyaAPI.login({ username: form.username, password: form.password })
      : await window.ArogyaAPI.register({ ...form, lang });
    if (!resp.ok) {
      setError(resp.data.error || "Invalid credentials");
      return;
    }
    setCurrentUser(resp.data.user);
    setShowAuthModal(false);
    setForm({ fullName: "", username: "", password: "", phone: "", locality: "", regCode: "" });
    await onSuccessRefresh();
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    const res = await window.ArogyaAPI.updateUser(currentUser.id, { ...profileForm, lang });
    if (res && res.user) {
      setCurrentUser(res.user);
      setShowProfileModal(false);
      await onSuccessRefresh();
    }
  };

  return (
    <>
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full overflow-hidden border border-amber-200 shadow-2xl">
            <div className="bg-gradient-to-r from-[#F59E0B] via-[#F97316] to-[#F43F5E] p-6 text-white flex items-start justify-between">
              <div className="flex items-center gap-3.5">
                <div className="w-11 h-11 rounded-2xl bg-white/20 flex items-center justify-center text-xl">👤</div>
                <div>
                  <h3 className="text-lg font-extrabold leading-snug">{authMode === "login" ? tr.signInModalTitle : tr.createProfileModalTitle}</h3>
                  <p className="text-[11px] text-white/90 mt-0.5">{tr.authModalSub}</p>
                </div>
              </div>
              <button onClick={() => setShowAuthModal(false)} className="text-white/80 hover:text-white text-lg font-bold">✕</button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 bg-[#FFFBEB] p-1 rounded-2xl border border-amber-200">
                <button type="button" onClick={() => { setAuthMode("login"); setError(""); }} className={`py-2 rounded-xl text-xs font-extrabold transition ${authMode === "login" ? "bg-white text-amber-950 shadow-sm" : "text-stone-600"}`}>{tr.signInBtn}</button>
                <button type="button" onClick={() => { setAuthMode("register"); setError(""); }} className={`py-2 rounded-xl text-xs font-extrabold transition ${authMode === "register" ? "bg-white text-amber-950 shadow-sm" : "text-stone-600"}`}>{tr.createAccountBtn}</button>
              </div>
              {error && <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold">{error}</div>}
              <form onSubmit={submitAuth} className="space-y-3">
                {authMode === "register" && (
                  <div>
                    <label className="block text-xs font-bold text-stone-700 mb-1">{tr.fullNameLabel}</label>
                    <input type="text" required value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                  </div>
                )}
                <div>
                  <label className="block text-xs font-bold text-stone-700 mb-1">{tr.usernameLabel}</label>
                  <input type="text" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-stone-700 mb-1">{tr.passwordLabel}</label>
                  <input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                </div>
                {authMode === "register" && (
                  <>
                    <div>
                      <label className="block text-xs font-bold text-stone-700 mb-1">{tr.phoneLabel}</label>
                      <input type="text" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-stone-700 mb-1">{tr.localityLabel}</label>
                      <input type="text" value={form.locality} onChange={(e) => setForm({ ...form, locality: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-stone-700 mb-1">{tr.staffCodeLabel}</label>
                      <input type="text" value={form.regCode} onChange={(e) => setForm({ ...form, regCode: e.target.value })} className="w-full px-3.5 py-2.5 rounded-xl border border-stone-200 text-xs" />
                    </div>
                  </>
                )}
                <button type="submit" className="w-full py-3 rounded-xl bg-gradient-to-r from-[#F59E0B] to-[#F97316] text-white font-extrabold text-xs shadow-md transition mt-2">
                  {authMode === "login" ? tr.signInBtn : tr.createAccountBtn}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {showProfileModal && currentUser && (
        <div className="fixed inset-0 z-50 bg-stone-900/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full overflow-hidden border border-amber-200 shadow-2xl">
            <div className="bg-gradient-to-r from-[#F59E0B] via-[#F97316] to-[#F43F5E] p-6 text-white flex items-center justify-between">
              <div>
                <h3 className="text-lg font-extrabold">{tr.manageProfileBtn}</h3>
                <p className="text-xs text-white/90">{currentUser.username} ({currentUser.role.toUpperCase()})</p>
              </div>
              <button onClick={() => setShowProfileModal(false)} className="text-white font-bold">✕</button>
            </div>
            <form onSubmit={saveProfile} className="p-6 space-y-3">
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1">{tr.fullNameLabel}</label>
                <input type="text" value={profileForm.fullName} onChange={(e) => setProfileForm({ ...profileForm, fullName: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs" />
              </div>
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1">{tr.phoneLabel}</label>
                <input type="text" value={profileForm.phone} onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs" />
              </div>
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1">{tr.localityLabel}</label>
                <input type="text" value={profileForm.locality} onChange={(e) => setProfileForm({ ...profileForm, locality: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs" />
              </div>
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1">{tr.passwordLabel}</label>
                <input type="password" value={profileForm.password} onChange={(e) => setProfileForm({ ...profileForm, password: e.target.value })} className="w-full px-3.5 py-2 rounded-xl border text-xs" />
              </div>
              <div className="flex gap-2 pt-2">
                <button type="submit" className="flex-1 py-2.5 rounded-xl bg-[#0D9488] text-white font-extrabold text-xs">{tr.saveBtn}</button>
                <button type="button" onClick={() => { setCurrentUser(null); setShowProfileModal(false); }} className="px-4 py-2.5 rounded-xl bg-rose-600 text-white font-extrabold text-xs">{tr.signOutBtn}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
'''

APP_JSX = r'''function ArogyaSetuApp() {
  const { useState, useEffect, useRef } = React;
  const [db, setDb] = useState({ users: [], scans: [], appointments: [], referrals: [] });
  const [backendOnline, setBackendOnline] = useState(false);
  const [lang, setLang] = useState("en");
  const [activeTab, setActiveTab] = useState("lens");
  const [currentUser, setCurrentUser] = useState(null);
  const [prefilledClinic, setPrefilledClinic] = useState("");

  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [showProfileModal, setShowProfileModal] = useState(false);

  const [voiceState, setVoiceState] = useState("idle");
  const speechSessionRef = useRef(0);
  const audioRef = useRef(null);

  const refreshState = async () => {
    try {
      const data = await window.ArogyaAPI.getState();
      setDb(data);
      setBackendOnline(true);
    } catch (e) {
      setBackendOnline(false);
    }
  };

  useEffect(() => { refreshState(); }, []);

  const speakText = (rawText, customLang) => {
    const targetLang = customLang || lang;
    const sessionId = ++speechSessionRef.current;

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();

    const clean = (rawText || "").trim();
    if (!clean) {
      setVoiceState("idle");
      return;
    }

    setVoiceState("playing");
    const ttsUrl = `${window.API_BASE}/tts?lang=${encodeURIComponent(targetLang)}&text=${encodeURIComponent(clean)}`;
    const audio = new Audio(ttsUrl);
    audioRef.current = audio;

    audio.onplay = () => { if (speechSessionRef.current === sessionId) setVoiceState("playing"); };
    audio.onended = () => { if (speechSessionRef.current === sessionId) setVoiceState("idle"); };
    audio.onerror = () => {
      if (speechSessionRef.current !== sessionId) return;
      if (!("speechSynthesis" in window)) { setVoiceState("idle"); return; }
      const list = window.speechSynthesis.getVoices();
      const langObj = window.LANGUAGES.find((l) => l.code === targetLang) || window.LANGUAGES[0];
      const nativeVoice = list.find((v) => v.lang.toLowerCase().startsWith(targetLang));
      const hindiVoice = list.find((v) => v.lang.toLowerCase().startsWith("hi"));
      let spokenStr = clean, chosenVoice = nativeVoice, locale = langObj.locale;
      if (!nativeVoice && ["kn", "ta", "te", "ml"].includes(targetLang) && hindiVoice) {
        spokenStr = window.indicToDevanagariPhonetic(clean);
        chosenVoice = hindiVoice;
        locale = "hi-IN";
      }
      const utter = new SpeechSynthesisUtterance(spokenStr);
      if (chosenVoice) utter.voice = chosenVoice;
      utter.lang = locale;
      utter.rate = 0.95;
      utter.onend = () => { if (speechSessionRef.current === sessionId) setVoiceState("idle"); };
      utter.onerror = () => { if (speechSessionRef.current === sessionId) setVoiceState("idle"); };
      window.speechSynthesis.speak(utter);
    };

    audio.play().catch(() => { if (audio.onerror) audio.onerror(); });
  };

  const pauseVoice = () => {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
      setVoiceState("paused");
    } else if ("speechSynthesis" in window && window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
      setVoiceState("paused");
    }
  };

  const resumeVoice = () => {
    if (audioRef.current && audioRef.current.paused) {
      audioRef.current.play();
      setVoiceState("playing");
    } else if ("speechSynthesis" in window && window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setVoiceState("playing");
    }
  };

  const stopVoice = () => {
    speechSessionRef.current++;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setVoiceState("idle");
  };

  const tr = window.TRANSLATIONS[lang] || window.TRANSLATIONS.en;

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#FFFBF2] text-stone-900">
      <div>
        <window.HeaderAndNav
          lang={lang} setLang={setLang} activeTab={activeTab} setActiveTab={setActiveTab}
          currentUser={currentUser} backendOnline={backendOnline} voiceState={voiceState}
          speakText={speakText} pauseVoice={pauseVoice} resumeVoice={resumeVoice} stopVoice={stopVoice}
          openSignIn={() => { setAuthMode("login"); setShowAuthModal(true); }}
          openCreateAccount={() => { setAuthMode("register"); setShowAuthModal(true); }}
          openProfileModal={() => setShowProfileModal(true)}
        />
        <main className="pb-12">
          {activeTab === "lens" && (
            <window.SmartSkinLens
              lang={lang} currentUser={currentUser} speakText={speakText}
              onScanCompleted={refreshState}
              goToAppointments={() => setActiveTab("appointments")}
              goToDoctors={() => setActiveTab("doctors")}
            />
          )}
          {activeTab === "journal" && (
            <window.HomeAndJournal lang={lang} scans={db.scans} currentUser={currentUser} goToSkinLens={() => setActiveTab("lens")} />
          )}
          {activeTab === "appointments" && (
            <window.Appointments lang={lang} appointments={db.appointments} currentUser={currentUser} prefilledClinic={prefilledClinic} onRefresh={refreshState} />
          )}
          {activeTab === "doctors" && (
            <window.NearbyLocator lang={lang} mode="doctors" onBookVisitHere={(clinicTitle) => { setPrefilledClinic(clinicTitle); setActiveTab("appointments"); }} />
          )}
          {activeTab === "pharmacies" && (
            <window.NearbyLocator lang={lang} mode="pharmacies" onBookVisitHere={() => {}} />
          )}
          {activeTab === "referrals" && (
            <window.RolePortals lang={lang} mode="referrals" users={db.users} referrals={db.referrals} currentUser={currentUser} onRefresh={refreshState} />
          )}
          {activeTab === "admin" && (
            <window.RolePortals lang={lang} mode="admin" users={db.users} referrals={db.referrals} currentUser={currentUser} onRefresh={refreshState} />
          )}
        </main>
      </div>

      <window.AuthAndProfileModals
        showAuthModal={showAuthModal} setShowAuthModal={setShowAuthModal}
        authMode={authMode} setAuthMode={setAuthMode}
        currentUser={currentUser} setCurrentUser={setCurrentUser}
        showProfileModal={showProfileModal} setShowProfileModal={setShowProfileModal}
        lang={lang} onSuccessRefresh={refreshState}
      />

      <footer className="border-t border-amber-200/80 bg-[#FFFDF9] py-3.5 px-4">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-2 text-[11px] text-stone-500">
          <span><b className="text-stone-800">{tr.appName}</b> — {tr.appTagline}</span>
          <span>Instant Single-Voice 6-Language Assistant • {tr.tabLens} • Live GPS</span>
        </div>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<ArogyaSetuApp />);
'''


def sync_all_project_files():
    os.makedirs(BACKEND_APP_DIR, exist_ok=True)
    os.makedirs(FRONTEND_COMP_DIR, exist_ok=True)

    file_map = {
        os.path.join(BACKEND_APP_DIR, "database.py"): DATABASE_PY,
        os.path.join(BACKEND_APP_DIR, "ml_engine.py"): ML_ENGINE_PY,
        os.path.join(BACKEND_APP_DIR, "main.py"): MAIN_PY,
        os.path.join(FRONTEND_DIR, "index.html"): INDEX_HTML,
        os.path.join(FRONTEND_SRC_DIR, "api.js"): API_JS,
        os.path.join(FRONTEND_SRC_DIR, "voiceEngine.js"): VOICE_ENGINE_JS,
        os.path.join(FRONTEND_COMP_DIR, "HeaderAndNav.jsx"): HEADER_JSX,
        os.path.join(FRONTEND_COMP_DIR, "SmartSkinLens.jsx"): SMART_SKIN_LENS_JSX,
        os.path.join(FRONTEND_COMP_DIR, "HomeAndJournal.jsx"): HOME_JOURNAL_JSX,
        os.path.join(FRONTEND_COMP_DIR, "Appointments.jsx"): APPOINTMENTS_JSX,
        os.path.join(FRONTEND_COMP_DIR, "NearbyLocator.jsx"): NEARBY_LOCATOR_JSX,
        os.path.join(FRONTEND_COMP_DIR, "RolePortals.jsx"): ROLE_PORTALS_JSX,
        os.path.join(FRONTEND_COMP_DIR, "AuthAndProfileModals.jsx"): AUTH_MODALS_JSX,
        os.path.join(FRONTEND_SRC_DIR, "App.jsx"): APP_JSX,
    }

    for path, content in file_map.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class FrontendHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path).path
        if parsed_path == "/src/app_bundle.jsx":
            ordered_files = [
                os.path.join(FRONTEND_COMP_DIR, "HeaderAndNav.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "SmartSkinLens.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "HomeAndJournal.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "Appointments.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "NearbyLocator.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "RolePortals.jsx"),
                os.path.join(FRONTEND_COMP_DIR, "AuthAndProfileModals.jsx"),
                os.path.join(FRONTEND_SRC_DIR, "App.jsx"),
            ]
            combined = []
            for fp in ordered_files:
                if os.path.exists(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        combined.append(f.read())
            payload = ("\n\n".join(combined)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        return super().do_GET()

    def log_message(self, fmt, *args):
        pass


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.15)
    return False


if __name__ == "__main__":
    print("[1/3] Syncing separated Backend & Frontend architecture files...")
    sync_all_project_files()

    if BACKEND_APP_DIR not in sys.path:
        sys.path.insert(0, BACKEND_APP_DIR)

    import database
    import main as backend_main

    print("[2/3] Verifying SQLite Database (backend/arogya_setu.db)...")
    database.init_db()

    if not is_port_in_use(8000):
        threading.Thread(
            target=lambda: ReusableThreadingHTTPServer(("127.0.0.1", 8000), backend_main.ArogyaAPIHandler).serve_forever(),
            daemon=True,
        ).start()

    if not is_port_in_use(5173):
        handler = partial(FrontendHandler, directory=FRONTEND_DIR)
        threading.Thread(
            target=lambda: ReusableThreadingHTTPServer(("127.0.0.1", 5173), handler).serve_forever(),
            daemon=True,
        ).start()

    if wait_for_port(8000) and wait_for_port(5173):
        print("\n========================================================")
        print(" Arogya Setu Full-Stack Auto-Localhost Active!")
        print(" -> Frontend UI : http://127.0.0.1:5173")
        print(" -> Backend API : http://127.0.0.1:8000/api/v1/health")
        print(" -> Neural TTS  : http://127.0.0.1:8000/api/v1/tts")
        print("========================================================\n")
        webbrowser.open("http://127.0.0.1:5173")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
import json
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

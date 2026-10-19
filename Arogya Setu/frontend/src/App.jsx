function ArogyaSetuApp() {
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

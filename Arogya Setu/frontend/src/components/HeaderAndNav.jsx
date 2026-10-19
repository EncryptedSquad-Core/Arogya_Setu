window.HeaderAndNav = function ({
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

window.HomeAndJournal = function ({ lang, scans, currentUser, goToSkinLens }) {
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

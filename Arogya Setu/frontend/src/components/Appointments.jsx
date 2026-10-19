window.Appointments = function ({ lang, appointments, currentUser, prefilledClinic, onRefresh }) {
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

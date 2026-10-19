window.RolePortals = function ({ mode, users, referrals, currentUser, onRefresh }) {
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

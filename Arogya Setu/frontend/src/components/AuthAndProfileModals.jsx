window.AuthAndProfileModals = function ({
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

window.SmartSkinLens = function ({
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

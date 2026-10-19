window.NearbyLocator = function ({ lang, mode, onBookVisitHere }) {
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

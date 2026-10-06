"use client";
/**
 * HR Yönetici Paneli
 * - İzin Takibi       : tüm çalışan izin talepleri
 * - Oryantasyon Takip : quiz sonuçları, bekleyen çalışanlar, mesajlaşma
 * - Kutlamalar        : bugünkü doğum günleri & yıldönümleri + bildirim gönder
 */
import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { fetchAllRequests, fetchEmployees, EmployeeListItem } from "@/lib/api";
import { LeaveRequest, IzinDurum } from "@/types/leave";
import LeaveStatusBadge from "@/components/inpulse/LeaveStatusBadge";
import { getCurrentUser } from "@/lib/auth";
import { useRouter } from "next/navigation";

const DURUM_OPTIONS = ["", "beklemede", "onaylandi", "reddedildi", "iptal"];
const DURUM_LABELS: Record<string, string> = {
  "": "Tümü", beklemede: "Beklemede", onaylandi: "Onaylandı",
  reddedildi: "Reddedildi", iptal: "İptal",
};

const IZIN_TURU_LABELS: Record<string, string> = {
  yillik:       "📅 Yıllık İzin",
  evlilik:      "💍 Evlilik İzni",
  olum:         "🕊️ Ölüm İzni",
  baba_dogum:   "👶 Babalık İzni",
  dogum_kadin:  "🤱 Doğum İzni",
  hastalik:     "🏥 Hastalık İzni",
  ucretsiz:     "📋 Ücretsiz İzin",
  "2saat":      "⏱️ 2 Saat İzin",
  "2saat_uzeri":"⏰ Mazeret İzni",
  idari:        "🏛️ İdari İzin",
};

// ─── Tipler ───────────────────────────────────────────────────────────────────

interface OrientationResult {
  id: string;
  employee_id: string;
  ad_soyad: string;
  dogru_sayisi: number;
  toplam_soru: number;
  puan: number;
  tamamlama_tarihi: string;
}

interface OrientationMessage {
  id: string;
  employee_id: string;
  gonderen_id: string;
  gonderen_rol: string;
  mesaj: string;
  okundu: boolean;
  olusturma: string;
}

interface Celebration {
  employee_id: string;
  ad_soyad: string;
  sube: string;
  tur: "dogum_gunu" | "yil_donumu";
  tarih: string;
  kac_gun_sonra: number;
  kac_yil: number | null;
}

// ─── Oryantasyon Takip Sekmesi ────────────────────────────────────────────────

function OrientationTab({ hrId }: { hrId: string }) {
  const [results, setResults] = useState<OrientationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmp, setSelectedEmp] = useState<string | null>(null);
  const [messages, setMessages] = useState<OrientationMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [yeniMesaj, setYeniMesaj] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchResults = useCallback(() => {
    fetch("/api/v1/hr/orientation/results")
      .then((r) => r.json())
      .then((d) => setResults(Array.isArray(d) ? d : []))
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchResults();
    const id = setInterval(fetchResults, 30_000);
    return () => clearInterval(id);
  }, [fetchResults]);

  useEffect(() => {
    if (!selectedEmp) return;
    setMsgLoading(true);
    const load = () =>
      fetch(`/api/v1/hr/orientation/messages/${selectedEmp}`)
        .then((r) => r.json())
        .then((d) => setMessages(Array.isArray(d) ? d : []))
        .catch(() => {})
        .finally(() => setMsgLoading(false));
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [selectedEmp]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!yeniMesaj.trim() || !selectedEmp) return;
    setSending(true);
    try {
      const r = await fetch("/api/v1/hr/orientation/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: selectedEmp,
          gonderen_id: hrId,
          gonderen_rol: "ik",
          mesaj: yeniMesaj.trim(),
        }),
      });
      if (r.ok) {
        const msg = await r.json();
        setMessages((p) => [...p, msg]);
        setYeniMesaj("");
      }
    } finally {
      setSending(false);
    }
  }

  const scoreColor = (p: number) =>
    p >= 80 ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : p >= 60 ? "text-amber-700 bg-amber-50 border-amber-200"
      : "text-red-700 bg-red-50 border-red-200";

  const selectedResult = results.find((r) => r.employee_id === selectedEmp);

  // Demo: bekleyen yeni çalışanlar (gerçekte bir endpoint'ten alınabilir)
  const BEKLEYEN = [
    { id: "demo-employee-ayse", ad_soyad: "Ayşe Aydın", sube: "Yazılım Geliştirme", ise_giris: "2026-10-05" },
  ].filter((b) => !results.find((r) => r.employee_id === b.id));

  return (
    <div className="space-y-6">
      {/* ── Bekleyen Çalışanlar ───────────────────────────────────────── */}
      {BEKLEYEN.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
          <h3 className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            Oryantasyon Bekleyen Çalışanlar
          </h3>
          <div className="space-y-2">
            {BEKLEYEN.map((b) => (
              <div key={b.id}
                className="flex items-center gap-3 bg-white rounded-xl border border-amber-200 px-4 py-3">
                <div className="w-9 h-9 bg-amber-500 rounded-full flex items-center justify-center
                                text-white text-xs font-bold flex-shrink-0">
                  {b.ad_soyad.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-gray-900">{b.ad_soyad}</p>
                  <p className="text-xs text-gray-500">{b.sube} · İşe giriş: {new Date(b.ise_giris).toLocaleDateString("tr-TR")}</p>
                </div>
                <span className="text-xs font-medium text-amber-600 bg-amber-100 px-2 py-1 rounded-lg">
                  ⏳ Bekleniyor
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Quiz Sonuçları + Mesajlaşma ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Sol: Sonuç listesi */}
        <div className="lg:col-span-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Tamamlanan Quiz Sonuçları
          </h3>
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : results.length === 0 ? (
            <div className="bg-white rounded-xl border border-dashed border-gray-200 p-8 text-center">
              <p className="text-3xl mb-2">🎓</p>
              <p className="text-gray-400 text-sm">Henüz tamamlanan oryantasyon yok.</p>
              <p className="text-gray-300 text-xs mt-1">Yeni çalışan quizi tamamladığında burada görünecek.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {results.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setSelectedEmp(r.employee_id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-all
                    ${selectedEmp === r.employee_id
                      ? "border-blue-400 bg-blue-50"
                      : "border-gray-100 bg-white hover:border-blue-200 hover:bg-blue-50"}`}
                >
                  <div className="w-9 h-9 bg-blue-600 rounded-full flex items-center justify-center
                                  text-white text-xs font-bold flex-shrink-0">
                    {r.ad_soyad.split(" ").map((n: string) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{r.ad_soyad}</p>
                    <p className="text-xs text-gray-400">
                      {new Date(r.tamamlama_tarihi).toLocaleDateString("tr-TR")}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-lg border ${scoreColor(r.puan)}`}>
                      {r.puan}/100
                    </span>
                    <span className="text-[10px] text-gray-400">
                      {r.dogru_sayisi}/{r.toplam_soru} doğru
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Sağ: Mesajlaşma */}
        <div className="lg:col-span-3">
          {!selectedEmp ? (
            <div className="bg-white rounded-xl border border-dashed border-gray-200 h-72
                            flex flex-col items-center justify-center gap-2">
              <p className="text-2xl">💬</p>
              <p className="text-gray-400 text-sm text-center px-6">
                Çalışanla mesajlaşmak için<br />sol taraftan bir sonuç seçin
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-100 flex flex-col" style={{ height: "420px" }}>
              <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center
                                text-white text-xs font-bold">
                  {selectedResult?.ad_soyad.split(" ").map((n: string) => n[0]).join("").slice(0, 2)}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{selectedResult?.ad_soyad}</p>
                  <p className="text-xs text-gray-400">Oryantasyon Süreci İletişimi</p>
                </div>
                {selectedResult && (
                  <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded-lg border
                    ${scoreColor(selectedResult.puan)}`}>
                    Quiz: {selectedResult.puan}/100
                  </span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {msgLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <p className="text-2xl mb-2">💬</p>
                      <p className="text-xs text-gray-400">Henüz mesaj yok. İlk mesajı siz gönderin.</p>
                    </div>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const benimMi = msg.gonderen_rol === "ik";
                    return (
                      <div key={msg.id} className={`flex ${benimMi ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm
                          ${benimMi
                            ? "bg-blue-600 text-white rounded-br-sm"
                            : "bg-gray-100 text-gray-800 rounded-bl-sm"}`}>
                          <p>{msg.mesaj}</p>
                          <p className={`text-[10px] mt-1 ${benimMi ? "text-blue-200" : "text-gray-400"}`}>
                            {new Date(msg.olusturma).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                            {benimMi ? " · İK" : " · Çalışan"}
                          </p>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="px-4 py-3 border-t border-gray-100 flex gap-2">
                <input
                  type="text"
                  value={yeniMesaj}
                  onChange={(e) => setYeniMesaj(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Mesaj yazın…"
                  className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
                <button
                  onClick={handleSend}
                  disabled={!yeniMesaj.trim() || sending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm
                             font-medium transition-colors disabled:opacity-40"
                >
                  {sending ? "…" : "Gönder"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Kutlamalar Sekmesi ───────────────────────────────────────────────────────

function CelebrationsTab() {
  const [items, setItems] = useState<Celebration[]>([]);
  const [loading, setLoading] = useState(true);
  const [notifying, setNotifying] = useState(false);
  const [notifResult, setNotifResult] = useState<{ gonderilen_sayisi: number } | null>(null);

  useEffect(() => {
    fetch("/api/v1/hr/celebrations/today?gun_aralik=14")
      .then((r) => r.json())
      .then((d) => setItems(Array.isArray(d) ? d : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleNotify() {
    setNotifying(true);
    setNotifResult(null);
    try {
      const r = await fetch("/api/v1/hr/celebrations/notify", { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        setNotifResult(data);
      }
    } catch {
      // sessiz hata
    } finally {
      setNotifying(false);
    }
  }

  const bugun = items.filter((i) => i.kac_gun_sonra === 0);
  const yaklasan = items.filter((i) => i.kac_gun_sonra > 0);

  const kutlamaCard = (item: Celebration) => {
    const isDogum = item.tur === "dogum_gunu";
    return (
      <div key={`${item.employee_id}-${item.tur}`}
        className={`flex items-center gap-4 p-4 rounded-2xl border
          ${isDogum
            ? "bg-purple-50 border-purple-200"
            : "bg-emerald-50 border-emerald-200"}`}
      >
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-2xl flex-shrink-0
          ${isDogum ? "bg-purple-100" : "bg-emerald-100"}`}>
          {isDogum ? "🎂" : "🏆"}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 text-sm">{item.ad_soyad}</p>
          <p className={`text-xs font-medium mt-0.5 ${isDogum ? "text-purple-700" : "text-emerald-700"}`}>
            {isDogum
              ? "Doğum Günü 🎉"
              : `${item.kac_yil}. İş Yılı 🌟`}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{item.sube}</p>
        </div>
        <div className="text-right flex-shrink-0 flex flex-col items-end gap-2">
          {item.kac_gun_sonra === 0 ? (
            <span className="inline-block text-xs font-bold text-white bg-gradient-to-r
              from-purple-500 to-pink-500 px-3 py-1 rounded-full">
              Bugün! 🎊
            </span>
          ) : (
            <span className="text-xs text-gray-400 font-medium">
              {item.kac_gun_sonra} gün sonra
            </span>
          )}
          <a
            href={`/inpulse/profile/${item.employee_id}`}
            className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors
              ${isDogum
                ? "text-purple-700 bg-purple-100 hover:bg-purple-200"
                : "text-emerald-700 bg-emerald-100 hover:bg-emerald-200"}`}
          >
            Profili Gör →
          </a>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Bildirim gönder butonu */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-100 p-5
                      flex items-center justify-between gap-4">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Kutlama Bildirimleri</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Bugün doğum günü veya iş yıldönümü olan çalışanlara platform bildirimi ve e-posta gönder.
            Her sabah 09:00&apos;da otomatik çalışır.
          </p>
        </div>
        <button
          onClick={handleNotify}
          disabled={notifying}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm
                     font-semibold transition-colors whitespace-nowrap disabled:opacity-50 flex items-center gap-2"
        >
          {notifying ? (
            <>
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Gönderiliyor…
            </>
          ) : "📨 Şimdi Gönder"}
        </button>
      </div>

      {notifResult && (
        <div className={`rounded-xl border px-4 py-3 text-sm font-medium
          ${notifResult.gonderilen_sayisi > 0
            ? "bg-emerald-50 border-emerald-200 text-emerald-700"
            : "bg-gray-50 border-gray-200 text-gray-600"}`}>
          {notifResult.gonderilen_sayisi > 0
            ? `✅ ${notifResult.gonderilen_sayisi} kişiye kutlama bildirimi ve e-posta gönderildi!`
            : "ℹ️ Bugün kutlanacak kimse yok."}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-200 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-gray-200 p-12 text-center">
          <p className="text-4xl mb-3">🎈</p>
          <p className="text-gray-500 font-medium text-sm">Önümüzdeki 14 günde kutlama yok</p>
          <p className="text-gray-300 text-xs mt-1">Doğum günleri ve yıldönümleri burada görünecek</p>
        </div>
      ) : (
        <>
          {bugun.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <span className="w-2 h-2 bg-pink-400 rounded-full animate-pulse" />
                Bugün
              </h3>
              <div className="space-y-2">{bugun.map(kutlamaCard)}</div>
            </div>
          )}
          {yaklasan.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Yaklaşan (14 gün)
              </h3>
              <div className="space-y-2">{yaklasan.map(kutlamaCard)}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Ana Sayfa ────────────────────────────────────────────────────────────────

export default function HRPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getCurrentUser>>(null);
  const [tab, setTab] = useState<"izin" | "oryantasyon" | "kutlamalar">("izin");
  const [talepler, setTalepler] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [durumFilter, setDurumFilter] = useState("");
  const [yilFilter] = useState(2026);
  // Çalışan adı map: id → ad_soyad
  const [empMap, setEmpMap] = useState<Record<string, string>>({});

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (u.role !== "ik") { router.replace("/inpulse"); return; }
    setUser(u);
  }, [router]);

  // Çalışan listesini bir kere yükle
  useEffect(() => {
    fetchEmployees().then((list: EmployeeListItem[]) => {
      const map: Record<string, string> = {};
      list.forEach((e) => { map[e.id] = e.ad_soyad; });
      setEmpMap(map);
    });
  }, []);

  const loadTalepler = useCallback(() => {
    setLoading(true);
    fetchAllRequests(durumFilter || undefined, yilFilter)
      .then(setTalepler)
      .finally(() => setLoading(false));
  }, [durumFilter, yilFilter]);

  useEffect(() => {
    if (tab !== "izin") return;
    loadTalepler();
    // 30 saniyede bir otomatik yenile — yönetici kararları anında yansısın
    const iv = setInterval(loadTalepler, 30_000);
    return () => clearInterval(iv);
  }, [tab, loadTalepler]);

  if (!user) return null;

  const TABS = [
    { key: "izin",        label: "📋 İzin Takibi" },
    { key: "oryantasyon", label: "🎓 Oryantasyon Takip" },
    { key: "kutlamalar",  label: "🎂 Kutlamalar" },
  ] as const;

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-4">
          <Link href="/inpulse" className="text-gray-400 hover:text-gray-600 text-sm">← Geri</Link>
          <div>
            <h1 className="font-semibold text-gray-900">HR Paneli</h1>
            <p className="text-xs text-gray-500">{yilFilter} — İnsan Kaynakları Yönetimi</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="w-7 h-7 bg-emerald-700 rounded-full flex items-center justify-center
                            text-white text-xs font-bold">
              {user.avatar}
            </div>
            <span className="text-sm text-gray-700 font-medium">{user.name}</span>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Sekmeler */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6 w-fit">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === t.key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ─── İzin Takibi ────────────────────────────────────────────────── */}
        {tab === "izin" && (
          <>
            <div className="flex gap-2 flex-wrap mb-5">
              {DURUM_OPTIONS.map((d) => (
                <button
                  key={d}
                  onClick={() => setDurumFilter(d)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
                    ${durumFilter === d
                      ? "bg-blue-600 text-white"
                      : "bg-white border border-gray-300 text-gray-600 hover:bg-gray-50"}`}
                >
                  {DURUM_LABELS[d]}
                </button>
              ))}
            </div>

            {loading ? (
              <div className="bg-gray-200 h-64 rounded-xl animate-pulse" />
            ) : talepler.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
                <p className="text-gray-500 text-sm">Bu filtreye uygun talep bulunamadı.</p>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Çalışan</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">İzin Türü</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Tarihler</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Süre</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Durum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {talepler.map((talep) => (
                      <tr key={talep.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <p className="text-gray-800 font-semibold text-sm">
                            {empMap[talep.employee_id] ?? talep.employee_id}
                          </p>
                          {talep.neden && (
                            <p className="text-xs text-gray-400 italic mt-0.5 truncate max-w-[160px]">
                              &ldquo;{talep.neden}&rdquo;
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-sm">
                          {IZIN_TURU_LABELS[talep.izin_turu] ?? talep.izin_turu.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                          {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")}
                          <span className="mx-1 text-gray-300">→</span>
                          {new Date(talep.giris_tarihi).toLocaleDateString("tr-TR")}
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-sm font-medium">
                          {talep.sure_gun} gün
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-1">
                            <LeaveStatusBadge durum={talep.durum as IzinDurum} />
                            {talep.ret_nedeni && (
                              <p className="text-[10px] text-red-500 leading-tight max-w-[140px] truncate">
                                {talep.ret_nedeni}
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ─── Oryantasyon Takip ────────────────────────────────────────── */}
        {tab === "oryantasyon" && <OrientationTab hrId={user.id} />}

        {/* ─── Kutlamalar ───────────────────────────────────────────────── */}
        {tab === "kutlamalar" && <CelebrationsTab />}
      </div>
    </main>
  );
}

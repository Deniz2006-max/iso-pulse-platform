"use client";
/**
 * Outpulse — Mevzuat Radar Sayfası
 * Resmi Gazete, SGK, ÇSGB kaynaklı mevzuat güncellemelerini listeler.
 * Arama, kategori filtresi, kaynak filtresi.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const RADAR_BASE = `${API}/api/v1/radar`;

interface MevzuatItem {
  id: string;
  kaynak: string;
  baslik: string;
  url: string | null;
  ozet: string | null;
  kategori: string | null;
  yayin_tarihi: string | null;
}

const KATEGORI_LABELS: Record<string, string> = {
  ik: "İnsan Kaynakları",
  mali: "Mali & Finans",
  hukuk: "Hukuki",
};

const KAYNAK_LABELS: Record<string, string> = {
  resmi_gazete: "Resmî Gazete",
  sgk: "SGK",
  csgb: "ÇSGB",
  mevzuat: "Mevzuat.gov.tr",
};

const KAYNAK_RENK: Record<string, string> = {
  resmi_gazete: "bg-red-100 text-red-700",
  sgk: "bg-blue-100 text-blue-700",
  csgb: "bg-green-100 text-green-700",
  mevzuat: "bg-purple-100 text-purple-700",
};

const KAT_RENK: Record<string, string> = {
  ik: "bg-orange-100 text-orange-700",
  mali: "bg-yellow-100 text-yellow-700",
  hukuk: "bg-indigo-100 text-indigo-700",
};

export default function OutpulsePage() {
  const [items, setItems] = useState<MevzuatItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [kategori, setKategori] = useState("");
  const [kaynak, setKaynak] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (kategori) params.set("kategori", kategori);
      if (kaynak) params.set("kaynak", kaynak);
      if (q) params.set("q", q);
      const res = await fetch(`${RADAR_BASE}/mevzuat?${params}`);
      if (res.ok) setItems(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [kategori, kaynak]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load();
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const res = await fetch(`${RADAR_BASE}/scan`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setScanResult(`✅ Tarama tamamlandı — ${data.bulunan_kayit} kayıt bulundu, ${data.yeni_kayit} yeni.`);
        await load();
      }
    } catch {
      setScanResult("❌ Tarama sırasında hata oluştu.");
    } finally {
      setScanning(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-slate-400 hover:text-white text-sm">← Ana Sayfa</Link>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">O</span>
              </div>
              <div>
                <h1 className="font-semibold text-white">Outpulse</h1>
                <p className="text-xs text-slate-400">Mevzuat Radar</p>
              </div>
            </div>
          </div>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
          >
            {scanning ? "Taranıyor…" : "🔍 Manuel Tara"}
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Scan result */}
        {scanResult && (
          <div className="mb-4 bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-sm text-slate-200">
            {scanResult}
          </div>
        )}

        {/* Arama + Filtreler */}
        <form onSubmit={handleSearch} className="mb-6 flex gap-3 flex-wrap">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Mevzuatta ara…"
            className="flex-1 min-w-48 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg"
          >
            Ara
          </button>
        </form>

        {/* Filtre çipleri */}
        <div className="flex gap-2 flex-wrap mb-6">
          {/* Kategori */}
          {(["", "ik", "mali", "hukuk"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKategori(k)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
                ${kategori === k
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-700 text-slate-300 hover:bg-slate-600"}`}
            >
              {k ? KATEGORI_LABELS[k] : "Tüm Kategoriler"}
            </button>
          ))}
          <span className="w-px bg-slate-600 mx-1" />
          {/* Kaynak */}
          {(["", "resmi_gazete", "sgk", "csgb", "mevzuat"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKaynak(k)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
                ${kaynak === k
                  ? "bg-blue-600 text-white"
                  : "bg-slate-700 text-slate-300 hover:bg-slate-600"}`}
            >
              {k ? KAYNAK_LABELS[k] : "Tüm Kaynaklar"}
            </button>
          ))}
        </div>

        {/* Liste */}
        {loading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-slate-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-12 text-center">
            <p className="text-4xl mb-3">📭</p>
            <p className="text-slate-400 text-sm">Sonuç bulunamadı.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <article
                key={item.id}
                className="bg-slate-800 border border-slate-700 hover:border-slate-500 rounded-xl p-5 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex gap-2 flex-wrap">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${KAYNAK_RENK[item.kaynak] ?? "bg-slate-700 text-slate-300"}`}>
                      {KAYNAK_LABELS[item.kaynak] ?? item.kaynak}
                    </span>
                    {item.kategori && (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${KAT_RENK[item.kategori] ?? "bg-slate-700 text-slate-300"}`}>
                        {KATEGORI_LABELS[item.kategori] ?? item.kategori}
                      </span>
                    )}
                  </div>
                  {item.yayin_tarihi && (
                    <span className="shrink-0 text-xs text-slate-500">
                      {new Date(item.yayin_tarihi).toLocaleDateString("tr-TR")}
                    </span>
                  )}
                </div>
                <h2 className="text-sm font-semibold text-white mb-1 leading-snug">
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-emerald-400 transition-colors">
                      {item.baslik}
                    </a>
                  ) : item.baslik}
                </h2>
                {item.ozet && (
                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                    {item.ozet}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}

        {/* Alt bilgi */}
        <div className="mt-8 text-center text-xs text-slate-600">
          Kaynaklar: Resmî Gazete · SGK · Çalışma Bakanlığı · Mevzuat.gov.tr
          <br />
          Bu platform bilgi amaçlıdır; hukuki tavsiye niteliği taşımaz.
        </div>
      </div>
    </main>
  );
}

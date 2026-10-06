"use client";
/**
 * İzin Geçmişi / Takip Sayfası
 * - Tüm talepler listelenir (yıl ve durum filtresiyle)
 * - Bekleyen talepler iptal edilebilir
 * - Görev çakışması olan talepler için detay paneli açılır
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchEmployeeRequests, cancelRequest } from "@/lib/api";
import { LeaveRequest, IzinDurum } from "@/types/leave";
import {
  LeaveConflictInfo, TaskConflict,
  PRIORITY_LABELS, PRIORITY_DOT,
} from "@/types/tasks";
import LeaveStatusBadge from "@/components/inpulse/LeaveStatusBadge";
import { checkLeaveConflicts } from "@/lib/tasks";
import { getCurrentUser } from "@/lib/auth";

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

function izinTuruLabel(kod: string): string {
  return IZIN_TURU_LABELS[kod] ?? kod.replace(/_/g, " ");
}

function getEmployeeId(): string {
  try {
    const u = getCurrentUser();
    return u?.id ?? "demo-employee-001";
  } catch {
    return "demo-employee-001";
  }
}

const DURUM_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Tümü" },
  { value: "beklemede", label: "Beklemede" },
  { value: "onaylandi", label: "Onaylandı" },
  { value: "reddedildi", label: "Reddedildi" },
  { value: "iptal", label: "İptal" },
];

/** Çakışma detay paneli */
function ConflictDetailPanel({ conflict }: { conflict: LeaveConflictInfo }) {
  const isOzel = conflict.ozel_izin;

  return (
    <div
      className={`mt-3 rounded-xl border p-3 ${
        isOzel ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"
      }`}
    >
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-sm">{isOzel ? "🚨" : "⚠️"}</span>
        <p className={`text-xs font-semibold ${isOzel ? "text-red-800" : "text-amber-800"}`}>
          {isOzel
            ? "Özel izin — yöneticiniz bu görevleri devredecektir"
            : "İzin sürenizde aktif görevler var"}
        </p>
      </div>

      <div className="space-y-1.5">
        {conflict.cakisan_gorevler.map((task: TaskConflict) => (
          <div
            key={task.task_id}
            className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs
              ${isOzel ? "bg-red-100" : "bg-amber-100"}`}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.oncelik]}`} />
            <span
              className={`font-medium flex-1 truncate ${
                isOzel ? "text-red-900" : "text-amber-900"
              }`}
            >
              {task.baslik}
            </span>
            <span className={`flex-shrink-0 ${isOzel ? "text-red-600" : "text-amber-600"}`}>
              {PRIORITY_LABELS[task.oncelik]}
            </span>
            <span className={`flex-shrink-0 ${isOzel ? "text-red-400" : "text-amber-400"}`}>
              {new Date(task.bitis_tarihi).toLocaleDateString("tr-TR")}
            </span>
          </div>
        ))}
      </div>

      {isOzel && (
        <p className="text-[10px] text-red-500 mt-2">
          Yöneticiniz onay aşamasında görevleri başka bir çalışana devredecektir.
        </p>
      )}
    </div>
  );
}

export default function LeaveHistoryPage() {
  const [talepler, setTalepler] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [durumFilter, setDurumFilter] = useState<string>("");
  const [cancelling, setCancelling] = useState<string | null>(null);
  // SSR guard: getCurrentUser() returns null on server — initialize with fallback,
  // then correct it on client mount via useEffect below.
  const [employeeId, setEmployeeId] = useState<string>("demo-employee-001");

  // leaveId → LeaveConflictInfo (çakışma olan talepler)
  const [conflictMap, setConflictMap] = useState<Record<string, LeaveConflictInfo>>({});
  // Hangi talepin detay paneli açık
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Client-side only: set the real logged-in user's ID after hydration
  useEffect(() => {
    const u = getCurrentUser();
    if (u?.id) setEmployeeId(u.id);
  }, []);

  const loadTalepler = async (eid: string) => {
    setLoading(true);
    try {
      const data = await fetchEmployeeRequests(eid, 2026);
      setTalepler(data);

      // Bekleyen talepler için paralel çakışma kontrolü
      const bekleyen = data.filter((t) => t.durum === "beklemede");
      if (bekleyen.length > 0) {
        const results = await Promise.allSettled(
          bekleyen.map((t) =>
            checkLeaveConflicts(
              eid,
              t.cikis_tarihi,
              t.giris_tarihi,
              t.izin_turu,
            ),
          ),
        );
        const map: Record<string, LeaveConflictInfo> = {};
        results.forEach((r, i) => {
          if (r.status === "fulfilled" && r.value.cakisan_gorevler.length > 0) {
            map[bekleyen[i].id] = r.value;
          }
        });
        setConflictMap(map);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // employeeId değişince (SSR fallback → gerçek ID) yeniden yükle
    loadTalepler(employeeId);
    // 30 saniyede bir otomatik yenile — onay/red bildirimleri canlı görünsün
    const interval = setInterval(() => loadTalepler(employeeId), 30_000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId]);

  const handleCancel = async (talepId: string) => {
    if (!confirm("Bu talebi iptal etmek istediğinizden emin misiniz?")) return;
    setCancelling(talepId);
    try {
      await cancelRequest(talepId, employeeId);
      await loadTalepler(employeeId);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "İptal edilemedi");
    } finally {
      setCancelling(null);
    }
  };

  const filtered = durumFilter
    ? talepler.filter((t) => t.durum === durumFilter)
    : talepler;

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link href="/inpulse" className="text-gray-400 hover:text-gray-600">← Geri</Link>
          <div>
            <h1 className="font-semibold text-gray-900">İzin Takibi</h1>
            <p className="text-xs text-gray-500">2026 — tüm talepleriniz</p>
          </div>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Filtreler + Yeni Talep */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex gap-2 flex-wrap">
            {DURUM_FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setDurumFilter(opt.value)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
                  ${durumFilter === opt.value
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-gray-300 text-gray-600 hover:bg-gray-50"}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Link
            href="/inpulse/leave"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            + Yeni Talep
          </Link>
        </div>

        {/* Liste */}
        {loading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
            <p className="text-4xl mb-3">📭</p>
            <p className="text-gray-500 text-sm">Henüz izin talebi bulunmuyor.</p>
            <Link
              href="/inpulse/leave"
              className="inline-block mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
            >
              İlk Talebi Oluştur
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-100">
            {filtered.map((talep) => {
              const conflict = conflictMap[talep.id];
              const hasConflict = !!conflict;
              const isExpanded = expandedId === talep.id;
              const isOzel = conflict?.ozel_izin ?? false;

              return (
                <div key={talep.id} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {/* İzin türü + durum rozeti + çakışma butonu */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-gray-900">
                          {izinTuruLabel(talep.izin_turu)}
                        </p>
                        <LeaveStatusBadge durum={talep.durum as IzinDurum} />

                        {hasConflict && (
                          <button
                            onClick={() =>
                              setExpandedId(isExpanded ? null : talep.id)
                            }
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                              text-[10px] font-semibold border transition-colors
                              ${isOzel
                                ? "bg-red-100 text-red-700 border-red-200 hover:bg-red-200"
                                : "bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200"
                              }`}
                          >
                            {isOzel ? "🚨" : "⚠️"}
                            {isOzel ? "Özel izin çakışması" : "Görev çakışması"}
                            <span className="ml-0.5 opacity-70">
                              {isExpanded ? "▲" : "▼"}
                            </span>
                          </button>
                        )}
                      </div>

                      {/* Tarih + süre */}
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")}
                        {" → "}
                        {new Date(talep.giris_tarihi).toLocaleDateString("tr-TR")}
                        {talep.sure_gun && ` (${talep.sure_gun} gün)`}
                      </p>

                      {talep.neden && (
                        <p className="text-xs text-gray-400 mt-1 italic">"{talep.neden}"</p>
                      )}
                      {talep.ret_nedeni && (
                        <p className="text-xs text-red-500 mt-1">
                          Red: {talep.ret_nedeni}
                        </p>
                      )}

                      {/* Açılan detay paneli */}
                      {isExpanded && conflict && (
                        <ConflictDetailPanel conflict={conflict} />
                      )}
                    </div>

                    {talep.durum === "beklemede" && (
                      <button
                        onClick={() => handleCancel(talep.id)}
                        disabled={cancelling === talep.id}
                        className="shrink-0 text-xs text-red-500 hover:text-red-700 disabled:opacity-40"
                      >
                        {cancelling === talep.id ? "İptal ediliyor…" : "İptal Et"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}

"use client";
/**
 * Yönetici Paneli — v13
 * İki ayrı sekme:
 *  1. Çalışan İzin Talepleri — bekleyen onaylar (onayla / reddet)
 *  2. Kendi İzin Takibim    — yöneticinin kendi izin geçmişi
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchManagerAllRequests,
  submitManagerDecision,
  fetchLeaveDocuments,
  fetchEmployeeRequests,
  LeaveDocument,
} from "@/lib/api";
import { LeaveRequest, IzinDurum } from "@/types/leave";
import { LeaveConflictInfo, TaskConflict, PRIORITY_LABELS, PRIORITY_DOT } from "@/types/tasks";
import { checkLeaveConflicts, reassignTask } from "@/lib/tasks";
import LeaveStatusBadge from "@/components/inpulse/LeaveStatusBadge";
import { getCurrentUser, MockUser } from "@/lib/auth";

// ─── Sabit etiketler (backend ile senkron) ──────────────────────────────────
const IZIN_TURU_LABELS: Record<string, string> = {
  yillik:      "📅 Yıllık İzin",
  evlilik:     "💍 Evlilik İzni",
  olum:        "🕊️ Ölüm İzni",
  baba_dogum:  "👶 Babalık İzni",
  dogum_kadin: "🤱 Doğum İzni",
  hastalik:    "🏥 Hastalık İzni",
  ucretsiz:    "📋 Ücretsiz İzin",
  "2saat":     "⏱️ 2 Saat İzin",
  "2saat_uzeri":"⏰ Mazeret İzni",
  idari:       "🏛️ İdari İzin",
};

const DURUM_RENK: Record<string, string> = {
  beklemede:  "bg-yellow-100 text-yellow-800",
  onaylandi:  "bg-green-100 text-green-800",
  reddedildi: "bg-red-100 text-red-800",
  iptal:      "bg-gray-100 text-gray-600",
};

function izinTuruLabel(kod: string): string {
  return IZIN_TURU_LABELS[kod] ?? kod.replace(/_/g, " ");
}

// Özel izin türleri (devir zorunlu)
const OZEL_IZIN_TURLERI = new Set(["olum", "dogum_kadin", "baba_dogum", "hastalik"]);

// Demo çalışan adları — üretimde /employees API'sinden gelir
const DEMO_EMPLOYEES: Record<string, string> = {
  "demo-employee-001": "Zeynep Yılmaz",
  "demo-employee-002": "Kemal Demir",
  "demo-employee-003": "Selin Kaya",
  "demo-employee-ayse": "Ayşe Aydın",
  "demo-manager-001":  "Mehmet Kaya",
};

function employeeName(id: string): string {
  return DEMO_EMPLOYEES[id] ?? id;
}

interface TaskReassignState { [taskId: string]: string; }
interface ConflictMap      { [leaveId: string]: LeaveConflictInfo; }
interface DocumentMap      { [leaveId: string]: LeaveDocument[]; }

// ─────────────────────────────────────────────────────────────────────────────
export default function ManagerPage() {
  const router = useRouter();
  const [user, setUser] = useState<MockUser | null>(null);

  // Sekme: "calisanlar" | "kendi"
  const [tab, setTab] = useState<"calisanlar" | "kendi">("calisanlar");

  // ── Sekme 1: bekleyen çalışan talepleri ──────────────────────────────────
  const [talepler, setTalepler]   = useState<LeaveRequest[]>([]);
  const [loading1, setLoading1]   = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const [retNedeni, setRetNedeni] = useState<Record<string, string>>({});
  const [conflicts, setConflicts] = useState<ConflictMap>({});
  const [reassignSelections, setReassignSelections] = useState<TaskReassignState>({});
  const [reassigning, setReassigning] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentMap>({});

  // ── Sekme 2: kendi izin geçmişi ──────────────────────────────────────────
  const [kendiTalepler, setKendiTalepler] = useState<LeaveRequest[]>([]);
  const [loading2, setLoading2]           = useState(false);

  // ─── Auth ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (u.role !== "yonetici" && u.role !== "ik") { router.replace("/inpulse"); return; }
    setUser(u);
  }, [router]);

  // ─── Çalışan talebi yükle (tümü: bekleyen + geçmiş) ─────────────────────────
  const loadCalisanTalepleri = async (yoneticiId: string) => {
    setLoading1(true);
    try {
      const data = await fetchManagerAllRequests(yoneticiId, 2026);
      setTalepler(data);
      // Sadece bekleyen talepler için çakışma ve belge kontrolü yap
      const bekleyen = data.filter((t) => t.durum === "beklemede");
      await Promise.all([
        fetchConflictsForAll(bekleyen, yoneticiId),
        fetchDocumentsForAll(bekleyen),
      ]);
    } finally {
      setLoading1(false);
    }
  };

  // ─── Kendi izin geçmişi yükle ─────────────────────────────────────────────
  const loadKendiTalepleri = async (yoneticiId: string) => {
    setLoading2(true);
    try {
      const data = await fetchEmployeeRequests(yoneticiId);
      setKendiTalepler(data);
    } finally {
      setLoading2(false);
    }
  };

  async function fetchDocumentsForAll(leaves: LeaveRequest[]) {
    const result: DocumentMap = {};
    await Promise.allSettled(
      leaves.map(async (t) => {
        const docs = await fetchLeaveDocuments(t.id);
        if (docs.length > 0) result[t.id] = docs;
      }),
    );
    setDocuments(result);
  }

  async function fetchConflictsForAll(leaves: LeaveRequest[], managerId: string) {
    const result: ConflictMap = {};
    await Promise.allSettled(
      leaves.map(async (t) => {
        try {
          const info = await checkLeaveConflicts(t.employee_id, t.cikis_tarihi, t.giris_tarihi, t.izin_turu);
          if (info.cakisan_gorevler.length > 0) result[t.id] = info;
        } catch { /* sessiz */ }
      }),
    );
    setConflicts(result);
    void managerId; // TS
  }

  // ─── user değişince yükle ─────────────────────────────────────────────────
  useEffect(() => {
    if (!user) return;
    loadCalisanTalepleri(user.id);
    const iv = setInterval(() => loadCalisanTalepleri(user.id), 30_000);
    return () => clearInterval(iv);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Kendi sekmesine geçince yükle
  useEffect(() => {
    if (!user || tab !== "kendi") return;
    loadKendiTalepleri(user.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, tab]);

  // ─── Karar ver ───────────────────────────────────────────────────────────
  const handleDecision = async (talepId: string, durum: "onaylandi" | "reddedildi") => {
    if (!user) return;
    setProcessing(talepId);
    try {
      await submitManagerDecision(user.id, talepId, {
        durum,
        ret_nedeni: retNedeni[talepId] || undefined,
      });
      await loadCalisanTalepleri(user.id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "İşlem başarısız");
    } finally {
      setProcessing(null);
    }
  };

  // ─── Görev devret ─────────────────────────────────────────────────────────
  async function handleReassign(task: TaskConflict, leaveId: string) {
    if (!user) return;
    const yeniId = reassignSelections[task.task_id];
    if (!yeniId) { alert("Lütfen bir çalışan seçin"); return; }
    setReassigning(task.task_id);
    try {
      await reassignTask(task.task_id, user.id, yeniId, `İzin sebebiyle devir (leave: ${leaveId})`);
      setConflicts((prev) => {
        const updated = { ...prev };
        if (updated[leaveId]) {
          updated[leaveId] = {
            ...updated[leaveId],
            cakisan_gorevler: updated[leaveId].cakisan_gorevler.filter((t) => t.task_id !== task.task_id),
          };
          if (updated[leaveId].cakisan_gorevler.length === 0) delete updated[leaveId];
        }
        return updated;
      });
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Devir başarısız");
    } finally {
      setReassigning(null);
    }
  }

  if (!user) return null;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* ─── Header ──────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link href="/inpulse" className="text-gray-400 hover:text-gray-600">← Geri</Link>
          <div>
            <h1 className="font-semibold text-gray-900">Yönetici Paneli</h1>
            <p className="text-xs text-gray-500">{user.name}</p>
          </div>
        </div>
      </header>

      {/* ─── Sekmeler ────────────────────────────────────────────────────── */}
      <div className="max-w-2xl mx-auto px-6 pt-6">
        <div className="flex rounded-xl overflow-hidden border border-gray-200 bg-white mb-6">
          <button
            onClick={() => setTab("calisanlar")}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${
              tab === "calisanlar"
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            👥 Çalışan İzin Talepleri
            {talepler.filter((t) => t.durum === "beklemede").length > 0 && (
              <span className={`ml-2 text-xs rounded-full px-2 py-0.5 ${
                tab === "calisanlar" ? "bg-white/20 text-white" : "bg-red-100 text-red-700"
              }`}>
                {talepler.filter((t) => t.durum === "beklemede").length}
              </span>
            )}
          </button>
          <button
            onClick={() => setTab("kendi")}
            className={`flex-1 py-3 text-sm font-medium transition-colors border-l border-gray-200 ${
              tab === "kendi"
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            📋 Kendi İzin Takibim
          </button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 pb-8">

        {/* ════════════════════════════════════════════════════════════════════
            SEKME 1 — Çalışan Talepleri
        ════════════════════════════════════════════════════════════════════ */}
        {tab === "calisanlar" && (
          <>
            {loading1 ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-32 bg-gray-200 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : talepler.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
                <p className="text-4xl mb-3">✅</p>
                <p className="text-gray-500 text-sm">Ekibinizden henüz izin talebi yok.</p>
              </div>
            ) : (
              <>
                {/* Bekleyen talepler başlığı */}
                {talepler.some((t) => t.durum === "beklemede") && (
                  <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                    ⏳ Bekleyen Onaylar
                  </h2>
                )}
                <div className="space-y-4">
                  {talepler.filter((t) => t.durum === "beklemede").map((talep) => {
                  const conflict = conflicts[talep.id];
                  const hasConflict = !!conflict && conflict.cakisan_gorevler.length > 0;
                  const isOzel =
                    (conflict?.ozel_izin ?? false) || OZEL_IZIN_TURLERI.has(talep.izin_turu);

                  return (
                    <div key={talep.id} className="bg-white rounded-xl border border-blue-200 shadow-sm p-5">
                      {/* Talep başlığı */}
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <p className="font-semibold text-gray-900 text-sm">
                            {employeeName(talep.employee_id)}
                          </p>
                          <p className="text-sm text-gray-600 mt-0.5">
                            {izinTuruLabel(talep.izin_turu)} —{" "}
                            {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")}
                            {" → "}
                            {new Date(talep.giris_tarihi).toLocaleDateString("tr-TR")}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            {talep.sure_gun} iş günü
                            {talep.neden && ` · "${talep.neden}"`}
                          </p>
                          {talep.ret_nedeni && (
                            <p className="text-xs text-red-500 mt-1">Red: {talep.ret_nedeni}</p>
                          )}
                        </div>
                        <LeaveStatusBadge durum={talep.durum as IzinDurum} />
                      </div>

                      {/* Çakışma paneli — sadece bekleyen için */}
                      {hasConflict && (
                        <div className={`rounded-lg border p-3 mb-4 ${
                          isOzel ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"
                        }`}>
                          <div className="flex items-center gap-1.5 mb-2">
                            <span>{isOzel ? "🚨" : "⚠️"}</span>
                            <p className={`text-xs font-semibold ${isOzel ? "text-red-800" : "text-amber-800"}`}>
                              {isOzel
                                ? "Özel izin — aşağıdaki görevler devredilmelidir"
                                : "İzin döneminde aktif görevler mevcut"}
                            </p>
                          </div>

                          <div className="space-y-2">
                            {conflict.cakisan_gorevler.map((task: TaskConflict) => (
                              <div key={task.task_id} className="space-y-1.5">
                                <div className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded-md
                                  ${isOzel ? "bg-red-100" : "bg-amber-100"}`}>
                                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.oncelik]}`} />
                                  <span className={`font-medium flex-1 truncate ${isOzel ? "text-red-900" : "text-amber-900"}`}>
                                    {task.baslik}
                                  </span>
                                  <span className={`flex-shrink-0 ${isOzel ? "text-red-600" : "text-amber-600"}`}>
                                    {PRIORITY_LABELS[task.oncelik]}
                                  </span>
                                  <span className={`flex-shrink-0 ${isOzel ? "text-red-400" : "text-amber-400"}`}>
                                    {new Date(task.bitis_tarihi).toLocaleDateString("tr-TR")}
                                  </span>
                                </div>

                                {isOzel && (
                                  <div className="flex items-center gap-2 pl-1">
                                    <select
                                      value={reassignSelections[task.task_id] ?? ""}
                                      onChange={(e) =>
                                        setReassignSelections((prev) => ({ ...prev, [task.task_id]: e.target.value }))
                                      }
                                      className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5
                                                 focus:outline-none focus:ring-2 focus:ring-blue-400"
                                    >
                                      <option value="">— Çalışan seç —</option>
                                      {Object.entries(DEMO_EMPLOYEES)
                                        .filter(([id]) => id !== talep.employee_id && !id.includes("manager"))
                                        .map(([id, name]) => (
                                          <option key={id} value={id}>{name}</option>
                                        ))}
                                    </select>
                                    <button
                                      onClick={() => handleReassign(task, talep.id)}
                                      disabled={!reassignSelections[task.task_id] || reassigning === task.task_id}
                                      className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5
                                                 rounded-lg transition-colors disabled:opacity-40 flex-shrink-0"
                                    >
                                      {reassigning === task.task_id ? "Devrediyor…" : "🔄 Devret"}
                                    </button>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>

                          {isOzel && conflict.cakisan_gorevler.length > 0 && (
                            <p className="text-[10px] text-red-500 mt-2">
                              Onaylamadan önce tüm görevleri devretmeniz önerilir.
                            </p>
                          )}
                        </div>
                      )}

                      {/* Belgeler */}
                      {documents[talep.id]?.length > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                          <p className="text-xs font-semibold text-blue-800 mb-2">📎 Yüklenen Belgeler</p>
                          <div className="space-y-1">
                            {documents[talep.id].map((doc) => (
                              <div key={doc.id} className="flex items-center gap-2 text-xs text-blue-700">
                                <span>🗒️</span>
                                <span className="font-medium truncate">{doc.dosya_adi}</span>
                                <span className="text-blue-400 flex-shrink-0">
                                  {new Date(doc.yuklenme_tarihi).toLocaleDateString("tr-TR")}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Onayla / Reddet butonları */}
                      <>
                          <input
                            type="text"
                            placeholder="Red nedeni (reddetmek için gerekli)"
                            value={retNedeni[talep.id] ?? ""}
                            onChange={(e) => setRetNedeni((prev) => ({ ...prev, [talep.id]: e.target.value }))}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mb-3
                                       focus:outline-none focus:ring-2 focus:ring-blue-400"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleDecision(talep.id, "onaylandi")}
                              disabled={processing === talep.id}
                              className="flex-1 py-2 bg-green-600 text-white rounded-lg text-sm font-medium
                                         hover:bg-green-700 disabled:opacity-40 transition-colors"
                            >
                              ✓ Onayla
                            </button>
                            <button
                              onClick={() => handleDecision(talep.id, "reddedildi")}
                              disabled={processing === talep.id || !retNedeni[talep.id]}
                              className="flex-1 py-2 bg-red-600 text-white rounded-lg text-sm font-medium
                                         hover:bg-red-700 disabled:opacity-40 transition-colors"
                            >
                              ✕ Reddet
                            </button>
                          </div>
                      </>
                    </div>
                  );
                })}
                </div>

                {/* Geçmiş bölümü */}
                {talepler.some((t) => t.durum !== "beklemede") && (
                  <>
                    <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-6 mb-3">
                      📋 Karar Geçmişi
                    </h2>
                    <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-100">
                      {talepler.filter((t) => t.durum !== "beklemede").map((talep) => (
                        <div key={talep.id} className="px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <p className="text-sm font-semibold text-gray-900">
                                  {employeeName(talep.employee_id)}
                                </p>
                                <LeaveStatusBadge durum={talep.durum as IzinDurum} />
                              </div>
                              <p className="text-xs text-gray-600">
                                {izinTuruLabel(talep.izin_turu)} —{" "}
                                {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")}
                                {" → "}
                                {new Date(talep.giris_tarihi).toLocaleDateString("tr-TR")}
                                {talep.sure_gun != null && ` (${talep.sure_gun} gün)`}
                              </p>
                              {talep.neden && (
                                <p className="text-xs text-gray-400 mt-1 italic">"{talep.neden}"</p>
                              )}
                              {talep.ret_nedeni && (
                                <p className="text-xs text-red-500 mt-1">Red: {talep.ret_nedeni}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </>
        )}

        {/* ════════════════════════════════════════════════════════════════════
            SEKME 2 — Kendi İzin Takibim
        ════════════════════════════════════════════════════════════════════ */}
        {tab === "kendi" && (
          <>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-500">
                {loading2 ? "Yükleniyor…" : `${kendiTalepler.length} izin talebi`}
              </p>
              <Link
                href="/inpulse/leave"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                + Yeni Talep
              </Link>
            </div>

            {loading2 ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-20 bg-gray-200 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : kendiTalepler.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
                <p className="text-4xl mb-3">📭</p>
                <p className="text-gray-500 text-sm">Henüz izin talebiniz bulunmuyor.</p>
                <Link
                  href="/inpulse/leave"
                  className="inline-block mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
                >
                  İlk Talebi Oluştur
                </Link>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-100">
                {kendiTalepler.map((talep) => (
                  <div key={talep.id} className="px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <p className="text-sm font-semibold text-gray-900">
                            {izinTuruLabel(talep.izin_turu)}
                          </p>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            DURUM_RENK[talep.durum] ?? "bg-gray-100 text-gray-600"
                          }`}>
                            {talep.durum === "beklemede"  ? "⏳ Beklemede"
                            : talep.durum === "onaylandi"  ? "✅ Onaylandı"
                            : talep.durum === "reddedildi" ? "❌ Reddedildi"
                            : "🚫 İptal"}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")}
                          {" → "}
                          {new Date(talep.giris_tarihi).toLocaleDateString("tr-TR")}
                          {talep.sure_gun != null && ` (${talep.sure_gun} gün)`}
                        </p>
                        {talep.neden && (
                          <p className="text-xs text-gray-400 mt-1 italic">"{talep.neden}"</p>
                        )}
                        {talep.ret_nedeni && (
                          <p className="text-xs text-red-500 mt-1">Red: {talep.ret_nedeni}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

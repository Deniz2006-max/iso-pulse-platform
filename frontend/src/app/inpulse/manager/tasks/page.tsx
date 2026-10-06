"use client";
/**
 * Yönetici Görev Paneli
 * /inpulse/manager/tasks
 * Ekip görevleri, filtreler, yeni görev oluşturma, devir
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getCurrentUser, MockUser } from "@/lib/auth";
import { fetchManagerTasks, createTask, reassignTask } from "@/lib/tasks";
import { Task, PRIORITY_LABELS } from "@/types/tasks";
import TaskCard from "@/components/inpulse/TaskCard";

const DURUM_TABS = [
  { key: "", label: "Tümü" },
  { key: "atandi", label: "Atandı" },
  { key: "devam_ediyor", label: "Devam Ediyor" },
  { key: "onay_bekliyor", label: "Onay Bekliyor" },
  { key: "tamamlandi", label: "Tamamlandı" },
];

// Demo çalışan listesi — gerçek sistemde API'den gelir
const DEMO_EMPLOYEES = [
  { id: "demo-employee-001", ad: "Amira Yılmaz" },
  { id: "demo-employee-002", ad: "Zeynep Kılıç" },
  { id: "demo-employee-003", ad: "Ahmet Demir" },
];

interface NewTaskForm {
  baslik: string;
  aciklama: string;
  oncelik: string;
  bitis_tarihi: string;
  employee_id: string;
}

export default function ManagerTasksPage() {
  const router = useRouter();
  const [user, setUser] = useState<MockUser | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [durumFilter, setDurumFilter] = useState("");
  const [oncelikFilter, setOncelikFilter] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [form, setForm] = useState<NewTaskForm>({
    baslik: "",
    aciklama: "",
    oncelik: "orta",
    bitis_tarihi: "",
    employee_id: DEMO_EMPLOYEES[0].id,
  });

  // Devir paneli
  const [reassignTaskId, setReassignTaskId] = useState<string | null>(null);
  const [reassignTargetId, setReassignTargetId] = useState(DEMO_EMPLOYEES[0].id);
  const [reassignSebep, setReassignSebep] = useState("");
  const [reassignLoading, setReassignLoading] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (u.role !== "yonetici" && u.role !== "ik") {
      router.replace("/inpulse");
      return;
    }
    setUser(u);
  }, [router]);

  useEffect(() => {
    if (!user) return;
    loadTasks();
  }, [user, durumFilter, oncelikFilter]);

  async function loadTasks() {
    if (!user) return;
    setLoading(true);
    try {
      const data = await fetchManagerTasks(user.id, {
        durum: durumFilter || undefined,
        oncelik: oncelikFilter || undefined,
      });
      setTasks(data);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function handleTaskUpdated(updated: Task) {
    setTasks((prev) => prev.map((t) => t.id === updated.id ? updated : t));
  }

  async function handleCreateTask() {
    if (!user || !form.baslik || !form.bitis_tarihi) return;
    setCreateLoading(true);
    try {
      const created = await createTask(user.id, {
        baslik: form.baslik,
        aciklama: form.aciklama || undefined,
        oncelik: form.oncelik,
        bitis_tarihi: form.bitis_tarihi,
        employee_id: form.employee_id,
      });
      setTasks((prev) => [created, ...prev]);
      setShowCreateForm(false);
      setForm({ baslik: "", aciklama: "", oncelik: "orta", bitis_tarihi: "", employee_id: DEMO_EMPLOYEES[0].id });
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleReassign() {
    if (!user || !reassignTaskId) return;
    setReassignLoading(true);
    try {
      const updated = await reassignTask(
        reassignTaskId,
        user.id,
        reassignTargetId,
        reassignSebep || undefined,
      );
      handleTaskUpdated(updated);
      setReassignTaskId(null);
      setReassignSebep("");
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setReassignLoading(false);
    }
  }

  if (!user) return null;

  const tamamlanmayan = tasks.filter(t => t.durum !== "tamamlandi").length;
  const onayBekleyen = tasks.filter(t => t.durum === "onay_bekliyor").length;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/inpulse"
              className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center
                         hover:bg-blue-700 transition-colors"
            >
              <span className="text-white font-bold text-sm">←</span>
            </Link>
            <div>
              <h1 className="font-semibold text-gray-900">Görev Yönetimi</h1>
              <p className="text-xs text-gray-500">Ekip görevlerini yönet</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700
                       text-white text-sm rounded-xl transition-colors shadow-sm"
          >
            <span>+</span> Görev Oluştur
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* Özet satırı */}
        {!loading && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{tasks.length}</p>
              <p className="text-xs text-gray-500 mt-1">Toplam Görev</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-2xl font-bold text-amber-600">{onayBekleyen}</p>
              <p className="text-xs text-gray-500 mt-1">Onay Bekliyor</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{tamamlanmayan}</p>
              <p className="text-xs text-gray-500 mt-1">Devam Eden</p>
            </div>
          </div>
        )}

        {/* Filtreler */}
        <div className="flex flex-wrap gap-2 mb-5">
          {DURUM_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setDurumFilter(tab.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors
                ${durumFilter === tab.key
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-600 hover:border-blue-300"}`}
            >
              {tab.label}
            </button>
          ))}
          <div className="ml-auto">
            <select
              value={oncelikFilter}
              onChange={(e) => setOncelikFilter(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600
                         focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
              <option value="">Tüm Öncelikler</option>
              {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Yükleniyor */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-100 p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {/* Hata */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Görev listesi */}
        {!loading && !error && tasks.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
            <p className="text-4xl mb-3">📋</p>
            <p className="text-gray-500 text-sm">Görev bulunamadı</p>
          </div>
        )}

        {!loading && tasks.length > 0 && (
          <div className="space-y-3">
            {tasks.map((task) => (
              <div key={task.id} className="relative">
                <TaskCard
                  task={task}
                  role={user.role}
                  currentUserId={user.id}
                  onUpdated={handleTaskUpdated}
                />
                {/* Devir butonu */}
                {task.durum !== "tamamlandi" && (
                  <button
                    onClick={() => { setReassignTaskId(task.id); setReassignTargetId(DEMO_EMPLOYEES[0].id); }}
                    className="mt-1 text-xs text-gray-400 hover:text-blue-600 transition-colors"
                  >
                    🔄 Devret
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Görev oluşturma modalı */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h2 className="font-bold text-gray-900 mb-4">Yeni Görev Oluştur</h2>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Başlık *</label>
                <input
                  type="text"
                  value={form.baslik}
                  onChange={(e) => setForm({ ...form, baslik: e.target.value })}
                  placeholder="Görev başlığı…"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Açıklama</label>
                <textarea
                  value={form.aciklama}
                  onChange={(e) => setForm({ ...form, aciklama: e.target.value })}
                  placeholder="Görev açıklaması…"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm resize-none h-20
                             focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Öncelik</label>
                  <select
                    value={form.oncelik}
                    onChange={(e) => setForm({ ...form, oncelik: e.target.value })}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                               focus:outline-none focus:ring-2 focus:ring-blue-300"
                  >
                    <option value="yuksek">Yüksek</option>
                    <option value="orta">Orta</option>
                    <option value="dusuk">Düşük</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Bitiş Tarihi *</label>
                  <input
                    type="date"
                    value={form.bitis_tarihi}
                    onChange={(e) => setForm({ ...form, bitis_tarihi: e.target.value })}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                               focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Çalışan</label>
                <select
                  value={form.employee_id}
                  onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  {DEMO_EMPLOYEES.map((e) => (
                    <option key={e.id} value={e.id}>{e.ad}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-5">
              <button
                onClick={handleCreateTask}
                disabled={createLoading || !form.baslik || !form.bitis_tarihi}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl
                           text-sm font-medium transition-colors disabled:opacity-50"
              >
                {createLoading ? "Oluşturuluyor…" : "Oluştur"}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl
                           text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                İptal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Devir modalı */}
      {reassignTaskId && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h2 className="font-bold text-gray-900 mb-4">Görevi Devret</h2>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Devredilecek Çalışan</label>
                <select
                  value={reassignTargetId}
                  onChange={(e) => setReassignTargetId(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  {DEMO_EMPLOYEES.map((e) => (
                    <option key={e.id} value={e.id}>{e.ad}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Sebep (opsiyonel)</label>
                <textarea
                  value={reassignSebep}
                  onChange={(e) => setReassignSebep(e.target.value)}
                  placeholder="İzin sebebi, hastalık vb.…"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm resize-none h-16
                             focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-5">
              <button
                onClick={handleReassign}
                disabled={reassignLoading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl
                           text-sm font-medium transition-colors disabled:opacity-50"
              >
                {reassignLoading ? "Devrediliyor…" : "Devret"}
              </button>
              <button
                onClick={() => setReassignTaskId(null)}
                className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-xl
                           text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                İptal
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

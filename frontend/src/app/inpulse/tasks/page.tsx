"use client";
/**
 * Çalışan Görev Listesi
 * /inpulse/tasks
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getCurrentUser, MockUser } from "@/lib/auth";
import { fetchEmployeeTasks } from "@/lib/tasks";
import { Task, TaskStatus, STATUS_LABELS } from "@/types/tasks";
import TaskCard from "@/components/inpulse/TaskCard";

const DURUM_TABS: { key: string; label: string }[] = [
  { key: "", label: "Tümü" },
  { key: "atandi", label: "Atandı" },
  { key: "devam_ediyor", label: "Devam Ediyor" },
  { key: "onay_bekliyor", label: "Onay Bekliyor" },
  { key: "tamamlandi", label: "Tamamlandı" },
];

export default function MyTasksPage() {
  const router = useRouter();
  const [user, setUser] = useState<MockUser | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [durumFilter, setDurumFilter] = useState("");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    setUser(u);
  }, [router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    fetchEmployeeTasks(user.id, durumFilter || undefined)
      .then(setTasks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, durumFilter]);

  function handleTaskUpdated(updated: Task) {
    setTasks((prev) => prev.map((t) => t.id === updated.id ? updated : t));
  }

  if (!user) return null;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <Link
            href="/inpulse"
            className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center
                       hover:bg-blue-700 transition-colors"
          >
            <span className="text-white font-bold text-sm">←</span>
          </Link>
          <div>
            <h1 className="font-semibold text-gray-900">Görevlerim</h1>
            <p className="text-xs text-gray-500">Atanmış ve devam eden görevler</p>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* Durum sekmeleri */}
        <div className="flex gap-2 overflow-x-auto pb-1 mb-5">
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
        </div>

        {/* Görev sayacı */}
        {!loading && (
          <p className="text-xs text-gray-400 mb-4">
            {tasks.length} görev bulundu
          </p>
        )}

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
            <p className="text-4xl mb-3">🎉</p>
            <p className="text-gray-500 text-sm">
              {durumFilter
                ? `"${STATUS_LABELS[durumFilter as TaskStatus]}" durumunda görev yok`
                : "Henüz görev atanmadı"}
            </p>
          </div>
        )}

        {!loading && tasks.length > 0 && (
          <div className="space-y-3">
            {tasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                role={user.role}
                currentUserId={user.id}
                onUpdated={handleTaskUpdated}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

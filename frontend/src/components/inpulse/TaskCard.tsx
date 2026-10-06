"use client";
/**
 * TaskCard — Görev Kartı Bileşeni
 * Öncelik rengi, kalan gün, durum rozeti, eylem butonları
 */
import { useState } from "react";
import {
  Task,
  TaskStatus,
  PRIORITY_LABELS,
  PRIORITY_DOT,
  STATUS_LABELS,
  STATUS_COLORS,
} from "@/types/tasks";
import { updateTaskStatus } from "@/lib/tasks";

interface TaskCardProps {
  task: Task;
  role: "calisan" | "yonetici" | "ik";
  currentUserId: string;
  onUpdated?: (updated: Task) => void;
}

function getRemainingDays(bitisTarihi: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const bitis = new Date(bitisTarihi);
  bitis.setHours(0, 0, 0, 0);
  return Math.ceil((bitis.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export default function TaskCard({ task, role, currentUserId, onUpdated }: TaskCardProps) {
  const [loading, setLoading] = useState(false);
  const [retNotu, setRetNotu] = useState("");
  const [showRetInput, setShowRetInput] = useState(false);

  const kalan = getRemainingDays(task.bitis_tarihi);
  const gecti = kalan < 0;
  const kritik = kalan >= 0 && kalan <= 3;

  async function handleStatusChange(yeniDurum: string, notu?: string) {
    setLoading(true);
    try {
      const updated = await updateTaskStatus(task.id, currentUserId, yeniDurum, notu);
      onUpdated?.(updated);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const leftBorderColor = {
    yuksek: "border-l-red-500",
    orta: "border-l-amber-400",
    dusuk: "border-l-green-500",
  }[task.oncelik] ?? "border-l-gray-300";

  return (
    <div
      className={`bg-white rounded-xl border border-gray-100 border-l-4 ${leftBorderColor}
                  shadow-sm hover:shadow-md transition-shadow p-4`}
    >
      {/* Üst satır: başlık + durum */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.oncelik]}`} />
          <h3 className="text-sm font-semibold text-gray-900 truncate">{task.baslik}</h3>
        </div>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0
                      ${STATUS_COLORS[task.durum as TaskStatus]}`}
        >
          {STATUS_LABELS[task.durum as TaskStatus]}
        </span>
      </div>

      {/* Açıklama */}
      {task.aciklama && (
        <p className="text-xs text-gray-500 mb-3 line-clamp-2">{task.aciklama}</p>
      )}

      {/* Alt bilgi: atanan, tarih, kalan */}
      <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
        <div className="flex items-center gap-3">
          {task.calisan_adi && (
            <span className="flex items-center gap-1">
              <span>👤</span> {task.calisan_adi}
            </span>
          )}
          <span className="flex items-center gap-1">
            <span>📅</span>{" "}
            {new Date(task.bitis_tarihi).toLocaleDateString("tr-TR")}
          </span>
        </div>
        {/* Kalan gün rozeti */}
        <span
          className={`font-medium px-2 py-0.5 rounded-full text-xs
            ${gecti
              ? "bg-red-100 text-red-600"
              : kritik
              ? "bg-amber-100 text-amber-700"
              : "bg-gray-100 text-gray-500"
            }`}
        >
          {gecti ? `${Math.abs(kalan)} gün geçti` : kalan === 0 ? "Bugün!" : `${kalan} gün`}
        </span>
      </div>

      {/* Öncelik etiketi */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-gray-400">Öncelik:</span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border
          ${task.oncelik === "yuksek" ? "bg-red-50 text-red-600 border-red-200" :
            task.oncelik === "orta" ? "bg-amber-50 text-amber-600 border-amber-200" :
            "bg-green-50 text-green-600 border-green-200"}`}
        >
          {PRIORITY_LABELS[task.oncelik]}
        </span>
      </div>

      {/* Ret notu */}
      {task.ret_notu && (
        <div className="mb-3 bg-red-50 border border-red-100 rounded-lg p-2">
          <p className="text-xs text-red-600">
            <span className="font-semibold">Ret notu:</span> {task.ret_notu}
          </p>
        </div>
      )}

      {/* Eylem butonları — çalışan */}
      {role === "calisan" && task.durum === "atandi" && (
        <button
          onClick={() => handleStatusChange("devam_ediyor")}
          disabled={loading}
          className="w-full text-xs bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg
                     transition-colors disabled:opacity-50"
        >
          Başla
        </button>
      )}

      {role === "calisan" && task.durum === "devam_ediyor" && (
        <button
          onClick={() => handleStatusChange("teslim_edildi")}
          disabled={loading}
          className="w-full text-xs bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-lg
                     transition-colors disabled:opacity-50"
        >
          Teslim Et
        </button>
      )}

      {/* Eylem butonları — yönetici (onay_bekliyor) */}
      {(role === "yonetici" || role === "ik") && task.durum === "onay_bekliyor" && (
        <div className="space-y-2">
          <button
            onClick={() => handleStatusChange("tamamlandi")}
            disabled={loading}
            className="w-full text-xs bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg
                       transition-colors disabled:opacity-50"
          >
            ✓ Onayla
          </button>

          {!showRetInput ? (
            <button
              onClick={() => setShowRetInput(true)}
              disabled={loading}
              className="w-full text-xs border border-red-300 text-red-600 hover:bg-red-50
                         py-2 rounded-lg transition-colors disabled:opacity-50"
            >
              Reddet
            </button>
          ) : (
            <div className="space-y-1">
              <textarea
                value={retNotu}
                onChange={(e) => setRetNotu(e.target.value)}
                placeholder="Red nedeni (zorunlu değil)…"
                className="w-full text-xs border border-gray-200 rounded-lg p-2 resize-none h-16
                           focus:outline-none focus:ring-2 focus:ring-red-300"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => handleStatusChange("atandi", retNotu || undefined)}
                  disabled={loading}
                  className="flex-1 text-xs bg-red-600 hover:bg-red-700 text-white py-2 rounded-lg
                             transition-colors disabled:opacity-50"
                >
                  Reddet
                </button>
                <button
                  onClick={() => setShowRetInput(false)}
                  className="flex-1 text-xs border border-gray-200 text-gray-500 py-2 rounded-lg
                             hover:bg-gray-50 transition-colors"
                >
                  İptal
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

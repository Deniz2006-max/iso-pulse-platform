"use client";
/**
 * NotificationBell — Bildirim Zili Bileşeni
 * Header'da gösterilir; dropdown ile son bildirimleri listeler
 */
import { useEffect, useRef, useState } from "react";
import { Notification, NotificationSummary } from "@/types/tasks";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "@/lib/notifications";

interface NotificationBellProps {
  userId: string;
}

const NOTIF_ICONS: Record<string, string> = {
  task_assigned: "📋",
  task_deadline_7: "⏰",
  task_deadline_3: "⚠️",
  task_deadline_1: "🚨",
  task_submitted: "📤",
  task_approved: "✅",
  task_rejected: "❌",
  task_reassigned: "🔄",
};

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Az önce";
  if (mins < 60) return `${mins} dk önce`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} sa önce`;
  const days = Math.floor(hours / 24);
  return `${days} gün önce`;
}

export default function NotificationBell({ userId }: NotificationBellProps) {
  const [summary, setSummary] = useState<NotificationSummary | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 30000); // 30 sn'de bir yenile
    return () => clearInterval(interval);
  }, [userId]);

  // Dropdown dışına tıklayınca kapat
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function loadNotifications() {
    try {
      const data = await fetchNotifications(userId, false, 15);
      setSummary(data);
    } catch {
      // Sessiz hata — bildirim zili kritik değil
    }
  }

  async function handleMarkAllRead() {
    setLoading(true);
    try {
      await markAllNotificationsRead(userId);
      await loadNotifications();
    } finally {
      setLoading(false);
    }
  }

  async function handleRead(notif: Notification) {
    if (!notif.okundu) {
      await markNotificationRead(notif.id).catch(() => {});
      setSummary((prev) =>
        prev
          ? {
              ...prev,
              okunmamis_sayi: Math.max(0, prev.okunmamis_sayi - 1),
              bildirimler: prev.bildirimler.map((b) =>
                b.id === notif.id ? { ...b, okundu: true } : b
              ),
            }
          : prev
      );
    }
  }

  const okunmamis = summary?.okunmamis_sayi ?? 0;

  return (
    <div className="relative" ref={ref}>
      {/* Zil butonu */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative w-9 h-9 flex items-center justify-center rounded-full
                   hover:bg-gray-100 transition-colors"
        aria-label="Bildirimler"
      >
        <span className="text-lg">🔔</span>
        {okunmamis > 0 && (
          <span
            className="absolute top-0.5 right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white
                       text-[10px] font-bold rounded-full flex items-center justify-center px-1"
          >
            {okunmamis > 9 ? "9+" : okunmamis}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl
                     border border-gray-100 z-50 overflow-hidden"
        >
          {/* Başlık */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h3 className="font-semibold text-sm text-gray-900">Bildirimler</h3>
            {okunmamis > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={loading}
                className="text-xs text-blue-600 hover:underline disabled:opacity-50"
              >
                Tümünü okundu işaretle
              </button>
            )}
          </div>

          {/* Liste */}
          <div className="max-h-72 overflow-y-auto divide-y divide-gray-50">
            {!summary || summary.bildirimler.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400">
                Bildirim yok 🎉
              </div>
            ) : (
              summary.bildirimler.map((notif) => (
                <div
                  key={notif.id}
                  onClick={() => handleRead(notif)}
                  className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors
                    ${notif.okundu ? "hover:bg-gray-50" : "bg-blue-50 hover:bg-blue-100"}`}
                >
                  <span className="text-lg flex-shrink-0 mt-0.5">
                    {NOTIF_ICONS[notif.tur] ?? "📌"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs leading-snug ${notif.okundu ? "text-gray-600" : "text-gray-900 font-medium"}`}>
                      {notif.mesaj}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {formatRelativeTime(notif.olusturma)}
                    </p>
                  </div>
                  {!notif.okundu && (
                    <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1" />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

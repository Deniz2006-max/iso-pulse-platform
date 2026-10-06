/**
 * Bildirim Sistemi API İstemcisi
 */
import { NotificationSummary } from "@/types/tasks";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const NOTIF_BASE = `${BASE_URL}/api/v1/hr/notifications`;

async function notifFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${NOTIF_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API hatası");
  }
  return res.json() as Promise<T>;
}

// ── Kullanıcının bildirimleri ────────────────────────────────────────────────
export const fetchNotifications = (
  userId: string,
  sadece_okunmamis = false,
  limit = 20,
): Promise<NotificationSummary> => {
  const params = new URLSearchParams({
    sadece_okunmamis: String(sadece_okunmamis),
    limit: String(limit),
  });
  return notifFetch(`/${userId}?${params}`);
};

// ── Bildirimi okundu işaretle ─────────────────────────────────────────────────
export const markNotificationRead = (notificationId: string): Promise<{ ok: boolean }> =>
  notifFetch(`/${notificationId}/read`, { method: "PATCH" });

// ── Tümünü okundu işaretle ───────────────────────────────────────────────────
export const markAllNotificationsRead = (userId: string): Promise<{ ok: boolean }> =>
  notifFetch(`/${userId}/read-all`, { method: "PATCH" });

// ── Yeni bildirim oluştur ────────────────────────────────────────────────────
export const createNotification = (payload: {
  user_id: string;
  tur: string;
  mesaj: string;
  ilgili_leave_id?: string;
  ilgili_task_id?: string;
}): Promise<unknown> =>
  notifFetch("/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

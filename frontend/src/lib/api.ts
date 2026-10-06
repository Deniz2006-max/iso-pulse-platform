/**
 * İSO Pulse API İstemcisi
 * Tüm HTTP çağrıları bu dosyadan geçer.
 */
import {
  IzinTuruBilgi, LeaveBalance, LeaveRequest,
  LeaveRequestCreate, ManagerDecision, EmployeeLeaveOverview,
} from "@/types/leave";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HR_BASE = `${BASE_URL}/api/v1/hr/leave`;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${HR_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API hatası");
  }
  return res.json() as Promise<T>;
}

// ── İzin Türleri ────────────────────────────────────────────────────────────
export const fetchIzinTurleri = (): Promise<IzinTuruBilgi[]> =>
  apiFetch("/types");

// ── Bakiye ──────────────────────────────────────────────────────────────────
export const fetchBalance = (employeeId: string, yil = 2026): Promise<LeaveBalance> =>
  apiFetch(`/balance/${employeeId}?yil=${yil}`);

// ── Talep oluşturma ─────────────────────────────────────────────────────────
export const createLeaveRequest = (
  employeeId: string,
  data: LeaveRequestCreate,
): Promise<LeaveRequest> =>
  apiFetch(`/request/${employeeId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// ── Çalışanın talepleri ─────────────────────────────────────────────────────
export const fetchEmployeeRequests = (
  employeeId: string,
  yil?: number,
): Promise<LeaveRequest[]> =>
  apiFetch(`/requests/${employeeId}${yil ? `?yil=${yil}` : ""}`);

// ── Talep iptali ─────────────────────────────────────────────────────────────
export const cancelRequest = (
  talepId: string,
  employeeId: string,
): Promise<LeaveRequest> =>
  apiFetch(`/request/${talepId}/cancel?employee_id=${employeeId}`, { method: "PATCH" });

// ── Çalışan özeti ─────────────────────────────────────────────────────────────
export const fetchOverview = (
  employeeId: string,
  yil = 2026,
): Promise<EmployeeLeaveOverview> =>
  apiFetch(`/overview/${employeeId}?yil=${yil}`);

// ── Yönetici: bekleyenler ─────────────────────────────────────────────────────
export const fetchPendingRequests = (yoneticiId: string): Promise<LeaveRequest[]> =>
  apiFetch(`/manager/${yoneticiId}/pending`);

// ── Yönetici: tüm ekip talepleri (geçmiş dahil) ───────────────────────────────
export const fetchManagerAllRequests = (
  yoneticiId: string,
  yil?: number,
): Promise<LeaveRequest[]> =>
  apiFetch(`/manager/${yoneticiId}/all${yil ? `?yil=${yil}` : ""}`);

// ── Yönetici kararı ───────────────────────────────────────────────────────────
export const submitManagerDecision = (
  yoneticiId: string,
  talepId: string,
  karar: ManagerDecision,
): Promise<LeaveRequest> =>
  apiFetch(`/manager/${yoneticiId}/decide/${talepId}`, {
    method: "POST",
    body: JSON.stringify(karar),
  });

// ── HR: tüm talepler ──────────────────────────────────────────────────────────
export const fetchAllRequests = (
  durum?: string,
  yil?: number,
): Promise<LeaveRequest[]> => {
  const params = new URLSearchParams();
  if (durum) params.set("durum", durum);
  if (yil) params.set("yil", String(yil));
  return apiFetch(`/hr/all-requests?${params}`);
};

// ── Çalışan listesi ───────────────────────────────────────────────────────────
export interface EmployeeListItem {
  id: string;
  ad_soyad: string;
  sube: string | null;
  ise_giris_tarihi: string;
  dogum_tarihi: string | null;
  is_hr: boolean;
  is_yonetici: boolean;
}

const EMP_BASE = `${BASE_URL}/api/v1/hr/employees`;

export const fetchEmployees = (): Promise<EmployeeListItem[]> =>
  fetch(EMP_BASE).then((r) => (r.ok ? r.json() : [])).catch(() => []);

// ── İzin Belgeleri ────────────────────────────────────────────────────────────
export interface LeaveDocument {
  id: string;
  leave_request_id: string;
  belge_turu: string;
  dosya_adi: string;
  yuklenme_tarihi: string;
}

export async function uploadLeaveDocument(
  talepId: string,
  file: File,
): Promise<LeaveDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${HR_BASE}/document/${talepId}/upload`, {
    method: "POST",
    body: formData,
    // Content-Type header'ı set etme — browser multipart boundary'yi kendisi ekler
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Yükleme hatası");
  }
  return res.json();
}

export async function fetchLeaveDocuments(talepId: string): Promise<LeaveDocument[]> {
  try {
    const res = await fetch(`${HR_BASE}/document/${talepId}`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

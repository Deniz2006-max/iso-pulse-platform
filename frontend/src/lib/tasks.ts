/**
 * Görev Yönetimi API İstemcisi
 */
import { Task, LeaveConflictInfo, AuditLog } from "@/types/tasks";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TASKS_BASE = `${BASE_URL}/api/v1/hr/tasks`;

async function taskFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${TASKS_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API hatası");
  }
  return res.json() as Promise<T>;
}

// ── Çalışanın görevleri ─────────────────────────────────────────────────────
export const fetchEmployeeTasks = (
  employeeId: string,
  durum?: string,
): Promise<Task[]> => {
  const params = durum ? `?durum=${durum}` : "";
  return taskFetch(`/employee/${employeeId}${params}`);
};

// ── Yöneticinin ekip görevleri ───────────────────────────────────────────────
export const fetchManagerTasks = (
  yoneticiId: string,
  filters?: { durum?: string; oncelik?: string; employee_id?: string },
): Promise<Task[]> => {
  const params = new URLSearchParams();
  if (filters?.durum) params.set("durum", filters.durum);
  if (filters?.oncelik) params.set("oncelik", filters.oncelik);
  if (filters?.employee_id) params.set("employee_id", filters.employee_id);
  const qs = params.toString() ? `?${params}` : "";
  return taskFetch(`/manager/${yoneticiId}${qs}`);
};

// ── Görev detayı ─────────────────────────────────────────────────────────────
export const fetchTask = (taskId: string): Promise<Task> =>
  taskFetch(`/${taskId}`);

// ── Görev oluştur (yönetici) ─────────────────────────────────────────────────
export const createTask = (
  yoneticiId: string,
  data: {
    baslik: string;
    aciklama?: string;
    oncelik: string;
    bitis_tarihi: string;
    employee_id: string;
  },
): Promise<Task> =>
  taskFetch(`/manager/${yoneticiId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// ── Durum güncelle ───────────────────────────────────────────────────────────
export const updateTaskStatus = (
  taskId: string,
  yapanId: string,
  yeniDurum: string,
  retNotu?: string,
): Promise<Task> => {
  const params = new URLSearchParams({ yeni_durum: yeniDurum, yapan_id: yapanId });
  if (retNotu) params.set("ret_notu", retNotu);
  return taskFetch(`/${taskId}/status?${params}`, { method: "PATCH" });
};

// ── Görev devret ─────────────────────────────────────────────────────────────
export const reassignTask = (
  taskId: string,
  devirEdenId: string,
  yeniEmployeeId: string,
  sebep?: string,
): Promise<Task> =>
  taskFetch(`/${taskId}/reassign?devir_eden_id=${devirEdenId}`, {
    method: "POST",
    body: JSON.stringify({ yeni_employee_id: yeniEmployeeId, sebep }),
  });

// ── İzin çakışma kontrolü ────────────────────────────────────────────────────
export const checkLeaveConflicts = (
  employeeId: string,
  leaveStart: string,
  leaveEnd: string,
  izinTuru: string,
): Promise<LeaveConflictInfo> => {
  const params = new URLSearchParams({
    employee_id: employeeId,
    leave_start: leaveStart,
    leave_end: leaveEnd,
    izin_turu: izinTuru,
  });
  return taskFetch(`/conflicts/check?${params}`);
};

// ── Denetim kaydı ────────────────────────────────────────────────────────────
export const fetchAuditLog = (taskId: string): Promise<AuditLog[]> =>
  taskFetch(`/${taskId}/audit`);

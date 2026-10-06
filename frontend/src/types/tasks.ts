/**
 * Görev Yönetimi — TypeScript Tipleri
 */

export type TaskPriority = "yuksek" | "orta" | "dusuk";
export type TaskStatus =
  | "atandi"
  | "devam_ediyor"
  | "teslim_edildi"
  | "onay_bekliyor"
  | "tamamlandi";

export interface Task {
  id: string;
  baslik: string;
  aciklama: string | null;
  oncelik: TaskPriority;
  durum: TaskStatus;
  bitis_tarihi: string; // ISO date
  employee_id: string;
  yonetici_id: string;
  teslim_edildi_at: string | null;
  tamamlandi_at: string | null;
  ret_notu: string | null;
  olusturma: string;
  guncelleme: string;
  // JOIN ile gelen alanlar
  calisan_adi?: string;
  yonetici_adi?: string;
}

export interface TaskConflict {
  task_id: string;
  baslik: string;
  bitis_tarihi: string;
  oncelik: TaskPriority;
}

export interface LeaveConflictInfo {
  employee_id: string;
  leave_start: string;
  leave_end: string;
  cakisan_gorevler: TaskConflict[];
  ozel_izin: boolean;
}

export interface AuditLog {
  id: string;
  task_id: string;
  eylem: string;
  yapan_id: string | null;
  eski_deger: string | null;
  yeni_deger: string | null;
  olusturma: string;
}

export interface Notification {
  id: string;
  user_id: string;
  tur: string;
  ilgili_task_id: string | null;
  ilgili_leave_id: string | null;
  mesaj: string;
  okundu: boolean;
  olusturma: string;
}

export interface NotificationSummary {
  okunmamis_sayi: number;
  bildirimler: Notification[];
}

// UI sabitler
export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  yuksek: "Yüksek",
  orta: "Orta",
  dusuk: "Düşük",
};

export const PRIORITY_COLORS: Record<TaskPriority, string> = {
  yuksek: "bg-red-100 text-red-700 border-red-200",
  orta: "bg-amber-100 text-amber-700 border-amber-200",
  dusuk: "bg-green-100 text-green-700 border-green-200",
};

export const PRIORITY_DOT: Record<TaskPriority, string> = {
  yuksek: "bg-red-500",
  orta: "bg-amber-500",
  dusuk: "bg-green-500",
};

export const STATUS_LABELS: Record<TaskStatus, string> = {
  atandi: "Atandı",
  devam_ediyor: "Devam Ediyor",
  teslim_edildi: "Teslim Edildi",
  onay_bekliyor: "Onay Bekliyor",
  tamamlandi: "Tamamlandı",
};

export const STATUS_COLORS: Record<TaskStatus, string> = {
  atandi: "bg-gray-100 text-gray-600",
  devam_ediyor: "bg-blue-100 text-blue-700",
  teslim_edildi: "bg-purple-100 text-purple-700",
  onay_bekliyor: "bg-amber-100 text-amber-700",
  tamamlandi: "bg-green-100 text-green-700",
};

// İzin modülü TypeScript tipleri

export type IzinTuru =
  | "yillik"
  | "2saat"
  | "2saat_uzeri"
  | "evlilik"
  | "olum"
  | "baba_dogum"
  | "dogum_kadin"
  | "ucretsiz"
  | "hastalik"
  | "idari";

export type IzinDurum = "beklemede" | "onaylandi" | "reddedildi" | "iptal";

export interface IzinTuruBilgi {
  kod: IzinTuru;
  label: string;
  aciklama: string;
  max_gun: number | null;
  bakiyeden_dusuler: boolean;
}

export interface LeaveBalance {
  employee_id: string;
  yil: number;
  onceki_yildan: number;
  yillik_hak: number;
  idari_eklenen: number;
  kullanilan: number;
  bakiye: number;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  izin_turu: IzinTuru;
  cikis_tarihi: string;  // "YYYY-MM-DD"
  giris_tarihi: string;
  sure_gun: number | null;
  neden: string | null;
  durum: IzinDurum;
  ret_nedeni: string | null;
  yonetici_id: string | null;
  olusturma: string;
  guncelleme: string;
}

export interface LeaveRequestCreate {
  izin_turu: IzinTuru;
  cikis_tarihi: string;
  giris_tarihi: string;
  neden?: string;
}

export interface ManagerDecision {
  durum: "onaylandi" | "reddedildi";
  ret_nedeni?: string;
}

export interface EmployeeLeaveOverview {
  employee_id: string;
  ad_soyad: string;
  bakiye: LeaveBalance;
  son_talepler: LeaveRequest[];
}

export const DURUM_LABELS: Record<IzinDurum, string> = {
  beklemede: "Beklemede",
  onaylandi: "Onaylandı",
  reddedildi: "Reddedildi",
  iptal: "İptal",
};

export const DURUM_COLORS: Record<IzinDurum, string> = {
  beklemede: "bg-yellow-100 text-yellow-800",
  onaylandi: "bg-green-100 text-green-800",
  reddedildi: "bg-red-100 text-red-800",
  iptal: "bg-gray-100 text-gray-600",
};

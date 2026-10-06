/**
 * Kutlama API İstemcisi
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface CelebrationItem {
  employee_id: string;
  ad_soyad: string;
  sube: string;
  tur: "dogum_gunu" | "yil_donumu";
  tarih: string;
  kac_gun_sonra: number;
  kac_yil: number | null;
}

export async function fetchCelebrations(gunAralik = 7): Promise<CelebrationItem[]> {
  const res = await fetch(
    `${BASE_URL}/api/v1/hr/celebrations/today?gun_aralik=${gunAralik}`,
  );
  if (!res.ok) throw new Error("Kutlamalar alınamadı");
  return res.json();
}

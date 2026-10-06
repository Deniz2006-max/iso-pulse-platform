"use client";
/**
 * Kutlama Kartı — Dashboard'da gösterilir
 * Önümüzdeki 7 gün içindeki doğum günü ve işe giriş yıldönümleri
 */
import { useEffect, useState } from "react";
import { fetchCelebrations, CelebrationItem } from "@/lib/celebrations";

const TUR_ICON: Record<string, string> = {
  dogum_gunu: "🎂",
  yil_donumu: "🏆",
};

const TUR_LABEL: Record<string, string> = {
  dogum_gunu: "Doğum Günü",
  yil_donumu: "İşe Giriş Yıldönümü",
};

function gunLabel(kacGunSonra: number): string {
  if (kacGunSonra === 0) return "Bugün! 🎉";
  if (kacGunSonra === 1) return "Yarın";
  return `${kacGunSonra} gün sonra`;
}

export default function CelebrationCard() {
  const [items, setItems] = useState<CelebrationItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCelebrations(7)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-3" />
        <div className="space-y-2">
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
        </div>
      </div>
    );
  }

  if (items.length === 0) return null;

  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 mt-6">
      <h3 className="text-sm font-semibold text-amber-800 mb-3 flex items-center gap-2">
        🎊 Yaklaşan Kutlamalar
      </h3>
      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={`${item.employee_id}-${item.tur}`}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 ${
              item.kac_gun_sonra === 0
                ? "bg-amber-200 border border-amber-300"
                : "bg-white border border-amber-100"
            }`}
          >
            <span className="text-xl">{TUR_ICON[item.tur]}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {item.ad_soyad}
              </p>
              <p className="text-xs text-gray-500">
                {item.sube} ·{" "}
                {item.tur === "yil_donumu" && item.kac_yil
                  ? `${item.kac_yil}. ${TUR_LABEL[item.tur]}`
                  : TUR_LABEL[item.tur]}
              </p>
            </div>
            <span
              className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                item.kac_gun_sonra === 0
                  ? "bg-amber-600 text-white"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {gunLabel(item.kac_gun_sonra)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

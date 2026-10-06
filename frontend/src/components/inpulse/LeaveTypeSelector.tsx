"use client";
import { IzinTuruBilgi, IzinTuru } from "@/types/leave";

const ICONS: Record<string, string> = {
  yillik: "🏖️",
  "2saat": "⏰",
  "2saat_uzeri": "🕐",
  evlilik: "💍",
  olum: "🕯️",
  baba_dogum: "👶",
  dogum_kadin: "🤱",
  ucretsiz: "📋",
  hastalik: "🏥",
  idari: "🏢",
};

interface Props {
  izinTurleri: IzinTuruBilgi[];
  selected: IzinTuru | null;
  onSelect: (tur: IzinTuru) => void;
}

export default function LeaveTypeSelector({ izinTurleri, selected, onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {izinTurleri.map((tur) => (
        <button
          key={tur.kod}
          onClick={() => onSelect(tur.kod)}
          className={`flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all
            ${
              selected === tur.kod
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 bg-white hover:border-blue-300 hover:bg-gray-50"
            }`}
        >
          <span className="text-2xl mt-0.5">{ICONS[tur.kod] ?? "📄"}</span>
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 text-sm">{tur.label}</p>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{tur.aciklama}</p>
            {tur.max_gun && (
              <span className="inline-block mt-1 text-xs bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">
                Maks. {tur.max_gun} gün
              </span>
            )}
            {tur.bakiyeden_dusuler && (
              <span className="inline-block mt-1 ml-1 text-xs bg-orange-100 text-orange-700 rounded px-1.5 py-0.5">
                Bakiyeden düşer
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

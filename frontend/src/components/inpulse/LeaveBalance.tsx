"use client";
import { LeaveBalance as LB } from "@/types/leave";

interface Props {
  balance: LB;
}

export default function LeaveBalanceCard({ balance }: Props) {
  // API'den gelen değerler string olabilir (Decimal) — Number() ile güvenli dönüştür
  const onceki   = Number(balance.onceki_yildan)  || 0;
  const hak      = Number(balance.yillik_hak)      || 0;
  const idari    = Number(balance.idari_eklenen)   || 0;
  const kullanil = Number(balance.kullanilan)      || 0;
  const bakiye   = Number(balance.bakiye)          || 0;
  const toplam   = hak + onceki + idari;

  const items = [
    { label: "Önceki Yıldan", value: onceki,   color: "text-blue-600" },
    { label: "Yıllık Hak",    value: hak,      color: "text-green-600" },
    { label: "İdari Eklenen", value: idari,    color: "text-purple-600" },
    { label: "Kullanılan",    value: kullanil, color: "text-orange-600" },
  ];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          {balance.yil} İzin Bakiyesi
        </h3>
        <div className="text-right">
          <span className="text-3xl font-bold text-gray-900">{bakiye.toFixed(1)}</span>
          <span className="text-sm text-gray-500 ml-1">gün</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <div key={item.label} className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">{item.label}</p>
            <p className={`text-lg font-semibold ${item.color}`}>
              {item.value.toFixed(1)}
            </p>
          </div>
        ))}
      </div>

      {/* Bakiye çubuğu */}
      <div className="mt-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Kullanım oranı</span>
          <span>
            {toplam > 0 ? `${Math.round((kullanil / toplam) * 100)}%` : "—"}
          </span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all"
            style={{ width: `${toplam > 0 ? Math.min(100, (kullanil / toplam) * 100) : 0}%` }}
          />
        </div>
      </div>
    </div>
  );
}

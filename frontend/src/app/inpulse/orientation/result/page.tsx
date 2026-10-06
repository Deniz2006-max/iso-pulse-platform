"use client";
/**
 * Oryantasyon — Adım 4: Sonuç Ekranı
 * Quiz skoru gösterilir, çalışan platforma yönlendirilir.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";

interface OryantasyonSonucu {
  dogru: number;
  toplam: number;
  puan: number;
}

function ScoreCircle({ puan }: { puan: number }) {
  const renk =
    puan >= 80 ? "text-emerald-600" : puan >= 50 ? "text-amber-500" : "text-red-500";
  const halka =
    puan >= 80 ? "stroke-emerald-500" : puan >= 50 ? "stroke-amber-400" : "stroke-red-400";
  const r = 52;
  const cevre = 2 * Math.PI * r;
  const dolu = (puan / 100) * cevre;

  return (
    <div className="relative w-36 h-36 mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#e5e7eb" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          className={halka}
          strokeWidth="10"
          strokeDasharray={`${dolu} ${cevre - dolu}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-3xl font-bold ${renk}`}>{puan}</span>
        <span className="text-xs text-gray-400">/ 100</span>
      </div>
    </div>
  );
}

export default function OrientationResultPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getCurrentUser>>(null);
  const [sonuc, setSonuc] = useState<OryantasyonSonucu | null>(null);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!u.isNewEmployee) { router.replace("/hub"); return; }
    setUser(u);

    const raw = sessionStorage.getItem("orientation_result");
    if (!raw) {
      router.replace("/inpulse/orientation/quiz");
      return;
    }
    setSonuc(JSON.parse(raw));
  }, [router]);

  if (!user || !sonuc) return null;

  const { dogru, toplam, puan } = sonuc;
  const basarili = puan >= 60;
  const mesaj = puan >= 80
    ? "Mükemmel! Harika bir başlangıç yaptınız. 🎉"
    : puan >= 60
    ? "Tebrikler! Oryantasyonu başarıyla tamamladınız. ✓"
    : "Oryantasyon tamamlandı. İK ile iletişime geçebilirsiniz.";

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex flex-col items-center justify-center px-4 py-10">
      {/* İlerleme adımları */}
      <div className="flex items-center justify-center gap-2 mb-8">
        {["Kayıt", "Video", "Quiz", "Sonuç"].map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-emerald-600 text-white">
              ✓
            </div>
            <span className="text-xs hidden sm:block text-emerald-700 font-semibold">{step}</span>
            {i < 3 && <span className="text-emerald-300 text-xs">›</span>}
          </div>
        ))}
      </div>

      <div className="w-full max-w-md">
        {/* Başlık */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Oryantasyon Tamamlandı!</h1>
          <p className="text-sm text-gray-500 mt-1">{user.name}</p>
        </div>

        {/* Skor kartı */}
        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8 text-center mb-5">
          <ScoreCircle puan={puan} />

          <p className={`font-semibold text-base mt-4 ${
            puan >= 80 ? "text-emerald-700" : puan >= 60 ? "text-amber-600" : "text-red-600"
          }`}>
            {mesaj}
          </p>

          <div className="flex justify-center gap-6 mt-5 text-sm">
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900">{dogru}</p>
              <p className="text-xs text-gray-400 mt-0.5">Doğru</p>
            </div>
            <div className="w-px bg-gray-100" />
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900">{toplam - dogru}</p>
              <p className="text-xs text-gray-400 mt-0.5">Yanlış</p>
            </div>
            <div className="w-px bg-gray-100" />
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900">{toplam}</p>
              <p className="text-xs text-gray-400 mt-0.5">Toplam</p>
            </div>
          </div>

          {/* İK bildirimi */}
          <div className="mt-5 bg-blue-50 border border-blue-100 rounded-xl p-3 text-left">
            <p className="text-xs text-blue-700 font-semibold mb-1">📩 İK'ya İletildi</p>
            <p className="text-xs text-blue-600">
              Oryantasyon sonuçlarınız İnsan Kaynakları birimine otomatik olarak iletildi.
              Sorularınız için İK ile platform üzerinden iletişime geçebilirsiniz.
            </p>
          </div>
        </div>

        {/* Aksiyonlar */}
        <div className="space-y-2">
          <button
            onClick={() => { window.location.href = "/inpulse"; }}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl
                       font-semibold text-sm transition-colors"
          >
            İSO Pulse'a Giriş Yap →
          </button>
          {!basarili && (
            <button
              onClick={() => { window.location.href = "/inpulse/orientation/quiz"; }}
              className="w-full py-3 bg-white border-2 border-gray-200 hover:bg-gray-50 text-gray-700
                         rounded-xl font-medium text-sm transition-colors"
            >
              Quizi Tekrar Dene
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

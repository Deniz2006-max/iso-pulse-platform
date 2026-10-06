"use client";
/**
 * Oryantasyon — Adım 3: Quiz
 * 6 soruluk oryantasyon sınavı.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser } from "@/lib/auth";

interface Soru {
  soru: string;
  secenekler: string[];
  dogru: number; // 0-indexed
  aciklama: string;
}

const SORULAR: Soru[] = [
  {
    soru: "İSO Pulse platformunda 'İnpulse' modülü ne için kullanılır?",
    secenekler: [
      "Mevzuat takibi ve yasal düzenlemeleri izlemek için",
      "Çalışan izin yönetimi, görev takibi ve oryantasyon için",
      "Dış müşteri ilişkilerini yönetmek için",
      "Finansal raporları düzenlemek için",
    ],
    dogru: 1,
    aciklama: "İnpulse, çalışanların izin taleplerini yönettiği, görevlerini takip ettiği ve oryantasyon süreçlerini tamamladığı iç kanal modülüdür.",
  },
  {
    soru: "Yıllık izin talebini onaya göndermeden önce hangi bilgileri girmeniz gerekir?",
    secenekler: [
      "Yalnızca çıkış tarihi yeterlidir",
      "İzin türü, çıkış tarihi ve giriş tarihi",
      "Sadece izin süresi (gün sayısı)",
      "İzin türü ve neden alanı zorunludur",
    ],
    dogru: 1,
    aciklama: "İzin talebi oluştururken izin türü, çıkış tarihi ve giriş tarihi zorunlu alanlardır. Neden alanı isteğe bağlıdır.",
  },
  {
    soru: "Hastalık izni için sistemde hangi ek adım gereklidir?",
    secenekler: [
      "Ek adım gerekmez, standart izin gibi işlenir",
      "Doktor raporu belgesi yüklenmesi gerekir",
      "Yöneticiye ayrıca e-posta gönderilmesi gerekir",
      "Hastalık izninde onay beklenmez, otomatik onaylanır",
    ],
    dogru: 1,
    aciklama: "Hastalık izninde (ücretsiz hastalik türü) sistemde belge yükleme ekranı açılır ve doktor raporunun yüklenmesi beklenir.",
  },
  {
    soru: "Özel izin türlerinde (ölüm, doğum, hastalık) görev çakışması olduğunda yönetici ne yapabilir?",
    secenekler: [
      "İzni otomatik reddeder",
      "Çakışan görevleri başka bir çalışana devredebilir",
      "İzin süresini kısaltır",
      "Görevlerin durumunu 'dondurulmuş' olarak işaretler",
    ],
    dogru: 1,
    aciklama: "Yönetici onay panelinde, özel izin türlerinde çakışan görevleri başka bir ekip üyesine devredebilir. Bu, izin sürecini engellemeden iş akışının sürmesini sağlar.",
  },
  {
    soru: "İSO Pulse'ta bildirimler nasıl takip edilir?",
    secenekler: [
      "Sadece e-posta ile bildirim gönderilir",
      "Üst çubukta zil ikonuna tıklayarak platformda görüntülenir",
      "Bildirimler yalnızca yöneticilere iletilir",
      "Bildirimler haftalık özet olarak gönderilir",
    ],
    dogru: 1,
    aciklama: "İSO Pulse'ta tüm bildirimler (izin onayı, görev ataması vb.) platform içi bildirim merkezi üzerinden zil ikonu ile takip edilir.",
  },
  {
    soru: "İSO Pulse'ta 'Outpulse' modülü ne işlevi görür?",
    secenekler: [
      "Çalışan maaş bordrosu hesaplamaları için",
      "Resmi Gazete, SGK ve mevzuat güncellemelerini izlemek için",
      "Müşteri şikayetlerini kayıt altına almak için",
      "Toplantı odası rezervasyonları için",
    ],
    dogru: 1,
    aciklama: "Outpulse modülü, Resmi Gazete, Mevzuat.gov.tr, SGK ve ÇSGB gibi kaynaklardan yasal ve mevzuat güncellemelerini otomatik takip eder ve İK ekibini bilgilendirir.",
  },
];

export default function OrientationQuizPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getCurrentUser>>(null);
  const [aktif, setAktif] = useState(0);
  const [secilen, setSecilen] = useState<number | null>(null);
  const [cevaplar, setCevaplar] = useState<(number | null)[]>(new Array(SORULAR.length).fill(null));
  const [gosterAciklama, setGosterAciklama] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!u.isNewEmployee) { router.replace("/hub"); return; }
    setUser(u);
  }, [router]);

  const soruSayisi = SORULAR.length;
  const sonSoru = aktif === soruSayisi - 1;
  const dogru = cevaplar.filter((c, i) => c === SORULAR[i].dogru).length;

  function handleSecim(idx: number) {
    if (secilen !== null) return; // cevap verilmişse değiştirme
    setSecilen(idx);
    const yeniCevaplar = [...cevaplar];
    yeniCevaplar[aktif] = idx;
    setCevaplar(yeniCevaplar);
    setGosterAciklama(true);
  }

  function handleIleri() {
    if (!sonSoru) {
      setAktif((a) => a + 1);
      setSecilen(cevaplar[aktif + 1]);
      setGosterAciklama(cevaplar[aktif + 1] !== null);
    } else {
      handleBitir();
    }
  }

  async function handleBitir() {
    if (!user) return;
    setSubmitting(true);

    const sonDogru = cevaplar.filter((c, i) => c === SORULAR[i].dogru).length;
    const puan = Math.round((sonDogru / soruSayisi) * 100);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      await fetch(`${API_BASE}/api/v1/hr/orientation/results`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: user.id,
          dogru_sayisi: sonDogru,
          toplam_soru: soruSayisi,
          puan,
        }),
      });
    } catch {
      // Hata olursa sonuç sayfasına yine de git
    }

    // Sonuçları sessionStorage'a yaz
    sessionStorage.setItem(
      "orientation_result",
      JSON.stringify({ dogru: sonDogru, toplam: soruSayisi, puan }),
    );
    window.location.href = "/inpulse/orientation/result";
  }

  if (!user) return null;

  const soru = SORULAR[aktif];
  const dogruMu = secilen === soru.dogru;

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 py-8">
      {/* İlerleme adımları */}
      <div className="flex items-center justify-center gap-2 mb-6">
        {["Kayıt", "Video", "Quiz", "Sonuç"].map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                ${i < 2
                  ? "bg-emerald-600 text-white"
                  : i === 2
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-400"}`}
            >
              {i < 2 ? "✓" : i + 1}
            </div>
            <span className={`text-xs hidden sm:block ${i === 2 ? "text-blue-700 font-semibold" : i < 2 ? "text-emerald-700" : "text-gray-400"}`}>
              {step}
            </span>
            {i < 3 && <span className="text-gray-300 text-xs">›</span>}
          </div>
        ))}
      </div>

      <div className="w-full max-w-lg">
        {/* Quiz ilerleme */}
        <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
          <span>Soru {aktif + 1} / {soruSayisi}</span>
          <span>{cevaplar.filter(Boolean).length} yanıtlandı</span>
        </div>
        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden mb-6">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${((aktif + 1) / soruSayisi) * 100}%` }}
          />
        </div>

        {/* Soru kartı */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-md p-6 mb-4">
          <p className="font-semibold text-gray-900 text-sm leading-relaxed mb-5">
            {soru.soru}
          </p>

          <div className="space-y-2.5">
            {soru.secenekler.map((s, i) => {
              let cls = "border-gray-200 hover:border-blue-300 hover:bg-blue-50";
              if (secilen !== null) {
                if (i === soru.dogru) cls = "border-green-400 bg-green-50";
                else if (i === secilen && !dogruMu) cls = "border-red-400 bg-red-50";
                else cls = "border-gray-100 bg-gray-50 opacity-60";
              }

              return (
                <button
                  key={i}
                  onClick={() => handleSecim(i)}
                  disabled={secilen !== null}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 text-left
                              text-sm transition-all ${cls}`}
                >
                  <span
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 text-xs font-bold
                      ${secilen === null
                        ? "border-gray-300 text-gray-400"
                        : i === soru.dogru
                        ? "border-green-500 bg-green-500 text-white"
                        : i === secilen
                        ? "border-red-500 bg-red-500 text-white"
                        : "border-gray-300 text-gray-300"}`}
                  >
                    {secilen !== null
                      ? i === soru.dogru ? "✓" : i === secilen ? "✕" : String.fromCharCode(65 + i)
                      : String.fromCharCode(65 + i)}
                  </span>
                  <span className="text-gray-800">{s}</span>
                </button>
              );
            })}
          </div>

          {/* Açıklama */}
          {gosterAciklama && (
            <div
              className={`mt-4 rounded-xl p-3 text-xs leading-relaxed
                ${dogruMu ? "bg-green-50 text-green-800 border border-green-200" : "bg-blue-50 text-blue-800 border border-blue-200"}`}
            >
              <span className="font-semibold">{dogruMu ? "✓ Doğru! " : "ℹ️ Açıklama: "}</span>
              {soru.aciklama}
            </div>
          )}
        </div>

        {/* Devam butonu */}
        <button
          onClick={handleIleri}
          disabled={secilen === null || submitting}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl
                     font-semibold text-sm transition-colors disabled:opacity-40"
        >
          {submitting
            ? "Sonuçlar kaydediliyor…"
            : sonSoru
            ? "Quizi Tamamla ✓"
            : "Sonraki Soru →"}
        </button>
      </div>
    </main>
  );
}

"use client";
/**
 * Çalışan Profil Sayfası — İSO Pulse
 * Tüm roller için erişilebilir. Doğum günü / yıldönümü kutlama butonu içerir.
 */
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { getCurrentUser, MockUser } from "@/lib/auth";
import NotificationBell from "@/components/inpulse/NotificationBell";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Employee {
  id: string;
  ad_soyad: string;
  sube: string | null;
  ise_giris_tarihi: string;
  dogum_tarihi: string | null;
  is_hr: boolean;
  is_yonetici: boolean;
  email: string | null;
  aktif: boolean;
}

type KutlamaTur = "dogum_gunu" | "yil_donumu" | "genel";

function dayOfYear(dateStr: string): { month: number; day: number } {
  const d = new Date(dateStr);
  return { month: d.getMonth() + 1, day: d.getDate() };
}

function todayMD() {
  const t = new Date();
  return { month: t.getMonth() + 1, day: t.getDate() };
}

function daysUntil(dateStr: string): number {
  const today = new Date();
  const d = new Date(dateStr);
  let target = new Date(today.getFullYear(), d.getMonth(), d.getDate());
  if (target < today) target = new Date(today.getFullYear() + 1, d.getMonth(), d.getDate());
  return Math.round((target.getTime() - today.setHours(0, 0, 0, 0)) / 86400000);
}

function roleBadge(emp: Employee): string {
  if (emp.is_hr) return "İnsan Kaynakları";
  if (emp.is_yonetici) return "Yönetici";
  return "Çalışan";
}

function roleColor(emp: Employee): string {
  if (emp.is_hr) return "bg-emerald-100 text-emerald-700";
  if (emp.is_yonetici) return "bg-violet-100 text-violet-700";
  return "bg-blue-100 text-blue-700";
}

function avatarInitials(ad_soyad: string): string {
  return ad_soyad
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

function yilFarki(start: string): number {
  const today = new Date();
  const s = new Date(start);
  let years = today.getFullYear() - s.getFullYear();
  if (
    today.getMonth() < s.getMonth() ||
    (today.getMonth() === s.getMonth() && today.getDate() < s.getDate())
  )
    years--;
  return years;
}

export default function ProfilePage() {
  const router = useRouter();
  const params = useParams();
  const empId = params?.id as string;

  const [user, setUser] = useState<MockUser | null>(null);
  const [emp, setEmp] = useState<Employee | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTur, setModalTur] = useState<KutlamaTur>("genel");
  const [modalMesaj, setModalMesaj] = useState("");
  const [sending, setSending] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [bildirimOk, setBildirimOk] = useState(false);
  const [emailOk, setEmailOk] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    setUser(u);
  }, [router]);

  useEffect(() => {
    if (!empId) return;
    fetch(`${API}/api/v1/hr/employees/${empId}`)
      .then((r) => { if (!r.ok) throw new Error("Çalışan bulunamadı"); return r.json(); })
      .then(setEmp)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [empId]);

  // Kutlama durumu hesapla
  const today = todayMD();
  const isBirthday =
    emp?.dogum_tarihi &&
    dayOfYear(emp.dogum_tarihi).month === today.month &&
    dayOfYear(emp.dogum_tarihi).day === today.day;
  const isAnniversary =
    emp &&
    dayOfYear(emp.ise_giris_tarihi).month === today.month &&
    dayOfYear(emp.ise_giris_tarihi).day === today.day &&
    new Date(emp.ise_giris_tarihi).getFullYear() !== new Date().getFullYear();

  const birthdayDays = emp?.dogum_tarihi ? daysUntil(emp.dogum_tarihi) : null;
  const anniversaryDays = emp ? daysUntil(emp.ise_giris_tarihi) : null;

  function openModal(tur: KutlamaTur) {
    if (!emp || !user) return;
    setModalTur(tur);
    setBildirimOk(false);
    setEmailOk(false);
    setSendError(null);
    const ad = emp.ad_soyad.split(" ")[0];
    if (tur === "dogum_gunu") {
      setModalMesaj(`🎂 Doğum günün kutlu olsun, ${ad}! Sağlık, mutluluk ve başarılar dilerim. 🎉`);
    } else if (tur === "yil_donumu") {
      const yil = yilFarki(emp.ise_giris_tarihi);
      setModalMesaj(`🏆 ${yil}. iş yılın kutlu olsun, ${ad}! Ekibimize kattığın değer için teşekkürler. 🌟`);
    } else {
      setModalMesaj(`🎉 Merhaba ${ad}! Seni kutlamak istedim. Başarılarının devamını dilerim!`);
    }
    setModalOpen(true);
  }

  async function gonderBildirim() {
    if (!user || !emp) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await fetch(`${API}/api/v1/hr/celebrations/kutla`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hedef_id: emp.id,
          gonderen_id: user.id,
          gonderen_ad: user.name,
          tur: modalTur,
          mesaj: modalMesaj,
        }),
      });
      if (!res.ok) throw new Error("Bildirim gönderilemedi");
      setBildirimOk(true);
    } catch (e: unknown) {
      setSendError(e instanceof Error ? e.message : "Hata oluştu");
    } finally {
      setSending(false);
    }
  }

  async function gonderEmail() {
    if (!user || !emp || !emp.email) return;
    setEmailSending(true);
    setSendError(null);
    try {
      const yil = isAnniversary ? yilFarki(emp.ise_giris_tarihi) : null;
      const res = await fetch(`${API}/api/v1/hr/celebrations/kutla/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hedef_email: emp.email,
          hedef_ad_soyad: emp.ad_soyad,
          gonderen_ad: user.name,
          tur: modalTur,
          mesaj: modalMesaj,
          kac_yil: yil,
        }),
      });
      if (!res.ok) throw new Error("Email gönderilemedi");
      setEmailOk(true);
    } catch (e: unknown) {
      setSendError(e instanceof Error ? e.message : "Hata oluştu");
    } finally {
      setEmailSending(false);
    }
  }

  const isSelf = user?.id === empId;

  // Yeni çalışan kontrolü — işe girişten itibaren 30 gün içinde oryantasyon göster
  function isYeniCalisan(ise_giris: string): boolean {
    const baslangic = new Date(ise_giris);
    const bugun = new Date();
    const farkGun = Math.floor((bugun.getTime() - baslangic.getTime()) / 86400000);
    return farkGun >= 0 && farkGun <= 30;
  }

  // Toplam kıdem
  const kidemYil = emp ? Math.max(0, yilFarki(emp.ise_giris_tarihi)) : 0;
  const kidemAy = emp
    ? (() => {
        const s = new Date(emp.ise_giris_tarihi);
        const n = new Date();
        return (
          (n.getFullYear() - s.getFullYear()) * 12 +
          n.getMonth() -
          s.getMonth() -
          (n.getDate() < s.getDate() ? 1 : 0)
        ) % 12;
      })()
    : 0;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.back()}
              className="text-gray-500 hover:text-gray-800 transition-colors text-sm flex items-center gap-1"
            >
              ← Geri
            </button>
            <div className="w-px h-5 bg-gray-200" />
            <div>
              <h1 className="font-semibold text-gray-900">Çalışan Profili</h1>
              <p className="text-xs text-gray-500">İSO Pulse — İnpulse</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {user && <NotificationBell userId={user.id} />}
          </div>
        </div>
      </header>

      {/* Kendi doğum günü / yıl dönümü — sayfanın en üstünde kutlama bandı */}
      {isSelf && emp && (isBirthday || isAnniversary) && (
        <div className={`w-full py-4 px-6 flex items-center justify-center gap-3 text-white font-semibold text-sm
          ${isBirthday
            ? "bg-gradient-to-r from-purple-600 via-pink-500 to-purple-600"
            : "bg-gradient-to-r from-emerald-600 via-teal-500 to-emerald-600"}`}>
          <span className="text-xl">{isBirthday ? "🎂" : "🏆"}</span>
          <span>
            {isBirthday
              ? `Doğum Günün Kutlu Olsun, ${emp.ad_soyad.split(" ")[0]}! 🎉`
              : `${yilFarki(emp.ise_giris_tarihi)}. Çalışma Yıl Dönümün Kutlu Olsun, ${emp.ad_soyad.split(" ")[0]}! 🌟`}
          </span>
          <span className="text-xl">{isBirthday ? "🎂" : "🏆"}</span>
        </div>
      )}

      <div className="max-w-3xl mx-auto px-6 py-8">
        {loading && (
          <div className="bg-white rounded-2xl border p-12 text-center text-gray-400 animate-pulse">
            Profil yükleniyor…
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
            {error}
          </div>
        )}

        {emp && (
          <>
            {/* Profil kartı */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden mb-6">
              {/* Üst bant */}
              <div className="h-24 bg-gradient-to-r from-blue-600 to-violet-600" />
              <div className="px-6 pb-6">
                {/* Avatar */}
                <div className="-mt-10 mb-4 flex items-end justify-between">
                  <div className="w-20 h-20 rounded-2xl bg-white border-4 border-white shadow-md
                                  flex items-center justify-center text-blue-600 font-bold text-2xl">
                    {avatarInitials(emp.ad_soyad)}
                  </div>
                  {isSelf && (
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                      Bu benim profilim
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">{emp.ad_soyad}</h2>
                    <p className="text-gray-500 mt-0.5">{emp.sube ?? "—"}</p>
                    <span className={`mt-2 inline-block text-xs font-medium px-2.5 py-1 rounded-full ${roleColor(emp)}`}>
                      {roleBadge(emp)}
                    </span>
                  </div>

                  {/* Kutla butonu — kendine gönderme */}
                  {!isSelf && (
                    <div className="flex flex-col gap-2">
                      {(isBirthday || isAnniversary) && (
                        <div className="flex gap-2">
                          {isBirthday && (
                            <button
                              onClick={() => openModal("dogum_gunu")}
                              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700
                                         text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
                            >
                              🎂 Doğum Gününü Kutla
                            </button>
                          )}
                          {isAnniversary && (
                            <button
                              onClick={() => openModal("yil_donumu")}
                              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700
                                         text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
                            >
                              🏆 Yıl Dönümünü Kutla
                            </button>
                          )}
                        </div>
                      )}
                      <button
                        onClick={() => openModal("genel")}
                        className="flex items-center gap-2 bg-white hover:bg-gray-50 text-gray-700
                                   text-sm font-medium px-4 py-2 rounded-xl border border-gray-200
                                   transition-colors"
                      >
                        🎉 Tebrik Gönder
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Bugün kutlama banner'ı — sadece başkasının profilindeyken göster */}
            {!isSelf && (isBirthday || isAnniversary) && (
              <div className={`rounded-2xl p-4 mb-6 flex items-center gap-3
                ${isBirthday
                  ? "bg-purple-50 border border-purple-200"
                  : "bg-emerald-50 border border-emerald-200"}`}>
                <span className="text-3xl">{isBirthday ? "🎂" : "🏆"}</span>
                <div>
                  <p className={`font-semibold text-sm ${isBirthday ? "text-purple-800" : "text-emerald-800"}`}>
                    {isBirthday
                      ? `Bugün ${emp.ad_soyad.split(" ")[0]}'nın doğum günü! 🎉`
                      : `Bugün ${emp.ad_soyad.split(" ")[0]}'nın ${yilFarki(emp.ise_giris_tarihi)}. çalışma yıl dönümü! 🌟`}
                  </p>
                  <p className={`text-xs mt-0.5 ${isBirthday ? "text-purple-600" : "text-emerald-600"}`}>
                    Yukarıdaki butonla kutlamanı ilet!
                  </p>
                </div>
              </div>
            )}

            {/* Oryantasyon segmenti — yeni çalışanlar için (ilk 30 gün) */}
            {emp && isYeniCalisan(emp.ise_giris_tarihi) && (
              <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5 mb-6">
                <div className="flex items-start gap-4">
                  <span className="text-3xl">🌟</span>
                  <div className="flex-1">
                    <h3 className="text-amber-800 font-bold text-base mb-1">
                      Oryantasyon Süreci
                    </h3>
                    <p className="text-amber-700 text-sm mb-3">
                      {emp.ad_soyad.split(" ")[0]} aramıza yeni katıldı! Oryantasyon sürecinde desteklenmesi gereken adımlar:
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {[
                        { emoji: "🏢", label: "Ofis turu & ekip tanıtımı" },
                        { emoji: "💻", label: "Sistem erişimleri kurulumu" },
                        { emoji: "📋", label: "İş tanımı ve hedef belirleme" },
                        { emoji: "🤝", label: "Mentor atama" },
                        { emoji: "📖", label: "Şirket politikaları eğitimi" },
                        { emoji: "✅", label: "İlk hafta değerlendirme" },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center gap-2 bg-white/60 rounded-lg px-3 py-2">
                          <span className="text-base">{item.emoji}</span>
                          <span className="text-xs text-amber-800 font-medium">{item.label}</span>
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-amber-600 mt-3">
                      📅 İşe giriş: {new Date(emp.ise_giris_tarihi).toLocaleDateString("tr-TR", {
                        day: "numeric", month: "long", year: "numeric"
                      })}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Bilgi kartları */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              {/* İşe giriş */}
              <div className="bg-white rounded-xl border border-gray-100 p-5">
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">İşe Giriş</p>
                <p className="text-lg font-bold text-gray-900">
                  {new Date(emp.ise_giris_tarihi).toLocaleDateString("tr-TR", {
                    day: "numeric", month: "long", year: "numeric",
                  })}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  {kidemYil > 0 ? `${kidemYil} yıl` : ""}{kidemYil > 0 && kidemAy > 0 ? " " : ""}{kidemAy > 0 ? `${kidemAy} ay` : kidemYil === 0 ? "Yeni katıldı" : ""} kıdem
                </p>
                {!isAnniversary && anniversaryDays !== null && anniversaryDays > 0 && anniversaryDays <= 30 && (
                  <p className="text-xs text-emerald-600 mt-1.5 font-medium">
                    🏆 {anniversaryDays} gün sonra yıl dönümü
                  </p>
                )}
              </div>

              {/* Doğum günü */}
              <div className="bg-white rounded-xl border border-gray-100 p-5">
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">Doğum Günü</p>
                {emp.dogum_tarihi ? (
                  <>
                    <p className="text-lg font-bold text-gray-900">
                      {new Date(emp.dogum_tarihi).toLocaleDateString("tr-TR", {
                        day: "numeric", month: "long",
                      })}
                    </p>
                    {!isBirthday && birthdayDays !== null && birthdayDays > 0 && birthdayDays <= 30 && (
                      <p className="text-xs text-purple-600 mt-1.5 font-medium">
                        🎂 {birthdayDays} gün sonra
                      </p>
                    )}
                    {isBirthday && (
                      <p className="text-xs text-purple-600 mt-1.5 font-medium">🎂 Bugün!</p>
                    )}
                  </>
                ) : (
                  <p className="text-gray-400 text-sm">Belirtilmemiş</p>
                )}
              </div>

              {/* Email */}
              {emp.email && (
                <div className="bg-white rounded-xl border border-gray-100 p-5 sm:col-span-2">
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">Kurumsal Email</p>
                  <p className="text-gray-900 font-medium">{emp.email}</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Kutlama modalı */}
      {modalOpen && emp && user && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
            {/* Modal header */}
            <div className={`px-6 py-5 ${
              modalTur === "dogum_gunu"
                ? "bg-gradient-to-r from-purple-600 to-pink-600"
                : modalTur === "yil_donumu"
                ? "bg-gradient-to-r from-emerald-600 to-teal-600"
                : "bg-gradient-to-r from-blue-600 to-violet-600"
            }`}>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-white font-bold text-lg">
                    {modalTur === "dogum_gunu" ? "🎂 Doğum Günü Kutlaması"
                     : modalTur === "yil_donumu" ? "🏆 Yıl Dönümü Kutlaması"
                     : "🎉 Tebrik Mesajı"}
                  </h3>
                  <p className="text-white/80 text-sm mt-0.5">→ {emp.ad_soyad}</p>
                </div>
                <button
                  onClick={() => setModalOpen(false)}
                  className="text-white/70 hover:text-white text-xl leading-none"
                >×</button>
              </div>
            </div>

            {/* Modal body */}
            <div className="p-6">
              {/* Mesaj alanı */}
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mesajın (düzenleyebilirsin)
              </label>
              <textarea
                value={modalMesaj}
                onChange={(e) => setModalMesaj(e.target.value)}
                rows={4}
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800
                           focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />

              {sendError && (
                <p className="text-red-600 text-xs mt-2">{sendError}</p>
              )}

              {/* Gönderme butonları */}
              <div className="mt-4 space-y-3">
                {/* Platform bildirimi */}
                <button
                  onClick={gonderBildirim}
                  disabled={sending || bildirimOk || !modalMesaj.trim()}
                  className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl
                              text-sm font-medium transition-colors
                              ${bildirimOk
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"}`}
                >
                  {bildirimOk ? "✅ Platform bildirimi gönderildi!" : sending ? "Gönderiliyor…" : "📬 Platform Bildirimi Gönder"}
                </button>

                {/* Email — sadece email adresi varsa */}
                {emp.email ? (
                  <button
                    onClick={gonderEmail}
                    disabled={emailSending || emailOk || !modalMesaj.trim()}
                    className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl
                                text-sm font-medium border transition-colors
                                ${emailOk
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-white hover:bg-gray-50 text-gray-700 border-gray-200 disabled:opacity-50"}`}
                  >
                    {emailOk ? "✅ Email gönderildi!" : emailSending ? "Gönderiliyor…" : `✉️ Email Gönder (${emp.email})`}
                  </button>
                ) : (
                  <p className="text-center text-xs text-gray-400">Bu çalışanın email adresi kayıtlı değil</p>
                )}
              </div>

              {(bildirimOk || emailOk) && (
                <button
                  onClick={() => setModalOpen(false)}
                  className="mt-4 w-full text-center text-sm text-gray-500 hover:text-gray-700"
                >
                  Kapat
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

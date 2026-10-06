"use client";
/**
 * Oryantasyon — Adım 1: Yeni Çalışan Kayıt Formu
 * Ayşe Aydın'ın ilk günü: kişisel ve kurumsal bilgilerini girer.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser } from "@/lib/auth";

export default function OrientationRegisterPage() {
  const router = useRouter();
  const [user, setUser] = useState<ReturnType<typeof getCurrentUser>>(null);
  const [form, setForm] = useState({
    adSoyad: "",
    sicilNo: "",
    kurumEmail: "",
    subeBirim: "",
    sifre: "",
    sifreTekrar: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    // Sadece yeni çalışan bu sayfaya erişebilir
    if (!u.isNewEmployee) { router.replace("/hub"); return; }
    setUser(u);
    // Adı önceden doldur
    setForm((f) => ({ ...f, adSoyad: u.name, kurumEmail: u.email }));
  }, [router]);

  function validate() {
    const e: Record<string, string> = {};
    if (!form.adSoyad.trim()) e.adSoyad = "Ad soyad gerekli";
    if (!form.sicilNo.trim()) e.sicilNo = "Sicil numarası gerekli";
    if (!form.kurumEmail.trim()) e.kurumEmail = "Kurumsal e-posta gerekli";
    else if (!form.kurumEmail.includes("@iso.org.tr"))
      e.kurumEmail = "Kurumsal e-posta @iso.org.tr uzantılı olmalı";
    if (!form.subeBirim.trim()) e.subeBirim = "Şube/Birim gerekli";
    if (!form.sifre) e.sifre = "Şifre gerekli";
    else if (form.sifre.length < 6) e.sifre = "Şifre en az 6 karakter olmalı";
    if (form.sifre !== form.sifreTekrar) e.sifreTekrar = "Şifreler eşleşmiyor";
    return e;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setSubmitting(true);
    // Demo: kayıt bilgilerini sessionStorage'da sakla, video sayfasına geç
    sessionStorage.setItem("orientation_register", JSON.stringify(form));
    setTimeout(() => {
      window.location.href = "/inpulse/orientation/video";
    }, 600);
  }

  function field(
    key: keyof typeof form,
    label: string,
    type = "text",
    placeholder = "",
  ) {
    return (
      <div>
        <label className="block text-xs font-semibold text-gray-700 mb-1">{label}</label>
        <input
          type={type}
          value={form[key]}
          onChange={(e) => {
            setForm((f) => ({ ...f, [key]: e.target.value }));
            setErrors((er) => { const n = { ...er }; delete n[key]; return n; });
          }}
          placeholder={placeholder}
          className={`w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2
            ${errors[key]
              ? "border-red-300 focus:ring-red-300"
              : "border-gray-200 focus:ring-blue-400"}`}
        />
        {errors[key] && (
          <p className="text-xs text-red-500 mt-1">{errors[key]}</p>
        )}
      </div>
    );
  }

  if (!user) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-emerald-50 via-teal-50 to-cyan-50 flex flex-col items-center justify-center px-4 py-10">
      {/* Başlık */}
      <div className="mb-8 text-center">
        <div className="w-14 h-14 bg-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-lg shadow-emerald-200">
          <span className="text-white font-bold text-xl">İ</span>
        </div>
        <h1 className="text-xl font-bold text-gray-900">Hoş Geldiniz! 🎉</h1>
        <p className="text-sm text-gray-500 mt-1">
          İSO Pulse'a katıldığınız için mutluyuz, {user.name.split(" ")[0]}.
        </p>

        {/* İlerleme adımları */}
        <div className="flex items-center justify-center gap-2 mt-5">
          {["Kayıt", "Video", "Quiz", "Sonuç"].map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                  ${i === 0
                    ? "bg-emerald-600 text-white"
                    : "bg-gray-200 text-gray-400"}`}
              >
                {i + 1}
              </div>
              <span className={`text-xs hidden sm:block ${i === 0 ? "text-emerald-700 font-semibold" : "text-gray-400"}`}>
                {step}
              </span>
              {i < 3 && <span className="text-gray-300 text-xs">›</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Form */}
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-gray-100 p-6">
        <h2 className="text-sm font-bold text-gray-700 mb-5">Üyelik Bilgileri</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {field("adSoyad", "Ad Soyad", "text", "Adınız Soyadınız")}
          {field("sicilNo", "Sicil No", "text", "Örn: 2026-0042")}
          {field("kurumEmail", "Kurumsal E-posta", "email", "ad.soyad@iso.org.tr")}
          {field("subeBirim", "Şube / Birim", "text", "Örn: Yazılım Geliştirme")}

          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs text-gray-400 mb-3">Platform Şifresi Oluştur</p>
            {field("sifre", "Şifre", "password", "En az 6 karakter")}
            {field("sifreTekrar", "Şifre Tekrar", "password", "Şifrenizi tekrar girin")}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl
                       font-semibold text-sm transition-colors disabled:opacity-50 mt-2"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Kaydediliyor…
              </span>
            ) : (
              "Devam Et → Oryantasyon Videosu"
            )}
          </button>
        </form>
      </div>
    </main>
  );
}

"use client";
/**
 * Inpulse Ana Dashboard
 * "İzin Al" ve "İzin Takibi" ana bölümleri burada.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchOverview } from "@/lib/api";
import { EmployeeLeaveOverview } from "@/types/leave";
import { getCurrentUser, logout, MockUser } from "@/lib/auth";
import LeaveBalanceCard from "@/components/inpulse/LeaveBalance";
import LeaveStatusBadge from "@/components/inpulse/LeaveStatusBadge";
import ChatBot from "@/components/inpulse/ChatBot";
import NotificationBell from "@/components/inpulse/NotificationBell";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EmployeeProfile {
  id: string;
  ise_giris_tarihi: string;
  dogum_tarihi: string | null;
}

interface UpcomingEmployee {
  employee_id: string;
  ad_soyad: string;
  tur: string;
  kac_gun_sonra: number;
  kac_yil?: number;
}

/** Seeded çalışanlardan örnek kutlama listesi — API sonuç döndürmediğinde gösterilir */
const SAMPLE_CELEBRATIONS: UpcomingEmployee[] = [
  { employee_id: "demo-employee-002", ad_soyad: "Kemal Demir",   tur: "dogum_gunu", kac_gun_sonra: 0 },
  { employee_id: "demo-employee-003", ad_soyad: "Selin Kaya",    tur: "yil_donumu", kac_gun_sonra: 3, kac_yil: 2 },
  { employee_id: "demo-manager-001",  ad_soyad: "Zeynep Yılmaz", tur: "dogum_gunu", kac_gun_sonra: 6 },
];

interface KutlamaModal {
  emp: UpcomingEmployee | null;
  hedefEmail: string;
  mesaj: string;
  gonderiyor: boolean;
  sonuc: "ok" | "hata" | null;
}

interface BildirimDurum {
  [key: string]: "gonderiyor" | "tamam" | "hata";
}

export default function InpulseDashboard() {
  const router = useRouter();
  const [overview, setOverview] = useState<EmployeeLeaveOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<MockUser | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const [empProfile, setEmpProfile] = useState<EmployeeProfile | null>(null);
  const [upcomingCelebrations, setUpcomingCelebrations] = useState<UpcomingEmployee[]>([]);
  const [isFirstDay, setIsFirstDay] = useState(false);
  const [kutlamaModal, setKutlamaModal] = useState<KutlamaModal>({
    emp: null, hedefEmail: "", mesaj: "", gonderiyor: false, sonuc: null,
  });
  const [bildirimDurum, setBildirimDurum] = useState<BildirimDurum>({});
  const [oryantasyonSonuc, setOryantasyonSonuc] = useState<{
    puan: number; dogru_sayisi: number; toplam_soru: number;
  } | null | "loading">("loading");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    setUser(u);
    // Çalışan profilini çek
    fetch(`${API}/api/v1/hr/employees/${u.id}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data: EmployeeProfile | null) => {
        if (!data) return;
        setEmpProfile(data);
        // İlk gün kontrolü
        const today = new Date();
        const start = new Date(data.ise_giris_tarihi);
        if (
          start.getDate() === today.getDate() &&
          start.getMonth() === today.getMonth() &&
          start.getFullYear() === today.getFullYear()
        ) {
          setIsFirstDay(true);
        }
      })
      .catch(() => null);
    // Yaklaşan kutlamalar — 30 günlük aralık; boşsa örnek veriler gösterilir
    fetch(`${API}/api/v1/hr/celebrations/today?gun_aralik=30`)
      .then((r) => r.ok ? r.json() : [])
      .then((list: UpcomingEmployee[]) => setUpcomingCelebrations(list.slice(0, 4)))
      .catch(() => null);

    // Yeni çalışan ise oryantasyon sonucunu çek
    if (u.isNewEmployee) {
      fetch(`${API}/api/v1/hr/orientation/results/${u.id}`)
        .then((r) => r.ok ? r.json() : null)
        .then((data) => setOryantasyonSonuc(data ?? null))
        .catch(() => setOryantasyonSonuc(null));
    } else {
      setOryantasyonSonuc(null);
    }
  }, [router]);

  useEffect(() => {
    const currentUser = getCurrentUser();
    if (!currentUser) return;
    const empId = currentUser.id;

    const refresh = () =>
      fetchOverview(empId)
        .then(setOverview)
        .catch((e) => setError(e instanceof Error ? e.message : "Hata"))
        .finally(() => setLoading(false));

    refresh();
    // 30 saniyede bir bakiye + son talepler otomatik güncellenir
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Dışarı tıklayınca dropdown kapansın
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  async function emailAc(emp: UpcomingEmployee) {
    // Çalışanın emailini backend'den çek
    try {
      const res = await fetch(`${API}/api/v1/hr/employees/${emp.employee_id}`);
      const detail = res.ok ? await res.json() : null;
      setKutlamaModal({
        emp,
        hedefEmail: detail?.email ?? "",
        mesaj: "",
        gonderiyor: false,
        sonuc: null,
      });
    } catch {
      setKutlamaModal({ emp, hedefEmail: "", mesaj: "", gonderiyor: false, sonuc: null });
    }
  }

  async function emailGonder() {
    if (!kutlamaModal.emp || !kutlamaModal.hedefEmail.trim()) return;
    const { emp } = kutlamaModal;
    const tur = emp.tur === "dogum_gunu" ? "dogum_gunu" : "yil_donumu";
    const varsayilanMesaj = emp.tur === "dogum_gunu"
      ? `Sevgili ${emp.ad_soyad}, doğum günün kutlu olsun! 🎂`
      : `Sevgili ${emp.ad_soyad}, işe girişinin yıl dönümü kutlu olsun! 🏆`;
    setKutlamaModal((p) => ({ ...p, gonderiyor: true, sonuc: null }));
    try {
      await fetch(`${API}/api/v1/hr/celebrations/kutla/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hedef_email: kutlamaModal.hedefEmail,
          hedef_ad_soyad: emp.ad_soyad,
          gonderen_ad: user?.name ?? "İş Arkadaşın",
          tur,
          mesaj: kutlamaModal.mesaj.trim() || varsayilanMesaj,
        }),
      });
      setKutlamaModal((p) => ({ ...p, gonderiyor: false, sonuc: "ok" }));
    } catch {
      setKutlamaModal((p) => ({ ...p, gonderiyor: false, sonuc: "hata" }));
    }
  }

  async function bildirimGonder(emp: UpcomingEmployee) {
    if (!user) return;
    const key = `${emp.employee_id}-${emp.tur}`;
    setBildirimDurum((p) => ({ ...p, [key]: "gonderiyor" }));
    const tur = emp.tur === "dogum_gunu" ? "dogum_gunu" : "yil_donumu";
    const mesaj = emp.tur === "dogum_gunu"
      ? `${emp.ad_soyad}, doğum günün kutlu olsun! 🎂`
      : `${emp.ad_soyad}, yıl dönümün kutlu olsun! 🏆`;
    try {
      await fetch(`${API}/api/v1/hr/celebrations/kutla`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hedef_id: emp.employee_id,
          gonderen_id: user.id,
          gonderen_ad: user.name,
          tur,
          mesaj,
        }),
      });
      setBildirimDurum((p) => ({ ...p, [key]: "tamam" }));
    } catch {
      setBildirimDurum((p) => ({ ...p, [key]: "hata" }));
    }
  }

  const roleColors: Record<string, string> = {
    ik: "bg-emerald-100 text-emerald-700",
    yonetici: "bg-violet-100 text-violet-700",
    calisan: "bg-blue-100 text-blue-700",
  };

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/hub")}
              className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center
                         hover:bg-blue-700 transition-colors"
              title="Ana menüye dön"
            >
              <span className="text-white font-bold text-sm">İ</span>
            </button>
            <div>
              <h1 className="font-semibold text-gray-900">İSO Pulse</h1>
              <p className="text-xs text-gray-500">İnpulse — İç Kanal</p>
            </div>
          </div>

          {/* Bildirim zili + Profil */}
          <div className="flex items-center gap-2">
          {user && <NotificationBell userId={user.id} />}

          {/* Profil butonu */}
          {user && (
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setProfileOpen((v) => !v)}
                className="flex items-center gap-2.5 pl-1 pr-3 py-1 rounded-full
                           hover:bg-gray-100 transition-colors group"
                aria-haspopup="true"
                aria-expanded={profileOpen}
              >
                {/* Avatar */}
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center
                                text-white text-xs font-bold shadow-sm">
                  {user.avatar}
                </div>
                {/* İsim - sadece sm ve üstü */}
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-medium text-gray-900 leading-tight">{user.name}</p>
                  <p className="text-xs text-gray-500 leading-tight">{user.roleLabel}</p>
                </div>
                <span className="text-gray-400 text-xs">▾</span>
              </button>

              {/* Dropdown */}
              {profileOpen && (
                <div
                  className="absolute right-0 mt-2 w-60 bg-white rounded-2xl shadow-xl
                             border border-gray-100 z-50 overflow-hidden"
                >
                  {/* Kullanıcı bilgisi */}
                  <div className="px-4 py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center
                                      justify-center text-white font-bold text-sm flex-shrink-0">
                        {user.avatar}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-sm text-gray-900 truncate">{user.name}</p>
                        <p className="text-xs text-gray-500 truncate">{user.email}</p>
                      </div>
                    </div>
                    <span
                      className={`mt-2 inline-block text-xs font-medium px-2 py-0.5 rounded-full
                                  ${roleColors[user.role] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {user.roleLabel}
                    </span>
                  </div>

                  {/* Profilim */}
                  <button
                    onClick={() => { setProfileOpen(false); router.push(`/inpulse/profile/${user.id}`); }}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-gray-700
                               hover:bg-gray-50 transition-colors border-b border-gray-100"
                  >
                    <span>👤</span> Profilimi Görüntüle
                  </button>

                  {/* Hub'a dön */}
                  <button
                    onClick={() => { setProfileOpen(false); router.push("/hub"); }}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-gray-700
                               hover:bg-gray-50 transition-colors border-b border-gray-100"
                  >
                    <span>🏠</span> Ana Menüye Dön
                  </button>

                  {/* Çıkış */}
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-red-600
                               hover:bg-red-50 transition-colors"
                  >
                    <span>🚪</span> Çıkış Yap
                  </button>
                </div>
              )}
            </div>
          )}
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">

        {/* ── İlk Gün Oryantasyon Banner'ı ─────────────────────────────── */}
        {isFirstDay && (
          <div className="mb-6 bg-gradient-to-r from-violet-600 to-blue-600 rounded-2xl p-6 text-white shadow-lg">
            <div className="flex items-start gap-4">
              <span className="text-4xl flex-shrink-0">🎊</span>
              <div className="flex-1">
                <h2 className="text-xl font-bold mb-1">
                  Hoş geldin, {user?.name.split(" ")[0]}!
                </h2>
                <p className="text-white/85 text-sm mb-4">
                  Bugün İSO Pulse ailesine katıldığın ilk gün! Önce oryantasyon sürecini tamamlayarak
                  platformu ve çalışma kurallarını tanıyabilirsin.
                </p>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => router.push("/inpulse/orientation/register")}
                    className="bg-white text-violet-700 font-semibold text-sm px-5 py-2.5
                               rounded-xl hover:bg-violet-50 transition-colors"
                  >
                    🚀 Oryantasyona Başla
                  </button>
                  <button
                    onClick={() => router.push("/inpulse/orientation/video")}
                    className="bg-white/20 hover:bg-white/30 text-white font-medium text-sm
                               px-5 py-2.5 rounded-xl transition-colors"
                  >
                    🎬 Karşılama Videosunu İzle
                  </button>
                </div>
              </div>
            </div>
            {/* Adımlar */}
            <div className="mt-5 grid grid-cols-3 gap-3">
              {[
                { num: "1", label: "Kayıt & Video", icon: "📋" },
                { num: "2", label: "Eğitim İçeriği", icon: "📚" },
                { num: "3", label: "Quiz", icon: "✅" },
              ].map((step) => (
                <div key={step.num} className="bg-white/15 rounded-xl p-3 text-center">
                  <span className="text-lg">{step.icon}</span>
                  <p className="text-white/90 text-xs font-medium mt-1">Adım {step.num}</p>
                  <p className="text-white/70 text-xs">{step.label}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Yeni Çalışan: Kalıcı Oryantasyon Segmenti ───────────────── */}
        {user?.isNewEmployee && oryantasyonSonuc !== "loading" && (
          <div className={`mb-6 rounded-2xl border-2 p-5 ${
            oryantasyonSonuc
              ? "bg-emerald-50 border-emerald-200"
              : "bg-violet-50 border-violet-200"
          }`}>
            <div className="flex items-start gap-4">
              <span className="text-3xl flex-shrink-0">
                {oryantasyonSonuc ? "🎓" : "📚"}
              </span>
              <div className="flex-1 min-w-0">
                <h3 className={`font-bold text-base mb-0.5 ${
                  oryantasyonSonuc ? "text-emerald-800" : "text-violet-800"
                }`}>
                  {oryantasyonSonuc ? "Oryantasyon Tamamlandı" : "Oryantasyonunu Tamamla"}
                </h3>

                {oryantasyonSonuc ? (
                  <>
                    <p className="text-sm text-emerald-700 mb-3">
                      Quiz puanın:{" "}
                      <span className={`font-bold ${
                        oryantasyonSonuc.puan >= 80 ? "text-emerald-600"
                        : oryantasyonSonuc.puan >= 60 ? "text-amber-600"
                        : "text-red-600"
                      }`}>
                        {oryantasyonSonuc.puan}/100
                      </span>
                      {" "}({oryantasyonSonuc.dogru_sayisi}/{oryantasyonSonuc.toplam_soru} doğru)
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => router.push("/inpulse/orientation/video")}
                        className="text-sm bg-white border border-emerald-300 text-emerald-700
                                   hover:bg-emerald-100 font-medium px-4 py-2 rounded-xl transition-colors"
                      >
                        🎬 Videoyu Tekrar İzle
                      </button>
                      <button
                        onClick={() => router.push("/inpulse/orientation/quiz")}
                        className="text-sm bg-emerald-600 hover:bg-emerald-700 text-white
                                   font-medium px-4 py-2 rounded-xl transition-colors"
                      >
                        📝 Quizi Tekrar Çöz
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-violet-700 mb-3">
                      Platforma alışmak için oryantasyon videolarını izle ve quizi tamamla.
                    </p>
                    <button
                      onClick={() => router.push("/inpulse/orientation/register")}
                      className="text-sm bg-violet-600 hover:bg-violet-700 text-white
                                 font-semibold px-5 py-2.5 rounded-xl transition-colors"
                    >
                      🚀 Oryantasyona Başla
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Ana aksiyon butonları */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          {/* İzin Al */}
          <Link
            href="/inpulse/leave"
            className="group flex flex-col items-center justify-center gap-3 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl p-8 transition-colors shadow-md"
          >
            <span className="text-5xl">📅</span>
            <div className="text-center">
              <p className="text-xl font-bold">İzin Al</p>
              <p className="text-blue-100 text-sm mt-1">İzin türü seç ve talepte bulun</p>
            </div>
          </Link>

          {/* İzin Takibi */}
          <Link
            href="/inpulse/leave/history"
            className="group flex flex-col items-center justify-center gap-3 bg-white hover:bg-gray-50 text-gray-900 rounded-2xl p-8 transition-colors shadow-md border-2 border-gray-200"
          >
            <span className="text-5xl">📊</span>
            <div className="text-center">
              <p className="text-xl font-bold">İzin Takibi</p>
              <p className="text-gray-500 text-sm mt-1">Geçmiş ve bekleyen talepler</p>
            </div>
          </Link>
        </div>

        {/* Yönetici / İK: İzin Onayları butonu — öne çıkar */}
        {user && user.role === "yonetici" && (
          <div className="mb-4">
            <Link
              href="/inpulse/manager"
              className="group flex items-center gap-5 bg-gradient-to-r from-emerald-600 to-teal-600
                         hover:from-emerald-700 hover:to-teal-700 text-white rounded-2xl px-8 py-6
                         transition-all shadow-md w-full"
            >
              <span className="text-4xl">✅</span>
              <div>
                <p className="text-xl font-bold">İzin Onayları</p>
                <p className="text-emerald-100 text-sm mt-0.5">
                  Ekibinden gelen izin taleplerini onayla veya reddet
                </p>
              </div>
              <span className="ml-auto text-2xl opacity-70">→</span>
            </Link>
          </div>
        )}
        {user && user.role === "ik" && (
          <div className="mb-4">
            <Link
              href="/inpulse/hr"
              className="group flex items-center gap-5 bg-gradient-to-r from-emerald-600 to-teal-600
                         hover:from-emerald-700 hover:to-teal-700 text-white rounded-2xl px-8 py-6
                         transition-all shadow-md w-full"
            >
              <span className="text-4xl">🏢</span>
              <div>
                <p className="text-xl font-bold">HR Paneli</p>
                <p className="text-emerald-100 text-sm mt-0.5">
                  Tüm izin takibi, oryantasyon ve kutlamalar
                </p>
              </div>
              <span className="ml-auto text-2xl opacity-70">→</span>
            </Link>
          </div>
        )}

        {/* Görev butonları */}
        {user && (user.role === "yonetici" || user.role === "ik") ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            <Link
              href="/inpulse/tasks"
              className="group flex flex-col items-center justify-center gap-3 bg-violet-600 hover:bg-violet-700 text-white rounded-2xl p-8 transition-colors shadow-md"
            >
              <span className="text-5xl">✅</span>
              <div className="text-center">
                <p className="text-xl font-bold">Görevlerim</p>
                <p className="text-violet-100 text-sm mt-1">Atanmış görevleri görüntüle</p>
              </div>
            </Link>
            <Link
              href="/inpulse/manager/tasks"
              className="group flex flex-col items-center justify-center gap-3 bg-white hover:bg-gray-50 text-gray-900 rounded-2xl p-8 transition-colors shadow-md border-2 border-gray-200"
            >
              <span className="text-5xl">🗂️</span>
              <div className="text-center">
                <p className="text-xl font-bold">Görev Yönetimi</p>
                <p className="text-gray-500 text-sm mt-1">Ekip görevlerini yönet</p>
              </div>
            </Link>
          </div>
        ) : (
          <div className="mb-8">
            <Link
              href="/inpulse/tasks"
              className="group flex flex-col items-center justify-center gap-3 bg-violet-600 hover:bg-violet-700 text-white rounded-2xl p-8 transition-colors shadow-md"
            >
              <span className="text-5xl">✅</span>
              <div className="text-center">
                <p className="text-xl font-bold">Görevlerim</p>
                <p className="text-violet-100 text-sm mt-1">Atanmış görevleri görüntüle</p>
              </div>
            </Link>
          </div>
        )}

        {/* ── İzin Bakiyesi + Kutlamalar — yan yana ────────────────────── */}
        {loading && (
          <div className="bg-white rounded-xl border p-6 text-center text-gray-400 animate-pulse">
            Bakiye yükleniyor…
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
            {error}
          </div>
        )}
        {overview && (() => {
          // API verisi yoksa seeded örnek kutlamalar göster
          const kutlamalar = upcomingCelebrations.length > 0
            ? upcomingCelebrations
            : SAMPLE_CELEBRATIONS;

          return (
            <>
              {/* Yan yana grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {/* Sol: İzin Bakiyesi */}
                <LeaveBalanceCard balance={overview.bakiye} />

                {/* Sağ: Kutlama Bildirimleri */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
                      🎉 Kutlamalar
                    </h3>
                    {upcomingCelebrations.length === 0 && (
                      <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        Örnek veri
                      </span>
                    )}
                  </div>

                  <div className="space-y-2.5 flex-1">
                    {kutlamalar.map((c) => {
                      const key = `${c.employee_id}-${c.tur}`;
                      const bdStat = bildirimDurum[key];
                      const isDogum = c.tur === "dogum_gunu";
                      return (
                        <div
                          key={key}
                          className={`flex items-center gap-3 rounded-xl border p-3
                            ${isDogum ? "bg-purple-50 border-purple-100" : "bg-emerald-50 border-emerald-100"}`}
                        >
                          <span className="text-2xl flex-shrink-0">
                            {isDogum ? "🎂" : "🏆"}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className={`font-semibold text-sm truncate ${isDogum ? "text-purple-900" : "text-emerald-900"}`}>
                              {c.ad_soyad}
                            </p>
                            <p className={`text-xs ${isDogum ? "text-purple-600" : "text-emerald-600"}`}>
                              {c.kac_gun_sonra === 0 ? "Bugün 🎉" : `${c.kac_gun_sonra} gün sonra`}
                              {" · "}
                              {isDogum ? "Doğum günü" : "Yıl dönümü"}
                            </p>
                          </div>
                          <div className="flex flex-col gap-1 flex-shrink-0">
                            {/* Mesaj At */}
                            <button
                              onClick={() => bildirimGonder(c)}
                              disabled={bdStat === "gonderiyor" || bdStat === "tamam"}
                              className={`text-[11px] font-medium px-2.5 py-1 rounded-lg transition-colors
                                ${bdStat === "tamam"
                                  ? "bg-green-100 text-green-700 border border-green-200"
                                  : bdStat === "gonderiyor"
                                  ? "bg-gray-100 text-gray-400 border border-gray-200"
                                  : isDogum
                                  ? "bg-purple-100 hover:bg-purple-200 text-purple-800 border border-purple-200"
                                  : "bg-emerald-100 hover:bg-emerald-200 text-emerald-800 border border-emerald-200"}`}
                            >
                              {bdStat === "tamam" ? "✅ Tamam" : bdStat === "gonderiyor" ? "…" : "💬 Mesaj At"}
                            </button>
                            {/* Email Gönder */}
                            <button
                              onClick={() => emailAc(c)}
                              className="text-[11px] font-medium px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                            >
                              ✉️ Email Gönder
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Son talepler */}
              {overview.son_talepler.length > 0 && (
                <div className="mt-6">
                  <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Son Talepler
                  </h2>
                  <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-100">
                    {overview.son_talepler.slice(0, 5).map((talep) => (
                      <div key={talep.id} className="flex items-center justify-between px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {talep.izin_turu.replace(/_/g, " ")}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {new Date(talep.cikis_tarihi).toLocaleDateString("tr-TR")} —{" "}
                            {talep.sure_gun} gün
                          </p>
                        </div>
                        <LeaveStatusBadge durum={talep.durum} />
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 text-right">
                    <Link
                      href="/inpulse/leave/history"
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Tümünü gör →
                    </Link>
                  </div>
                </div>
              )}
            </>
          );
        })()}
      </div>

      {/* ── Email Kutlama Modalı ─────────────────────────────────────────── */}
      {kutlamaModal.emp && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">
                {kutlamaModal.emp.tur === "dogum_gunu" ? "🎂" : "🏆"}
              </span>
              <div>
                <h3 className="font-semibold text-gray-900">Kutlama Emaili Gönder</h3>
                <p className="text-xs text-gray-500">{kutlamaModal.emp.ad_soyad}</p>
              </div>
            </div>

            {kutlamaModal.sonuc === "ok" ? (
              <div className="text-center py-6">
                <p className="text-4xl mb-2">✅</p>
                <p className="font-semibold text-emerald-700">Email gönderildi!</p>
                <p className="text-xs text-gray-500 mt-1">{kutlamaModal.emp.ad_soyad} adresine kutlama maili iletildi.</p>
                <button
                  onClick={() => setKutlamaModal({ emp: null, hedefEmail: "", mesaj: "", gonderiyor: false, sonuc: null })}
                  className="mt-4 text-sm text-blue-600 hover:underline"
                >
                  Kapat
                </button>
              </div>
            ) : (
              <>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Email Adresi</label>
                    <input
                      type="email"
                      value={kutlamaModal.hedefEmail}
                      onChange={(e) => setKutlamaModal((p) => ({ ...p, hedefEmail: e.target.value }))}
                      placeholder="örnek@firma.com"
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                                 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">
                      Mesajınız <span className="text-gray-400 font-normal">(isteğe bağlı)</span>
                    </label>
                    <textarea
                      rows={3}
                      value={kutlamaModal.mesaj}
                      onChange={(e) => setKutlamaModal((p) => ({ ...p, mesaj: e.target.value }))}
                      placeholder={
                        kutlamaModal.emp.tur === "dogum_gunu"
                          ? `Sevgili ${kutlamaModal.emp.ad_soyad}, doğum günün kutlu olsun! 🎂`
                          : `Sevgili ${kutlamaModal.emp.ad_soyad}, yıl dönümün kutlu olsun! 🏆`
                      }
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                                 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    />
                  </div>
                </div>

                {kutlamaModal.sonuc === "hata" && (
                  <p className="mt-2 text-xs text-red-600">⚠️ Email gönderilemedi. Lütfen tekrar dene.</p>
                )}

                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => setKutlamaModal({ emp: null, hedefEmail: "", mesaj: "", gonderiyor: false, sonuc: null })}
                    className="flex-1 border border-gray-200 text-gray-600 text-sm rounded-xl py-2 hover:bg-gray-50 transition-colors"
                  >
                    İptal
                  </button>
                  <button
                    onClick={emailGonder}
                    disabled={kutlamaModal.gonderiyor || !kutlamaModal.hedefEmail.trim()}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-xl py-2 transition-colors"
                  >
                    {kutlamaModal.gonderiyor ? "Gönderiliyor…" : "✉️ Gönder"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Chatbot widget — sayfanın her yerinden erişilebilir */}
      <ChatBot />
    </main>
  );
}

"use client";
/**
 * İSO Pulse — Ana Hub
 * Login sonrası ürün seçim ekranı: Inpulse | Outpulse
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, logout, MockUser } from "@/lib/auth";

export default function HubPage() {
  const router = useRouter();
  const [user, setUser] = useState<MockUser | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    setUser(u);
  }, [router]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (!user) return null;

  const roleColors: Record<string, string> = {
    ik: "bg-emerald-100 text-emerald-700",
    yonetici: "bg-violet-100 text-violet-700",
    calisan: "bg-blue-100 text-blue-700",
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur border-b border-white/60 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-sm">İ</span>
            </div>
            <span className="font-semibold text-gray-900">İSO Pulse</span>
          </div>

          {/* Profil butonu */}
          <div className="relative">
            <button
              onClick={() => setProfileOpen((v) => !v)}
              className="flex items-center gap-2.5 pl-1 pr-3 py-1 rounded-full
                         hover:bg-gray-100 transition-colors group"
            >
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center
                              text-white text-xs font-bold shadow-sm">
                {user.avatar}
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-sm font-medium text-gray-900 leading-tight">{user.name}</p>
                <p className="text-xs text-gray-500 leading-tight">{user.roleLabel}</p>
              </div>
              <span className="text-gray-400 text-xs ml-0.5">▾</span>
            </button>

            {profileOpen && (
              <>
                {/* Overlay */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setProfileOpen(false)}
                />
                {/* Dropdown */}
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl
                                border border-gray-100 z-20 overflow-hidden">
                  {/* Kullanıcı bilgisi */}
                  <div className="px-4 py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center
                                      justify-center text-white font-bold text-sm">
                        {user.avatar}
                      </div>
                      <div>
                        <p className="font-semibold text-sm text-gray-900">{user.name}</p>
                        <p className="text-xs text-gray-500">{user.email}</p>
                      </div>
                    </div>
                    <span className={`mt-2 inline-block text-xs font-medium px-2 py-0.5 rounded-full ${roleColors[user.role] ?? "bg-gray-100 text-gray-600"}`}>
                      {user.roleLabel}
                    </span>
                  </div>

                  {/* Çıkış */}
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-red-600
                               hover:bg-red-50 transition-colors"
                  >
                    <span>🚪</span> Çıkış Yap
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* İçerik */}
      <div className="max-w-2xl mx-auto px-6 py-14 flex flex-col items-center">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
          Hoş geldin, {user.name.split(" ")[0]}
        </p>
        <h2 className="text-2xl font-bold text-gray-900 mb-1">Hangi platforma gitmek istiyorsun?</h2>
        <p className="text-gray-500 text-sm mb-10">Aşağıdan devam etmek istediğin modülü seç</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 w-full">
          {/* ── Inpulse ─────────────────────────────────────────── */}
          <button
            onClick={() => router.push("/inpulse")}
            className="group flex flex-col items-center justify-center gap-4 bg-blue-600
                       hover:bg-blue-700 text-white rounded-3xl p-10 shadow-xl
                       shadow-blue-200 hover:shadow-blue-300 transition-all duration-200
                       hover:-translate-y-1 active:scale-95"
          >
            <span className="text-6xl">📋</span>
            <div className="text-center">
              <p className="text-2xl font-bold">Inpulse</p>
              <p className="text-blue-100 text-sm mt-1 leading-snug">
                İzin talepleri, bakiye ve İK asistanı
              </p>
            </div>
            <span className="text-blue-200 text-sm mt-1 group-hover:text-white transition-colors">
              Giriş yap →
            </span>
          </button>

          {/* ── Outpulse ─────────────────────────────────────────── */}
          <div
            className="flex flex-col items-center justify-center gap-4 bg-white/70
                       text-gray-400 rounded-3xl p-10 shadow-lg border-2 border-dashed
                       border-gray-200 cursor-not-allowed select-none"
          >
            <span className="text-6xl opacity-50">🌐</span>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-500">Outpulse</p>
              <p className="text-gray-400 text-sm mt-1 leading-snug">
                Regülasyon takibi ve mevzuat izleme
              </p>
            </div>
            <span className="text-xs bg-gray-100 text-gray-400 px-3 py-1 rounded-full font-medium mt-1">
              Yakında
            </span>
          </div>
        </div>
      </div>
    </main>
  );
}

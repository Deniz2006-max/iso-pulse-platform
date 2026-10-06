"use client";
/**
 * İSO Pulse — Kişi Seçimli Giriş Ekranı
 * 4 kişi kartı: Zeynep Yılmaz, Ayşe Aydın (yeni), Mehmet Kaya, Selin Arslan
 */
import { useRouter } from "next/navigation";
import { useState } from "react";
import { loginById, ALL_MOCK_USERS, MockUser } from "@/lib/auth";

interface CardStyle {
  bg: string;
  border: string;
  hover: string;
  badgeBg: string;
  badgeText: string;
  avatarBg: string;
  icon?: string;
}

const CARD_STYLES: Record<string, CardStyle> = {
  "demo-employee-001": {
    bg: "bg-white",
    border: "border-gray-200 hover:border-blue-400",
    hover: "hover:bg-blue-50",
    badgeBg: "bg-blue-100",
    badgeText: "text-blue-700",
    avatarBg: "bg-blue-600",
  },
  "demo-employee-ayse": {
    bg: "bg-gradient-to-br from-emerald-50 to-teal-50",
    border: "border-emerald-200 hover:border-emerald-500",
    hover: "hover:from-emerald-100 hover:to-teal-100",
    badgeBg: "bg-emerald-100",
    badgeText: "text-emerald-700",
    avatarBg: "bg-emerald-600",
    icon: "🌟",
  },
  "demo-manager-001": {
    bg: "bg-white",
    border: "border-gray-200 hover:border-violet-400",
    hover: "hover:bg-violet-50",
    badgeBg: "bg-violet-100",
    badgeText: "text-violet-700",
    avatarBg: "bg-violet-600",
  },
  "demo-hr-001": {
    bg: "bg-white",
    border: "border-gray-200 hover:border-emerald-400",
    hover: "hover:bg-emerald-50",
    badgeBg: "bg-emerald-100",
    badgeText: "text-emerald-700",
    avatarBg: "bg-emerald-700",
  },
};

function PersonCard({
  user,
  onSelect,
  isLoading,
}: {
  user: MockUser;
  onSelect: () => void;
  isLoading: boolean;
}) {
  const style = CARD_STYLES[user.id] ?? {
    bg: "bg-white",
    border: "border-gray-200 hover:border-blue-400",
    hover: "hover:bg-blue-50",
    badgeBg: "bg-gray-100",
    badgeText: "text-gray-700",
    avatarBg: "bg-gray-600",
  };

  return (
    <button
      onClick={onSelect}
      disabled={isLoading}
      className={`
        w-full flex items-center gap-4 px-5 py-4 rounded-2xl border-2
        ${style.bg} ${style.border} ${style.hover}
        transition-all duration-200 shadow-sm hover:shadow-md
        disabled:opacity-60 disabled:cursor-not-allowed
        group text-left relative
      `}
    >
      {/* Yeni çalışan rozeti */}
      {user.isNewEmployee && (
        <span className="absolute top-2 right-3 text-[10px] font-bold bg-emerald-500 text-white px-2 py-0.5 rounded-full">
          İlk Gün 🎉
        </span>
      )}

      {/* Avatar */}
      <div
        className={`w-11 h-11 ${style.avatarBg} rounded-full flex items-center justify-center
                    text-white text-sm font-bold flex-shrink-0 shadow-sm`}
      >
        {user.avatar}
      </div>

      {/* İsim + Bilgi */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm text-gray-900">{user.name}</p>
        <p className="text-xs text-gray-500 mt-0.5 truncate">{user.email}</p>
        <span
          className={`inline-block mt-1 text-[10px] font-semibold px-2 py-0.5 rounded-full
                      ${style.badgeBg} ${style.badgeText}`}
        >
          {user.isNewEmployee ? "Yeni Çalışan — Oryantasyon" : user.roleLabel}
        </span>
      </div>

      {/* Ok / Spinner */}
      <div className="flex-shrink-0">
        {isLoading ? (
          <span className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin block" />
        ) : (
          <span className="text-gray-300 group-hover:text-gray-500 transition-colors text-lg">→</span>
        )}
      </div>
    </button>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [loadingId, setLoadingId] = useState<string | null>(null);

  function handleSelect(user: MockUser) {
    if (loadingId) return;
    setLoadingId(user.id);
    loginById(user.id);

    // Yeni çalışan → oryantasyon akışı; diğerleri → hub
    const target = user.isNewEmployee ? "/inpulse/orientation/register" : "/hub";
    setTimeout(() => {
      window.location.href = target;
    }, 400);
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div className="mb-10 flex flex-col items-center gap-3">
        <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-200">
          <span className="text-white font-bold text-2xl">İ</span>
        </div>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">İSO Pulse</h1>
          <p className="text-sm text-gray-500 mt-0.5">Çalışan Deneyim Platformu</p>
        </div>
      </div>

      {/* Kişi seçimi */}
      <div className="w-full max-w-sm space-y-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest text-center mb-5">
          Hesabını seç
        </p>

        {ALL_MOCK_USERS.map((user) => (
          <PersonCard
            key={user.id}
            user={user}
            onSelect={() => handleSelect(user)}
            isLoading={loadingId === user.id}
          />
        ))}
      </div>

      {/* Demo notu */}
      <p className="mt-10 text-xs text-gray-400 text-center max-w-xs leading-relaxed">
        Bu, <span className="font-medium text-gray-500">İSOV Hackathon</span> demo ortamıdır.
        Gerçek kimlik doğrulaması üretim sürümünde devreye alınacaktır.
      </p>
    </main>
  );
}

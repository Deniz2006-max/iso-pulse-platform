"use client";
/**
 * Oryantasyon — Adım 2: Oryantasyon Videosu
 * Video izlendikten sonra "Quize Geç" butonu aktif olur.
 */
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getCurrentUser } from "@/lib/auth";

export default function OrientationVideoPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [watched, setWatched] = useState(false);
  const [progress, setProgress] = useState(0);
  const [canSkip, setCanSkip] = useState(false);

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    if (!u.isNewEmployee) { router.replace("/hub"); return; }
    // Kayıt adımını atladıysa geri yönlendir
    if (!sessionStorage.getItem("orientation_register")) {
      router.replace("/inpulse/orientation/register");
      return;
    }
    // Demo: 10 saniye sonra "atla" butonu görünsün
    const t = setTimeout(() => setCanSkip(true), 10_000);
    return () => clearTimeout(t);
  }, [router]);

  function handleTimeUpdate() {
    const v = videoRef.current;
    if (!v || !v.duration) return;
    const pct = Math.floor((v.currentTime / v.duration) * 100);
    setProgress(pct);
    // %80 izlenince quiz butonu aktif
    if (pct >= 80) setWatched(true);
  }

  function handleEnded() {
    setWatched(true);
    setProgress(100);
  }

  function goToQuiz() {
    window.location.href = "/inpulse/orientation/quiz";
  }

  return (
    <main className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-8">
      {/* İlerleme adımları */}
      <div className="flex items-center justify-center gap-2 mb-6">
        {["Kayıt", "Video", "Quiz", "Sonuç"].map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                ${i === 0
                  ? "bg-emerald-600 text-white"
                  : i === 1
                  ? "bg-blue-500 text-white"
                  : "bg-gray-700 text-gray-400"}`}
            >
              {i === 0 ? "✓" : i + 1}
            </div>
            <span className={`text-xs hidden sm:block ${i === 1 ? "text-blue-300 font-semibold" : "text-gray-500"}`}>
              {step}
            </span>
            {i < 3 && <span className="text-gray-600 text-xs">›</span>}
          </div>
        ))}
      </div>

      <div className="w-full max-w-2xl">
        <h1 className="text-white font-bold text-lg mb-1 text-center">Oryantasyon Videosu</h1>
        <p className="text-gray-400 text-sm text-center mb-4">
          İSO Pulse platformunu ve çalışan haklarınızı tanıyın
        </p>

        {/* Video oynatıcı */}
        <div className="rounded-2xl overflow-hidden bg-black shadow-2xl">
          <video
            ref={videoRef}
            controls
            className="w-full aspect-video"
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleEnded}
            preload="metadata"
          >
            <source src="/orientation-video.mp4" type="video/mp4" />
            Tarayıcınız video oynatmayı desteklemiyor.
          </video>
        </div>

        {/* İlerleme çubuğu */}
        <div className="mt-4 mb-2">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>İzlenme durumu</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {!watched && (
            <p className="text-xs text-gray-500 mt-1.5">
              Quiz için videoyu en az %80 izlemeniz gerekiyor.
            </p>
          )}
        </div>

        {/* Butonlar */}
        <div className="flex gap-3 mt-5">
          {canSkip && !watched && (
            <button
              onClick={goToQuiz}
              className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-xl
                         text-sm font-medium transition-colors"
            >
              Atla (Demo)
            </button>
          )}
          <button
            onClick={goToQuiz}
            disabled={!watched && !canSkip}
            className={`py-3 rounded-xl text-sm font-semibold transition-colors
              ${watched
                ? "flex-1 bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-900/30"
                : "flex-1 bg-gray-800 text-gray-500 cursor-not-allowed"}`}
          >
            {watched ? "✓ Quize Geç →" : "Videoyu izleyin…"}
          </button>
        </div>
      </div>
    </main>
  );
}

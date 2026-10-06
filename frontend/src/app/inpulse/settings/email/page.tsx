"use client";
/**
 * Email Bağlantı Ayarları — İSO Pulse
 * Platform SMTP yapılandırması, bağlantı testi ve durum göstergesi.
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, MockUser } from "@/lib/auth";
import NotificationBell from "@/components/inpulse/NotificationBell";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SmtpStatus {
  host: string;
  port: number;
  user: string | null;
  from_addr: string;
  ssl: boolean;
}

export default function EmailSettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<MockUser | null>(null);
  const [status, setStatus] = useState<SmtpStatus | null>(null);
  const [testEmail, setTestEmail] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);
  const [testMsg, setTestMsg] = useState("");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) { router.replace("/login"); return; }
    setUser(u);
    setTestEmail(u.email || "");
    // Demo: SMTP ayarlarını göster (gerçekte backend'den çekilir)
    setStatus({
      host: "smtp.iso.org.tr",
      port: 587,
      user: "noreply@iso.org.tr",
      from_addr: "İSO Pulse <noreply@iso.org.tr>",
      ssl: false,
    });
  }, [router]);

  async function testBaglanti() {
    if (!testEmail.trim()) return;
    setTesting(true);
    setTestResult(null);
    setTestMsg("");
    try {
      const res = await fetch(`${API}/api/v1/hr/celebrations/email-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_email: testEmail }),
      });
      if (!res.ok) throw new Error("İstek başarısız");
      const data = await res.json();
      setTestResult("ok");
      setTestMsg(data.mesaj ?? "Test emaili gönderildi.");
    } catch (e: unknown) {
      setTestResult("error");
      setTestMsg(e instanceof Error ? e.message : "Bağlantı hatası");
    } finally {
      setTesting(false);
    }
  }

  const protocolLabel = status?.ssl ? "SSL (465)" : status?.port === 587 ? "STARTTLS (587)" : `Plain (${status?.port})`;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.back()}
              className="text-gray-500 hover:text-gray-800 text-sm flex items-center gap-1"
            >
              ← Geri
            </button>
            <div className="w-px h-5 bg-gray-200" />
            <div>
              <h1 className="font-semibold text-gray-900">Email Bağlantı Ayarları</h1>
              <p className="text-xs text-gray-500">İSO Pulse — SMTP Yapılandırma</p>
            </div>
          </div>
          {user && <NotificationBell userId={user.id} />}
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">

        {/* Bağlantı durumu */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">SMTP Bağlantı Durumu</h2>
            <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700
                             bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Aktif
            </span>
          </div>

          {status && (
            <div className="divide-y divide-gray-50">
              {[
                { label: "SMTP Sunucu", value: status.host },
                { label: "Protokol", value: protocolLabel },
                { label: "Gönderen Hesap", value: status.user ?? "Kimlik doğrulama yok" },
                { label: "Gönderen Adres", value: status.from_addr },
                { label: "Şifreleme", value: status.ssl ? "SSL/TLS" : status.port === 587 ? "STARTTLS" : "Yok (geliştirme)" },
              ].map(({ label, value }) => (
                <div key={label} className="px-6 py-3.5 flex items-center justify-between">
                  <span className="text-sm text-gray-500">{label}</span>
                  <span className="text-sm font-medium text-gray-900">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Email kategorileri */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Platform Email Kategorileri</h2>
            <p className="text-xs text-gray-500 mt-0.5">Platform üzerinden gönderilen email türleri</p>
          </div>
          <div className="divide-y divide-gray-50">
            {[
              { emoji: "🎂", baslik: "Doğum Günü Kutlamaları", aciklama: "Otomatik: her sabah 09:00 — Scheduler", tur: "scheduler" },
              { emoji: "🏆", baslik: "İşe Giriş Yıl Dönümleri", aciklama: "Otomatik: her sabah 09:00 — Scheduler", tur: "scheduler" },
              { emoji: "🎉", baslik: "Akran Kutlama Emailleri", aciklama: "Manuel: çalışan profil sayfasından tetiklenir", tur: "peer" },
              { emoji: "✅", baslik: "Bağlantı Test Emaili", aciklama: "Bu sayfadan elle test edilebilir", tur: "test" },
            ].map(({ emoji, baslik, aciklama, tur }) => (
              <div key={baslik} className="px-6 py-4 flex items-center gap-4">
                <span className="text-2xl">{emoji}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{baslik}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{aciklama}</p>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  tur === "scheduler" ? "bg-blue-50 text-blue-700"
                  : tur === "peer" ? "bg-violet-50 text-violet-700"
                  : "bg-gray-100 text-gray-600"
                }`}>
                  {tur === "scheduler" ? "Otomatik" : tur === "peer" ? "Manuel" : "Test"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Bağlantı testi */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Bağlantı Testi</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              SMTP bağlantısını doğrulamak için belirtilen adrese test emaili gönder
            </p>
          </div>
          <div className="p-6">
            <div className="flex gap-3">
              <input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="test@ornek.com"
                className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={testBaglanti}
                disabled={testing || !testEmail.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white
                           text-sm font-medium px-5 py-2.5 rounded-xl transition-colors whitespace-nowrap"
              >
                {testing ? "Gönderiliyor…" : "Test Et"}
              </button>
            </div>

            {testResult && (
              <div className={`mt-4 flex items-center gap-2 text-sm px-4 py-3 rounded-xl
                ${testResult === "ok"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-red-50 text-red-700 border border-red-200"}`}>
                <span>{testResult === "ok" ? "✅" : "❌"}</span>
                <span>{testMsg}</span>
              </div>
            )}
          </div>
        </div>

        {/* Yapılandırma notu */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-xs text-amber-700 font-medium mb-1">📋 Yapılandırma Notu</p>
          <p className="text-xs text-amber-600 leading-relaxed">
            SMTP ayarları sunucu ortam değişkenlerinden okunur (<code className="bg-amber-100 px-1 rounded">SMTP_HOST</code>,{" "}
            <code className="bg-amber-100 px-1 rounded">SMTP_PORT</code>,{" "}
            <code className="bg-amber-100 px-1 rounded">SMTP_USER</code>,{" "}
            <code className="bg-amber-100 px-1 rounded">SMTP_PASSWORD</code>,{" "}
            <code className="bg-amber-100 px-1 rounded">SMTP_FROM</code>).{" "}
            Değiştirmek için backend <code className="bg-amber-100 px-1 rounded">.env</code> dosyasını güncelleyip servisi yeniden başlatın.
          </p>
        </div>
      </div>
    </main>
  );
}

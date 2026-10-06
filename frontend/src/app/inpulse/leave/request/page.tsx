"use client";
/**
 * İzin Talebi Formu
 * URL: /inpulse/leave/request?tur=<izin_turu>
 * - Tarih seçimi
 * - Otomatik iş günü hesabı (API üzerinden)
 * - Neden alanı (opsiyonel)
 * - Bakiye kontrolü (yıllık izin için)
 * - Görev çakışma uyarısı (özel izinlerde devir zorunluluğu)
 */
import { useEffect, useState, Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createLeaveRequest, fetchBalance, fetchIzinTurleri, uploadLeaveDocument } from "@/lib/api";
import { createNotification } from "@/lib/notifications";
import { IzinTuruBilgi, IzinTuru, LeaveBalance } from "@/types/leave";
import { LeaveConflictInfo, TaskConflict, PRIORITY_LABELS, PRIORITY_DOT } from "@/types/tasks";
import { checkLeaveConflicts } from "@/lib/tasks";
import { getCurrentUser } from "@/lib/auth";

function ConflictPanel({ conflict, izinTuru }: { conflict: LeaveConflictInfo; izinTuru: string }) {
  if (conflict.cakisan_gorevler.length === 0) return null;

  const isOzel = conflict.ozel_izin;

  return (
    <div
      className={`rounded-xl border p-4 mb-5 ${
        isOzel
          ? "bg-red-50 border-red-200"
          : "bg-amber-50 border-amber-200"
      }`}
    >
      <div className="flex items-start gap-2 mb-3">
        <span className="text-lg flex-shrink-0">{isOzel ? "🚨" : "⚠️"}</span>
        <div>
          <p className={`text-sm font-semibold ${isOzel ? "text-red-800" : "text-amber-800"}`}>
            {isOzel
              ? "Özel izin — görev devri gerekiyor"
              : "İzin döneminde aktif görevleriniz var"}
          </p>
          <p className={`text-xs mt-0.5 ${isOzel ? "text-red-700" : "text-amber-700"}`}>
            {isOzel
              ? "Bu izin türü onaylandığında yöneticiniz aşağıdaki görevleri başka bir çalışana devredecektir."
              : "Bu görevler izin sürenizle çakışıyor. Yöneticiniz bilgilendirilecektir."}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {conflict.cakisan_gorevler.map((task: TaskConflict) => (
          <div
            key={task.task_id}
            className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs
              ${isOzel ? "bg-red-100" : "bg-amber-100"}`}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.oncelik]}`} />
              <span className={`font-medium truncate ${isOzel ? "text-red-900" : "text-amber-900"}`}>
                {task.baslik}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
              <span className={`${isOzel ? "text-red-600" : "text-amber-600"}`}>
                {PRIORITY_LABELS[task.oncelik]}
              </span>
              <span className={`${isOzel ? "text-red-500" : "text-amber-500"}`}>
                · {new Date(task.bitis_tarihi).toLocaleDateString("tr-TR")}
              </span>
            </div>
          </div>
        ))}
      </div>

      {isOzel && (
        <p className={`text-xs mt-3 text-red-600 font-medium`}>
          Talebi göndermek için devam edebilirsiniz — yöneticiniz onay aşamasında devir işlemini gerçekleştirecektir.
        </p>
      )}
    </div>
  );
}

function LeaveRequestForm() {
  const router = useRouter();
  const params = useSearchParams();
  const izinTuruKod = params.get("tur") as IzinTuru | null;

  // Giriş yapmış kullanıcıyı al — mock sabit ID yerine gerçek oturum
  const currentUser = getCurrentUser();
  const employeeId = currentUser?.id ?? "demo-employee-001";
  const managerId = "demo-manager-001"; // çakışma bildirimi için

  const [izinTuruBilgi, setIzinTuruBilgi] = useState<IzinTuruBilgi | null>(null);
  const [balance, setBalance] = useState<LeaveBalance | null>(null);
  const [cikis, setCikis] = useState("");
  const [giris, setGiris] = useState("");
  const [neden, setNeden] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [createdLeaveId, setCreatedLeaveId] = useState<string | null>(null);

  // Rapor yükleme (hastalık izni)
  const [raporFile, setRaporFile] = useState<File | null>(null);
  const [raporUploading, setRaporUploading] = useState(false);
  const [raporUploaded, setRaporUploaded] = useState(false);
  const [raporError, setRaporError] = useState<string | null>(null);

  // Çakışma durumu
  const [conflictInfo, setConflictInfo] = useState<LeaveConflictInfo | null>(null);
  const [conflictLoading, setConflictLoading] = useState(false);

  useEffect(() => {
    if (!izinTuruKod) return;
    Promise.all([fetchIzinTurleri(), fetchBalance(employeeId)]).then(([turleri, bakiye]) => {
      setIzinTuruBilgi(turleri.find((t) => t.kod === izinTuruKod) ?? null);
      setBalance(bakiye);
    });
  }, [izinTuruKod]);

  // Tarihlerin her ikisi de seçilince çakışma kontrolü
  const checkConflicts = useCallback(async () => {
    if (!cikis || !giris || !izinTuruKod) {
      setConflictInfo(null);
      return;
    }
    setConflictLoading(true);
    try {
      const info = await checkLeaveConflicts(employeeId, cikis, giris, izinTuruKod);
      setConflictInfo(info);
    } catch {
      // Çakışma kontrolü başarısız olsa da formu bloke etme
      setConflictInfo(null);
    } finally {
      setConflictLoading(false);
    }
  }, [cikis, giris, izinTuruKod]);

  useEffect(() => {
    if (cikis && giris) {
      checkConflicts();
    } else {
      setConflictInfo(null);
    }
  }, [cikis, giris, checkConflicts]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!izinTuruKod || !cikis || !giris) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createLeaveRequest(employeeId, {
        izin_turu: izinTuruKod,
        cikis_tarihi: cikis,
        giris_tarihi: giris,
        neden: neden || undefined,
      });
      setCreatedLeaveId(created.id);
      setSuccess(true);

      // Görev çakışması varsa yöneticiye ek bildirim gönder
      if (conflictInfo && conflictInfo.cakisan_gorevler.length > 0) {
        const gorevAdlari = conflictInfo.cakisan_gorevler
          .map((t) => t.baslik)
          .join(", ");
        const severity = conflictInfo.ozel_izin ? "🚨 Özel izin" : "⚠️ Dikkat";
        createNotification({
          user_id: managerId,
          tur: "leave_conflict",
          mesaj: `${severity} — İzin talebinde görev çakışması var: ${gorevAdlari}`,
          ilgili_leave_id: created.id,
        }).catch(() => {/* sessiz hata */});
      }

      // Hastalık izni değilse otomatik yönlendir
      // window.location kullanıyoruz: router.push() Next.js router cache nedeniyle
      // history sayfasını remount etmez, bu yüzden useEffect yeniden çalışmaz.
      if (izinTuruKod !== "hastalik") {
        setTimeout(() => { window.location.href = "/inpulse/leave/history"; }, 2000);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu");
    } finally {
      setLoading(false);
    }
  };

  if (!izinTuruKod) {
    return (
      <div className="p-8 text-center text-gray-500">
        İzin türü belirtilmedi.{" "}
        <Link href="/inpulse/leave" className="text-blue-600 underline">
          Geri dön
        </Link>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-lg mx-auto flex items-center gap-4">
          <Link href="/inpulse/leave" className="text-gray-400 hover:text-gray-600">
            ← Geri
          </Link>
          <div>
            <h1 className="font-semibold text-gray-900">
              {izinTuruBilgi?.label ?? izinTuruKod}
            </h1>
            <p className="text-xs text-gray-500">İzin talebi oluştur</p>
          </div>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-6 py-8">
        {/* Bakiye uyarısı */}
        {balance && izinTuruBilgi?.bakiyeden_dusuler && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl px-4 py-3 mb-6">
            <p className="text-sm text-orange-800">
              Bu izin bakiyenizden düşer.{" "}
              <span className="font-semibold">Mevcut: {Number(balance.bakiye).toFixed(1)} gün</span>
            </p>
          </div>
        )}

        {success ? (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
              <p className="text-3xl mb-2">✅</p>
              <p className="text-green-800 font-semibold">Talebiniz alındı!</p>
              <p className="text-sm text-green-600 mt-1">
                {izinTuruKod === "hastalik"
                  ? "Yöneticinize bildirim gönderildi. Doktor raporunuzu aşağıdan yükleyebilirsiniz."
                  : "Yöneticinize bildirim gönderildi. Geçmişe yönlendiriliyorsunuz…"}
              </p>
            </div>

            {/* Rapor yükleme — sadece hastalık izninde */}
            {izinTuruKod === "hastalik" && createdLeaveId && (
              <div className="bg-white rounded-xl border border-gray-100 p-6">
                <h2 className="font-semibold text-gray-900 text-sm mb-1">Doktor Raporu Yükle</h2>
                <p className="text-xs text-gray-500 mb-4">
                  Yöneticiniz ve İK, yüklediğiniz raporu onay aşamasında görebilecektir.
                </p>

                {raporUploaded ? (
                  <div className="flex flex-col items-center gap-2 py-4">
                    <p className="text-2xl">📎</p>
                    <p className="text-green-700 font-medium text-sm">Rapor başarıyla yüklendi</p>
                    <button
                      onClick={() => { window.location.href = "/inpulse/leave/history"; }}
                      className="mt-2 text-sm text-blue-600 hover:underline"
                    >
                      Geçmişe git →
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <label className="block">
                      <span className="text-xs font-medium text-gray-700">Dosya seç (PDF veya görsel)</span>
                      <input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={(e) => {
                          setRaporFile(e.target.files?.[0] ?? null);
                          setRaporError(null);
                        }}
                        className="mt-1 block w-full text-sm text-gray-600
                          file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0
                          file:text-xs file:font-medium file:bg-blue-50 file:text-blue-700
                          hover:file:bg-blue-100 cursor-pointer"
                      />
                    </label>
                    {raporError && (
                      <p className="text-xs text-red-600">{raporError}</p>
                    )}
                    <div className="flex gap-3">
                      <button
                        onClick={async () => {
                          if (!raporFile) { setRaporError("Lütfen bir dosya seçin"); return; }
                          setRaporUploading(true);
                          setRaporError(null);
                          try {
                            await uploadLeaveDocument(createdLeaveId, raporFile);
                            setRaporUploaded(true);
                          } catch (e: unknown) {
                            setRaporError(e instanceof Error ? e.message : "Yükleme başarısız");
                          } finally {
                            setRaporUploading(false);
                          }
                        }}
                        disabled={raporUploading || !raporFile}
                        className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium
                          hover:bg-blue-700 disabled:opacity-40 transition-colors"
                      >
                        {raporUploading ? "Yükleniyor…" : "📤 Raporu Yükle"}
                      </button>
                      <button
                        onClick={() => { window.location.href = "/inpulse/leave/history"; }}
                        className="py-2 px-4 border border-gray-300 rounded-lg text-sm text-gray-600
                          hover:bg-gray-50 transition-colors"
                      >
                        Atla
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-0">
            <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-5">
              {/* Çıkış tarihi */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  İzin Başlangıç Tarihi <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  value={cikis}
                  min={new Date().toISOString().split("T")[0]}
                  onChange={(e) => setCikis(e.target.value)}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">İzne çıkış tarihiniz</p>
              </div>

              {/* Giriş tarihi */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  İşe Giriş Tarihi <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  value={giris}
                  min={cikis || new Date().toISOString().split("T")[0]}
                  onChange={(e) => setGiris(e.target.value)}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">İzin dönüşü işe başlayacağınız tarih</p>
              </div>

              {/* Neden */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Açıklama
                  {izinTuruKod !== "yillik" && izinTuruKod !== "2saat" && (
                    <span className="text-red-500 ml-1">*</span>
                  )}
                </label>
                <textarea
                  value={neden}
                  onChange={(e) => setNeden(e.target.value)}
                  rows={3}
                  placeholder="İzin nedeninizi kısaca belirtin"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              {/* Hata */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}
            </div>

            {/* Çakışma paneli — form kartının dışında, submit butonunun üstünde */}
            {conflictLoading && cikis && giris && (
              <div className="mt-4 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
                <p className="text-xs text-gray-400 animate-pulse">Görev çakışmaları kontrol ediliyor…</p>
              </div>
            )}
            {!conflictLoading && conflictInfo && conflictInfo.cakisan_gorevler.length > 0 && (
              <div className="mt-4">
                <ConflictPanel conflict={conflictInfo} izinTuru={izinTuruKod} />
              </div>
            )}

            {/* Butonlar */}
            <div className="flex gap-3 pt-4">
              <Link
                href="/inpulse/leave"
                className="flex-1 py-2.5 border border-gray-300 rounded-lg text-sm text-center text-gray-700 hover:bg-gray-50"
              >
                Vazgeç
              </Link>
              <button
                type="submit"
                disabled={loading || !cikis || !giris}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium
                  disabled:opacity-40 hover:bg-blue-700 transition-colors"
              >
                {loading ? "Gönderiliyor…" : "Talebi Gönder"}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}

export default function LeaveRequestPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-gray-400">Yükleniyor…</div>}>
      <LeaveRequestForm />
    </Suspense>
  );
}

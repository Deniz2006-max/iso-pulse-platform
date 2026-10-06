"use client";
/**
 * İzin Türü Seçim Sayfası
 * "İzin Al" butonuna basıldıktan sonra açılan ilk sayfa.
 * Kullanıcı izin türünü seçince /inpulse/leave/request?tur=<kod> sayfasına geçer.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { fetchIzinTurleri, fetchBalance } from "@/lib/api";
import { IzinTuruBilgi, IzinTuru, LeaveBalance } from "@/types/leave";
import LeaveTypeSelector from "@/components/inpulse/LeaveTypeSelector";

const MOCK_EMPLOYEE_ID = "demo-employee-001";

export default function LeavePage() {
  const router = useRouter();
  const [izinTurleri, setIzinTurleri] = useState<IzinTuruBilgi[]>([]);
  const [balance, setBalance] = useState<LeaveBalance | null>(null);
  const [selected, setSelected] = useState<IzinTuru | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchIzinTurleri(),
      fetchBalance(MOCK_EMPLOYEE_ID),
    ])
      .then(([turleri, bakiye]) => {
        setIzinTurleri(turleri);
        setBalance(bakiye);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleDevam = () => {
    if (selected) {
      router.push(`/inpulse/leave/request?tur=${selected}`);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-4">
          <Link href="/inpulse" className="text-gray-400 hover:text-gray-600">
            ← Geri
          </Link>
          <div>
            <h1 className="font-semibold text-gray-900">İzin Talebi</h1>
            <p className="text-xs text-gray-500">İzin türünü seçin</p>
          </div>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Bakiye özet */}
        {balance && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-6 flex items-center justify-between">
            <span className="text-sm text-blue-700">Kullanılabilir yıllık izin bakiyeniz</span>
            <span className="text-xl font-bold text-blue-800">{Number(balance.bakiye).toFixed(1)} gün</span>
          </div>
        )}

        <h2 className="text-base font-semibold text-gray-700 mb-4">
          Almak istediğiniz izin türünü seçin
        </h2>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <LeaveTypeSelector
            izinTurleri={izinTurleri}
            selected={selected}
            onSelect={setSelected}
          />
        )}

        {/* Devam butonu */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleDevam}
            disabled={!selected}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium
              disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
          >
            Devam Et →
          </button>
        </div>
      </div>
    </main>
  );
}

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-white mb-2">İSO Pulse</h1>
        <p className="text-gray-400 mb-8">Hangi kanala gitmek istersiniz?</p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/inpulse"
            className="px-8 py-4 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors"
          >
            İnpulse<br />
            <span className="text-blue-200 text-sm font-normal">İç Kanal</span>
          </Link>
          <Link
            href="/outpulse"
            className="px-8 py-4 bg-gray-700 text-white rounded-xl font-semibold hover:bg-gray-600 transition-colors"
          >
            Outpulse<br />
            <span className="text-gray-400 text-sm font-normal">Mevzuat Radar</span>
          </Link>
        </div>
      </div>
    </main>
  );
}

"use client";
/**
 * Inpulse Chatbot Widget
 * Sağ alt köşede yüzen sohbet balonu.
 * İzin talebi, bakiye sorgulama, İK'ya mesaj gönderme.
 */
import { useEffect, useRef, useState } from "react";
import { sendChatMessage, sendHRMessage, QuickAction } from "@/lib/chat";

interface Message {
  role: "user" | "bot";
  text: string;
  quickActions?: QuickAction[];
  showHRButton?: boolean;
  leaveCreated?: boolean;
}

const SESSION_ID =
  typeof window !== "undefined"
    ? sessionStorage.getItem("chat_session") ??
      (() => {
        const id = crypto.randomUUID();
        sessionStorage.setItem("chat_session", id);
        return id;
      })()
    : "ssr-session";

const MOCK_EMPLOYEE_ID = "demo-employee-001";

// Markdown-ish basit renderer
function renderText(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br/>");
}

export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hrModal, setHRModal] = useState(false);
  const [hrMessage, setHRMessage] = useState("");
  const [hrSent, setHRSent] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // İlk açılışta karşılama mesajı
  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([
        {
          role: "bot",
          text: "Merhaba! 👋 İzin işlemlerin için buradayım. Ne yapmak istersin?",
          quickActions: [
            { label: "📅 İzin al", value: "yeni izin almak istiyorum" },
            { label: "📊 Bakiyemi gör", value: "izin bakiyem nedir" },
          ],
        },
      ]);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");

    setMessages((prev) => [...prev, { role: "user", text: msg }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(SESSION_ID, MOCK_EMPLOYEE_ID, msg);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: res.reply,
          quickActions: res.quick_actions,
          showHRButton: res.show_hr_button,
          leaveCreated: res.leave_created,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Bir hata oluştu. Lütfen tekrar dene." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleHRSend() {
    if (!hrMessage.trim()) return;
    try {
      await sendHRMessage(MOCK_EMPLOYEE_ID, hrMessage);
      setHRSent(true);
      setHRMessage("");
      setTimeout(() => {
        setHRModal(false);
        setHRSent(false);
      }, 2000);
    } catch {
      alert("Mesaj gönderilemedi.");
    }
  }

  return (
    <>
      {/* ── Yüzen buton ─────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-blue-600 hover:bg-blue-700
                   text-white rounded-full shadow-xl flex items-center justify-center
                   text-2xl transition-all active:scale-95"
        aria-label="Chatbot aç"
      >
        {open ? "✕" : "💬"}
      </button>

      {/* ── Chat paneli ──────────────────────────────────────────────── */}
      {open && (
        <div
          className="fixed bottom-24 right-6 z-50 w-80 sm:w-96 bg-white rounded-2xl
                     shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
          style={{ maxHeight: "70vh" }}
        >
          {/* Header */}
          <div className="bg-blue-600 px-4 py-3 flex items-center gap-2">
            <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-white font-bold text-sm">
              İ
            </div>
            <div>
              <p className="text-white font-semibold text-sm">İzin Asistanı</p>
              <p className="text-blue-200 text-xs">İnpulse · Online</p>
            </div>
          </div>

          {/* Mesajlar */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white rounded-br-sm"
                      : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm"
                  }`}
                >
                  {msg.role === "bot" ? (
                    <span dangerouslySetInnerHTML={{ __html: renderText(msg.text) }} />
                  ) : (
                    msg.text
                  )}

                  {/* Başarı işareti */}
                  {msg.leaveCreated && (
                    <div className="mt-2 flex items-center gap-1.5 text-green-600 text-xs font-medium">
                      <span className="text-base">🎉</span> Talep oluşturuldu!
                    </div>
                  )}

                  {/* Hızlı aksiyonlar */}
                  {msg.quickActions && msg.quickActions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {msg.quickActions.map((qa, j) => (
                        <button
                          key={j}
                          onClick={() => handleSend(qa.value)}
                          className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700
                                     border border-blue-200 rounded-full px-3 py-1 transition-colors"
                        >
                          {qa.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* İK Mesaj butonu */}
                  {msg.showHRButton && (
                    <button
                      onClick={() => setHRModal(true)}
                      className="mt-2 w-full text-xs bg-amber-50 hover:bg-amber-100
                                 text-amber-800 border border-amber-200 rounded-lg px-3 py-1.5
                                 font-medium transition-colors"
                    >
                      📩 İK'ya Mesaj At
                    </button>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
                  <span className="flex gap-1">
                    {[0, 1, 2].map((d) => (
                      <span
                        key={d}
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${d * 0.15}s` }}
                      />
                    ))}
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-100 bg-white">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Mesaj yaz…"
                className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2
                           focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className="w-9 h-9 bg-blue-600 hover:bg-blue-700 disabled:opacity-40
                           text-white rounded-xl flex items-center justify-center transition-colors"
              >
                ➤
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── İK Mesaj Modalı ─────────────────────────────────────────── */}
      {hrModal && (
        <div className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center px-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h3 className="font-semibold text-gray-900 mb-1">📩 İK'ya Mesaj Gönder</h3>
            <p className="text-xs text-gray-500 mb-4">
              Mesajın İK ekibine iletilecek, en kısa sürede dönüş yapılacak.
            </p>
            {hrSent ? (
              <div className="text-center py-4 text-green-600 font-medium">
                ✅ Mesajın İK'ya gönderildi!
              </div>
            ) : (
              <>
                <textarea
                  value={hrMessage}
                  onChange={(e) => setHRMessage(e.target.value)}
                  placeholder="Mesajınızı buraya yazın…"
                  rows={4}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm
                             focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => setHRModal(false)}
                    className="flex-1 border border-gray-200 text-gray-600 text-sm
                               rounded-xl py-2 hover:bg-gray-50 transition-colors"
                  >
                    İptal
                  </button>
                  <button
                    onClick={handleHRSend}
                    disabled={!hrMessage.trim()}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40
                               text-white text-sm rounded-xl py-2 transition-colors"
                  >
                    Gönder
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

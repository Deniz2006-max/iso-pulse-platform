const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface QuickAction {
  label: string;
  value: string;
}

export interface ChatApiResponse {
  session_id: string;
  reply: string;
  quick_actions: QuickAction[];
  leave_created: boolean;
  leave_id: string | null;
  show_hr_button: boolean;
}

export async function sendChatMessage(
  sessionId: string,
  employeeId: string,
  message: string
): Promise<ChatApiResponse> {
  const res = await fetch(`${API}/api/v1/hr/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      employee_id: employeeId,
      message,
    }),
  });
  if (!res.ok) throw new Error("Mesaj gönderilemedi");
  return res.json();
}

export async function sendHRMessage(
  employeeId: string,
  message: string
): Promise<{ success: boolean; info: string }> {
  const res = await fetch(`${API}/api/v1/hr/chat/hr-message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_id: employeeId, message }),
  });
  if (!res.ok) throw new Error("İK mesajı gönderilemedi");
  return res.json();
}

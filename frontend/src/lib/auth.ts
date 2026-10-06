/**
 * Mock Auth — localStorage tabanlı oturum yönetimi
 * Gerçek auth eklenince burası değiştirilecek.
 */

export type UserRole = "ik" | "yonetici" | "calisan";

export interface MockUser {
  id: string;
  name: string;
  role: UserRole;
  roleLabel: string;
  email: string;
  avatar: string;         // baş harfler
  isNewEmployee?: boolean; // İlk günü olan yeni çalışan → oryantasyon akışı
}

// Tüm demo kullanıcılar — login ekranında gösterilir
export const ALL_MOCK_USERS: MockUser[] = [
  {
    id: "demo-employee-001",
    name: "Zeynep Yılmaz",
    role: "calisan",
    roleLabel: "Çalışan",
    email: "zeynep.yilmaz@iso.org.tr",
    avatar: "ZY",
  },
  {
    id: "demo-employee-ayse",
    name: "Ayşe Aydın",
    role: "calisan",
    roleLabel: "Çalışan",
    email: "ayse.aydin@iso.org.tr",
    avatar: "AA",
    isNewEmployee: true,
  },
  {
    id: "demo-manager-001",
    name: "Mehmet Kaya",
    role: "yonetici",
    roleLabel: "Yönetici",
    email: "mehmet.kaya@iso.org.tr",
    avatar: "MK",
  },
  {
    id: "demo-hr-001",
    name: "Selin Arslan",
    role: "ik",
    roleLabel: "İnsan Kaynakları",
    email: "selin.arslan@iso.org.tr",
    avatar: "SA",
  },
];

// Geriye dönük uyumluluk için (mevcut kod role bazlı erişim yapıyorsa)
export const MOCK_USERS: Record<UserRole, MockUser> = {
  calisan: ALL_MOCK_USERS[0],
  yonetici: ALL_MOCK_USERS[2],
  ik: ALL_MOCK_USERS[3],
};

const STORAGE_KEY = "iso_pulse_user";

/** ID'ye göre giriş yap */
export function loginById(userId: string): MockUser | null {
  const user = ALL_MOCK_USERS.find((u) => u.id === userId);
  if (!user) return null;
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  }
  return user;
}

/** Geriye dönük uyumluluk — role göre giriş */
export function login(role: UserRole): MockUser {
  const user = MOCK_USERS[role];
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  }
  return user;
}

export function getCurrentUser(): MockUser | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    return JSON.parse(stored) as MockUser;
  } catch {
    return null;
  }
}

export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(STORAGE_KEY);
  }
}

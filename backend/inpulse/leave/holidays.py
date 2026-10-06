"""
2026 Türkiye Resmi Tatil Listesi ve İş Günü Hesaplama
4857 sayılı İş Kanunu — Pazar günleri + resmi tatiller çıkarılır.
"""
from datetime import date, timedelta

# ─── 2026 Resmi Tatilleri ────────────────────────────────────────────────────
# Not: Ramazan ve Kurban Bayramı tarihleri Hicri takvime göre değişir.
# 2026 için yaklaşık değerler (resmi ilanla güncellenmelidir).
TATIL_2026: set[date] = {
    # Yılbaşı
    date(2026, 1, 1),
    # Ramazan Bayramı (yaklaşık 20-22 Mart 2026 — 3 gün + arife)
    date(2026, 3, 19),   # Arife yarım gün (uygulamaya göre tam sayılabilir)
    date(2026, 3, 20),   # Ramazan Bayramı 1. gün
    date(2026, 3, 21),   # Ramazan Bayramı 2. gün
    date(2026, 3, 22),   # Ramazan Bayramı 3. gün
    # Ulusal Egemenlik ve Çocuk Bayramı
    date(2026, 4, 23),
    # Emek ve Dayanışma Günü
    date(2026, 5, 1),
    # Atatürk'ü Anma, Gençlik ve Spor Bayramı
    date(2026, 5, 19),
    # Kurban Bayramı (yaklaşık 27-30 Mayıs 2026 — 4 gün + arife)
    date(2026, 5, 26),   # Arife
    date(2026, 5, 27),   # Kurban Bayramı 1. gün
    date(2026, 5, 28),   # Kurban Bayramı 2. gün
    date(2026, 5, 29),   # Kurban Bayramı 3. gün
    date(2026, 5, 30),   # Kurban Bayramı 4. gün
    # Demokrasi ve Millî Birlik Günü
    date(2026, 7, 15),
    # Zafer Bayramı
    date(2026, 8, 30),
    # Cumhuriyet Bayramı
    date(2026, 10, 28),  # Arife yarım gün
    date(2026, 10, 29),  # Cumhuriyet Bayramı
}

# Önceki yıllar için genişletilebilir
TATIL_LISTESI: dict[int, set[date]] = {
    2026: TATIL_2026,
}


def is_tatil(gun: date) -> bool:
    """Verilen gün resmi tatil veya Pazar mı?"""
    if gun.weekday() == 6:   # Pazar
        return True
    yil_tatiller = TATIL_LISTESI.get(gun.year, set())
    return gun in yil_tatiller


def is_gunu_say(baslangic: date, bitis: date) -> int:
    """
    baslangic ile bitis (dahil) arasındaki iş günü sayısını hesaplar.
    Pazar günleri ve resmi tatiller hariç tutulur.
    Cumartesi iş günü sayılır (İSO uygulaması).
    """
    if bitis < baslangic:
        return 0
    gun_sayisi = 0
    gun = baslangic
    while gun <= bitis:
        if not is_tatil(gun):
            gun_sayisi += 1
        gun += timedelta(days=1)
    return gun_sayisi


def bir_sonraki_is_gunu(gun: date) -> date:
    """Verilen tarihten sonraki ilk iş gününü döndürür."""
    sonraki = gun + timedelta(days=1)
    while is_tatil(sonraki):
        sonraki += timedelta(days=1)
    return sonraki


def giris_tarihini_bul(cikis: date, sure_gun: int) -> date:
    """
    Çıkış tarihi ve iş günü sayısından giriş tarihini hesaplar.
    (Kullanıcı çıkış + gün sayısı girerse giriş tarihini otomatik bul)
    """
    sayac = 0
    gun = cikis
    while sayac < sure_gun:
        if not is_tatil(gun):
            sayac += 1
        if sayac < sure_gun:
            gun += timedelta(days=1)
    # Giriş = son iznin ertesi iş günü
    return bir_sonraki_is_gunu(gun)

"""
Chatbot Konuşma Motoru — kural tabanlı durum makinesi
Hiçbir LLM bağımlılığı yok; tüm mantık saf Python.

Akış:
  1. "izin almak istiyorum" → oturum sıfırla → hangi tür?
  2. İzin türü seçildi → ANINDA cinsiyet kontrolü → uygun değilse İK yönlendirme
  3. Tarih sor → tarih geldi → doğrula (çakışma / bakiye / geçmiş tarih)
  4. Özet göster → onay al → talebi oluştur + bakiyeyi güncelle
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from db.models import EmployeeProfile, LeaveRequest, LeaveBalance
from inpulse.leave.calculator import yillik_izin_hakki, bakiyeden_dusurmeli, IZIN_TURLERI
from inpulse.leave.holidays import is_gunu_say
from inpulse.chat.parser import (
    detect_intent, detect_leave_type, parse_date_range,
    cinsiyet_tahmin, normalize
)
from inpulse.chat.schemas import ChatResponse, QuickAction


# ─── Konuşma oturumu ─────────────────────────────────────────────────────────
class ConvSession:
    def __init__(self, session_id: str, employee_id: str):
        self.session_id = session_id
        self.employee_id = employee_id
        self.izin_turu: Optional[str] = None
        self.cikis_tarihi: Optional[date] = None
        self.giris_tarihi: Optional[date] = None
        self.neden: Optional[str] = None
        # Durum: start | await_type | await_dates | confirm | done
        self.state: str = "start"

    def reset(self):
        self.izin_turu = None
        self.cikis_tarihi = None
        self.giris_tarihi = None
        self.neden = None
        self.state = "start"


_sessions: dict[str, ConvSession] = {}


def get_or_create_session(session_id: str, employee_id: str) -> ConvSession:
    if session_id not in _sessions:
        _sessions[session_id] = ConvSession(session_id, employee_id)
    return _sessions[session_id]


# ─── Sabit etiketler ─────────────────────────────────────────────────────────
IZIN_TURU_LABELS = {
    "yillik":      "📅 Yıllık İzin",
    "evlilik":     "💍 Evlilik İzni",
    "olum":        "🕊️ Ölüm İzni",
    "baba_dogum":  "👶 Babalık İzni",
    "dogum_kadin": "🤱 Doğum İzni",
    "hastalik":    "🏥 Hastalık İzni",
    "ucretsiz":    "📋 Ücretsiz İzin",
    "2saat":       "⏱️ 2 Saat İzin",
    "2saat_uzeri": "⏰ Mazeret İzni",
    "idari":       "🏛️ İdari İzin",
}

# Tarih içerebilecek kelimeler — guardrail'i atlatmak için
TARIH_SINYALLERI = [
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran",
    "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
    "pazartesi", "salı", "çarşamba", "perşembe", "cuma",
    "yarın", "bugün", "hafta", "gün", "gun", "tarih",
]

# Oturumu sıfırlayacak "taze başlangıç" sinyalleri
FRESH_START_SINYALLER = [
    "yeni izin almak istiyorum",
    "izin almak istiyorum",
    "izin almak istiyor",
    "izin talep etmek",
    "yeni izin",
    "izin başvurusu",
]

# Açıklama çıkarmak için önekler
NEDEN_ONEKLERI = [
    "açıklama:", "açıklama :", "neden:", "neden :", "sebep:",
    "çünkü", "nedeniyle", "dolayı", "sebebiyle", "için not:",
]


def _izin_turu_listesi():
    return [QuickAction(label=lbl, value=kod) for kod, lbl in IZIN_TURU_LABELS.items()]


def _evet_hayir():
    return [
        QuickAction(label="✅ Evet, talebi oluştur", value="evet"),
        QuickAction(label="❌ İptal et",             value="iptal"),
    ]


def _yeni_talep():
    return [QuickAction(label="🆕 Yeni izin talebi", value="yeni izin almak istiyorum")]


def _kapsam_disi_cevap(session_id: str) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        reply=(
            "Bu konu İK departmanının sorumluluk alanına giriyor. "
            "Seni doğrudan İK ekibine yönlendiriyorum. "
            "Aşağıdaki butona tıklayarak İK'ya mesaj gönderebilirsin. 📩"
        ),
        show_hr_button=True,
        quick_actions=[QuickAction(label="🆕 İzin talebi oluştur", value="yeni izin almak istiyorum")],
    )


def _tarih_bekleniyor_cevap(session_id: str, izin_turu: str) -> ChatResponse:
    """Tarih beklerken konu dışı mesaj gelince nazikçe yönlendir."""
    tur_lbl = IZIN_TURU_LABELS.get(izin_turu, izin_turu)
    return ChatResponse(
        session_id=session_id,
        reply=(
            f"Ben şu an {tur_lbl} için **tarih** bekliyorum. "
            "Farklı bir konuda yardım almak istiyorsan İK ekibine ulaşabilirsin. 📩\n\n"
            "_Tarih örneği: 5 Ekim - 10 Ekim ya da yarın 3 gün_"
        ),
        show_hr_button=True,
        quick_actions=[QuickAction(label="❌ Talebi iptal et", value="iptal")],
    )


def _extract_neden(msg: str) -> Optional[str]:
    """
    Mesajdan açıklama metnini çıkarır.
    Örnekler: "Açıklama: doğurdum", "çünkü doğum yaptım"
    """
    m = msg.strip()
    ml = m.lower()

    # "Açıklama: ..." veya "Neden: ..." tarzı önekler
    for onek in ["açıklama:", "açıklama :", "neden:", "neden :", "sebep:"]:
        if ml.startswith(onek):
            return m[len(onek):].strip()

    # "çünkü ..." veya "... nedeniyle ..." içeren mesajların tamamı
    for anahtar in ["çünkü", "nedeniyle", "dolayı", "sebebiyle"]:
        if anahtar in ml:
            return m

    return None


# ─── Cinsiyet uyumu kontrolü ─────────────────────────────────────────────────
def _cinsiyet_uyumu_kontrol(
    izin_turu: str,
    employee: EmployeeProfile,
    session_id: str,
) -> Optional[ChatResponse]:
    """İzin türü çalışanın cinsiyetiyle uyumlu değilse hata döndürür."""
    cinsiyet = cinsiyet_tahmin(employee.ad_soyad)

    if izin_turu == "baba_dogum" and cinsiyet == "kadin":
        return ChatResponse(
            session_id=session_id,
            reply=(
                "⚠️ Babalık izni yalnızca erkek çalışanlara tanınmaktadır.\n\n"
                "Eğer **doğum (analık) iznine** başvurmak istiyorsanız "
                "'🤱 Doğum İzni al' seçeneğini kullanabilir ya da "
                "sorularınız için İK ekibine ulaşabilirsiniz."
            ),
            show_hr_button=True,
            quick_actions=[
                QuickAction(label="🤱 Doğum İzni al",    value="doğum izni almak istiyorum"),
                QuickAction(label="🆕 Farklı izin seç", value="yeni izin almak istiyorum"),
            ],
        )

    if izin_turu == "dogum_kadin" and cinsiyet == "erkek":
        return ChatResponse(
            session_id=session_id,
            reply=(
                "⚠️ Doğum (analık) izni yalnızca kadın çalışanlara tanınmaktadır.\n\n"
                "Eğer **babalık iznine** başvurmak istiyorsanız "
                "'👶 Babalık İzni al' seçeneğini kullanabilirsiniz."
            ),
            show_hr_button=True,
            quick_actions=[
                QuickAction(label="👶 Babalık İzni al", value="babalık izni almak istiyorum"),
                QuickAction(label="🆕 Farklı izin seç", value="yeni izin almak istiyorum"),
            ],
        )

    return None


# ─── Tarih / bakiye doğrulama ─────────────────────────────────────────────────
async def _dogrula(
    session: ConvSession,
    employee: EmployeeProfile,
    db: AsyncSession,
) -> Optional[str]:
    """Hata varsa Türkçe mesaj döndürür; yoksa None."""
    tur = session.izin_turu
    cikis = session.cikis_tarihi
    giris = session.giris_tarihi
    bugun = date.today()

    # 1️⃣ Geçmiş tarih
    if cikis < bugun:
        return "Seçtiğin başlangıç tarihi geçmişte kalıyor. Lütfen gelecekteki bir tarih seç."

    # 2️⃣ Kıdem kontrolü (yıllık izin için)
    if tur == "yillik":
        hak = yillik_izin_hakki(employee.ise_giris_tarihi)
        if hak == 0:
            kidem_gun = (bugun - employee.ise_giris_tarihi).days
            kalan = 365 - kidem_gun
            return (
                f"Yıllık izin hakkı kazanmak için işe girişinden itibaren 1 yıl tamamlanması gerekiyor. "
                f"Kıdeminiz yaklaşık {kidem_gun} gün; {kalan} gün sonra yıllık izin kullanabileceksin."
            )

    # 3️⃣ Çakışma kontrolü
    stmt = select(LeaveRequest).where(
        and_(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.durum.in_(["beklemede", "onaylandi"]),
            or_(
                and_(LeaveRequest.cikis_tarihi <= cikis, LeaveRequest.giris_tarihi > cikis),
                and_(LeaveRequest.cikis_tarihi < giris,  LeaveRequest.giris_tarihi >= giris),
                and_(LeaveRequest.cikis_tarihi >= cikis, LeaveRequest.giris_tarihi <= giris),
            ),
        )
    )
    result = await db.execute(stmt)
    mevcut = result.scalars().all()
    if mevcut:
        m = mevcut[0]
        return (
            f"Bu tarih aralığında zaten bir izin talebin var "
            f"({m.cikis_tarihi.strftime('%d.%m.%Y')} – {m.giris_tarihi.strftime('%d.%m.%Y')}, "
            f"durum: {m.durum}). Lütfen farklı bir tarih seç."
        )

    # 4️⃣ Bakiye kontrolü
    if bakiyeden_dusurmeli(tur):
        sure = Decimal(str(is_gunu_say(cikis, giris)))
        stmt_bal = select(LeaveBalance).where(
            and_(LeaveBalance.employee_id == employee.id, LeaveBalance.yil == bugun.year)
        )
        res_bal = await db.execute(stmt_bal)
        balance = res_bal.scalar_one_or_none()
        if balance and sure > balance.bakiye:
            return (
                f"Yeterli izin bakiyeniz yok. "
                f"Talep: {sure} iş günü, mevcut bakiye: {balance.bakiye} gün. "
                f"Daha kısa bir aralık seçebilir ya da ücretsiz izin kullanabilirsin."
            )

    return None


# ─── İzin talebi oluştur + bakiyeyi güncelle ─────────────────────────────────
async def _create_leave(
    session: ConvSession,
    employee: EmployeeProfile,
    db: AsyncSession,
) -> str:
    """
    Veritabanına izin talebi yazar.
    Bakiyeyi etkileyen izin türlerinde kullanilan alanını da günceller.
    """
    bugun = date.today()
    sure = Decimal(str(is_gunu_say(session.cikis_tarihi, session.giris_tarihi)))

    # Bakiye bağlantısı ve güncelleme
    balance_id = None
    if bakiyeden_dusurmeli(session.izin_turu):
        stmt_bal = select(LeaveBalance).where(
            and_(LeaveBalance.employee_id == employee.id, LeaveBalance.yil == bugun.year)
        )
        res_bal = await db.execute(stmt_bal)
        balance = res_bal.scalar_one_or_none()

        # Bakiye satırı yoksa oluştur
        if not balance:
            hak = yillik_izin_hakki(employee.ise_giris_tarihi, bugun.year)
            balance = LeaveBalance(
                id=str(uuid.uuid4()),
                employee_id=employee.id,
                yil=bugun.year,
                onceki_yildan=Decimal("0"),
                yillik_hak=hak,
                idari_eklenen=Decimal("0"),
                kullanilan=Decimal("0"),
            )
            db.add(balance)
            await db.flush()

        # balance_id kaydet; gerçek düşüm yönetici onayında yapılır
        balance_id = balance.id

    leave = LeaveRequest(
        id=str(uuid.uuid4()),
        employee_id=employee.id,
        balance_id=balance_id,
        izin_turu=session.izin_turu,
        cikis_tarihi=session.cikis_tarihi,
        giris_tarihi=session.giris_tarihi,
        sure_gun=sure,
        neden=session.neden,
        durum="beklemede",
        yonetici_id=employee.yonetici_id,
    )
    db.add(leave)
    await db.flush()
    return leave.id


# ─── Özet mesajı üret ─────────────────────────────────────────────────────────
def _olustur_ozet(session: ConvSession) -> str:
    tur_lbl = IZIN_TURU_LABELS.get(session.izin_turu, session.izin_turu)
    sure = is_gunu_say(session.cikis_tarihi, session.giris_tarihi)
    bitis_goster = session.giris_tarihi - timedelta(days=1)
    return (
        f"📋 **İzin Talebi Özeti:**\n"
        f"• Tür: {tur_lbl}\n"
        f"• Başlangıç: {session.cikis_tarihi.strftime('%d.%m.%Y')}\n"
        f"• Bitiş: {bitis_goster.strftime('%d.%m.%Y')}\n"
        f"• Süre: {sure} iş günü\n"
        f"• Açıklama: {session.neden or '—'}\n\n"
        "Talebi oluşturmamı ister misin?"
    )


# ─── Ana işleyici ─────────────────────────────────────────────────────────────
async def process_message(
    session_id: str,
    employee_id: str,
    message: str,
    db: AsyncSession,
) -> ChatResponse:
    session = get_or_create_session(session_id, employee_id)
    msg = message.strip()
    m = normalize(msg)

    # ── Çalışan profili ───────────────────────────────────────────────────────
    stmt = select(EmployeeProfile).where(EmployeeProfile.id == employee_id)
    result = await db.execute(stmt)
    employee = result.scalar_one_or_none()
    if not employee:
        return ChatResponse(
            session_id=session_id,
            reply="Çalışan profilin bulunamadı. Lütfen sistem yöneticisine başvur.",
        )

    # ── İptal sinyali ─────────────────────────────────────────────────────────
    IPTAL_SINYALLER = {"iptal", "vazgeç", "hayır", "hayir", "iptal et", "dur", "bırak"}
    if m in IPTAL_SINYALLER:
        session.reset()
        return ChatResponse(
            session_id=session_id,
            reply="Tamam, işlemi iptal ettim. Başka bir şey için yardımcı olabilir miyim?",
            quick_actions=[QuickAction(label="🆕 Yeni izin talebi", value="yeni izin almak istiyorum")],
        )

    # ── Taze başlangıç sinyali → oturumu sıfırla ─────────────────────────────
    if any(s in m for s in FRESH_START_SINYALLER):
        session.reset()

    # ── Onay bekleniyor ───────────────────────────────────────────────────────
    if session.state == "confirm":
        ONAY_KELIMELERI = {"evet", "onaylıyorum", "oluştur", "tamam", "ok", "okey",
                           "evet talebi oluştur", "evet, talebi oluştur"}

        if m in ONAY_KELIMELERI:
            hata = await _dogrula(session, employee, db)
            if hata:
                session.cikis_tarihi = None
                session.giris_tarihi = None
                session.state = "await_dates"
                return ChatResponse(
                    session_id=session_id,
                    reply=f"⚠️ {hata}\n\nBaşka bir tarih aralığı belirtmek ister misin?",
                )
            leave_id = await _create_leave(session, employee, db)
            session.reset()
            session.state = "done"
            return ChatResponse(
                session_id=session_id,
                reply=(
                    "✅ İzin talebiniz başarıyla oluşturuldu! "
                    "Yöneticinize bildirim gönderildi; onay bekleniyor."
                ),
                leave_created=True,
                leave_id=leave_id,
                quick_actions=_yeni_talep(),
            )

        # Confirm durumunda açıklama ekleme: "Açıklama: doğurdum"
        neden_yeni = _extract_neden(msg)
        if neden_yeni:
            session.neden = neden_yeni
            return ChatResponse(
                session_id=session_id,
                reply=_olustur_ozet(session),
                quick_actions=_evet_hayir(),
            )

        # Confirm durumunda kapsam dışı → guardrail
        # (Onay ya da açıklama beklenirken tamamen farklı bir mesaj)
        return ChatResponse(
            session_id=session_id,
            reply=(
                "Talebi onaylamak için **'✅ Evet, talebi oluştur'** butonuna basabilirsin "
                "ya da başka bir izin türü için iptal edebilirsin."
            ),
            quick_actions=_evet_hayir(),
        )

    # ── Done → taze başlangıç ─────────────────────────────────────────────────
    if session.state == "done":
        session.reset()

    # ── Niyet tespiti ─────────────────────────────────────────────────────────
    intent = detect_intent(msg)

    if intent == "selam":
        return ChatResponse(
            session_id=session_id,
            reply=(
                f"Merhaba {employee.ad_soyad.split()[0]}! 👋 "
                "İzin işlemlerin için yardımcı olabilirim. Ne yapmak istersin?"
            ),
            quick_actions=[
                QuickAction(label="📅 İzin al",      value="yeni izin almak istiyorum"),
                QuickAction(label="📊 Bakiyemi gör", value="izin bakiyem nedir"),
            ],
        )

    if intent == "kapsam_disi":
        return _kapsam_disi_cevap(session_id)

    # ── Bakiye sorgusu ────────────────────────────────────────────────────────
    BAKIYE_KELIMELERI = ("bakiye", "kaç günüm", "ne kadar iznim", "izin hakkım", "kalan izin", "bakiyem")
    if any(k in m for k in BAKIYE_KELIMELERI):
        stmt_bal = select(LeaveBalance).where(
            and_(LeaveBalance.employee_id == employee_id, LeaveBalance.yil == date.today().year)
        )
        res_bal = await db.execute(stmt_bal)
        balance = res_bal.scalar_one_or_none()
        if balance:
            satirlar = [
                f"📊 **{date.today().year} yılı izin bakiyeniz:**",
                f"• Yıllık hak: {balance.yillik_hak} gün",
            ]
            if balance.onceki_yildan > 0:
                satirlar.append(f"• Önceki yıldan devreden: {balance.onceki_yildan} gün")
            if balance.idari_eklenen > 0:
                satirlar.append(f"• İdari eklenen: {balance.idari_eklenen} gün")
            satirlar.append(f"• Kullanılan: {balance.kullanilan} gün")
            satirlar.append(f"• **Kalan bakiye: {balance.bakiye} gün**")
            return ChatResponse(
                session_id=session_id,
                reply="\n".join(satirlar),
                quick_actions=[QuickAction(label="📅 İzin al", value="yeni izin almak istiyorum")],
            )
        return ChatResponse(
            session_id=session_id,
            reply="Bakiye kaydın bulunamadı. İK ile iletişime geçebilirsin.",
            show_hr_button=True,
        )

    # ════════════════════════════════════════════════════════════════════════════
    # VERİ TOPLAMA AKIŞI
    # ════════════════════════════════════════════════════════════════════════════

    # ── ADIM 1: İzin türü ────────────────────────────────────────────────────
    if not session.izin_turu:
        detected_type = detect_leave_type(msg)
        if detected_type:
            cinsiyet_hatasi = _cinsiyet_uyumu_kontrol(detected_type, employee, session_id)
            if cinsiyet_hatasi:
                session.reset()
                return cinsiyet_hatasi
            session.izin_turu = detected_type

    if not session.izin_turu:
        session.state = "await_type"
        return ChatResponse(
            session_id=session_id,
            reply="Hangi tür izin almak istiyorsunuz? Aşağıdan seçebilir ya da yazabilirsin:",
            quick_actions=_izin_turu_listesi(),
        )

    # ── ADIM 2: Tarihler ─────────────────────────────────────────────────────
    if not session.cikis_tarihi:
        # Kullanıcı henüz tarih girerken izin türünü değiştirmek isteyebilir.
        # (Hızlı aksiyon butonları kodun kendisini gönderir: "baba_dogum" vb.)
        new_type = detect_leave_type(msg)
        if new_type and new_type != session.izin_turu:
            cinsiyet_hatasi = _cinsiyet_uyumu_kontrol(new_type, employee, session_id)
            if cinsiyet_hatasi:
                session.reset()
                return cinsiyet_hatasi
            session.izin_turu = new_type
            # Yeni tür belirlendi; tarih sormaya devam et (fall-through)

        cikis, giris = parse_date_range(msg)
        if cikis:
            session.cikis_tarihi = cikis
        if giris:
            session.giris_tarihi = giris
        if session.cikis_tarihi and not session.giris_tarihi:
            session.giris_tarihi = session.cikis_tarihi + timedelta(days=1)

    # Açıklama/neden çıkarma (tarih yoksa ya da ek mesaj olarak)
    if not session.neden:
        neden_cikar = _extract_neden(msg)
        if neden_cikar:
            session.neden = neden_cikar

    # Tarih yok → mesaj konu dışı mı kontrol et
    if not session.cikis_tarihi:
        session.state = "await_dates"

        # Mesajda hiç tarih sinyali yoksa ve kapsam dışı görünüyorsa guardrail
        mesajda_tarih_sinyali = (
            any(k in m for k in TARIH_SINYALLERI)
            or bool(re.search(r"\d", m))   # herhangi bir rakam
        )
        if not mesajda_tarih_sinyali:
            # Açıkça izinle ilgili değilse kapsam dışı yönlendirme
            # Eğer mesaj çok kısaysa (tek kelime) nazik hatırlatma yap
            if len(msg.split()) >= 3:
                return _tarih_bekleniyor_cevap(session_id, session.izin_turu)

        tur_lbl = IZIN_TURU_LABELS.get(session.izin_turu, session.izin_turu)
        return ChatResponse(
            session_id=session_id,
            reply=(
                f"{tur_lbl} seçildi. ✅\n\n"
                "İzin **başlangıç** ve **bitiş** tarihlerini belirt.\n"
                "_Örnek: 5 Ekim - 10 Ekim ya da yarın 3 gün_"
            ),
        )

    # ── ADIM 3: Doğrula ve onayla ────────────────────────────────────────────
    hata = await _dogrula(session, employee, db)
    if hata:
        session.cikis_tarihi = None
        session.giris_tarihi = None
        session.state = "await_dates"
        return ChatResponse(
            session_id=session_id,
            reply=f"⚠️ {hata}\n\nBaşka bir tarih aralığı belirtmek ister misin?",
        )

    session.state = "confirm"
    return ChatResponse(
        session_id=session_id,
        reply=_olustur_ozet(session),
        quick_actions=_evet_hayir(),
    )

from __future__ import annotations

from typing import TypedDict

from schemas.outputs import SourceName


class MockDocument(TypedDict):
    """Legislation snapshot that main.py hashes and diffs before graph invoke."""

    document_id: str
    source: SourceName
    title: str
    old_text: str | None
    new_text: str


NOISE_APPOINTMENT: MockDocument = {
    "document_id": "noise-appointment",
    "source": "resmi_gazete",
    "title": "Kayseri Valiliği İl Milli Eğitim Müdürlüğü atama kararı",
    "old_text": None,
    "new_text": (
        "T.C. Resmî Gazete\n"
        "Sayı: 32601\n\n"
        "MADDE 1 – Ahmet Yılmaz, Kayseri İl Milli Eğitim Müdürlüğüne "
        "vali yardımcısı olarak atanmıştır.\n"
        "MADDE 2 – Bu karar yayımı tarihinde yürürlüğe girer.\n"
    ),
}

IK_OVERTIME: MockDocument = {
    "document_id": "ik-overtime",
    "source": "sgk",
    "title": "Fazla çalışma süresi üst sınırının güncellenmesi",
    "old_text": (
        "MADDE 41 – Fazla çalışma süresinin toplamı bir yılda iki yüz yetmiş "
        "saatten fazla olamaz.\n"
        "İşveren, fazla çalışmayı yazılı talep ile belgelemek zorundadır.\n"
    ),
    "new_text": (
        "MADDE 41 – Fazla çalışma süresinin toplamı bir yılda üç yüz altmış "
        "saatten fazla olamaz.\n"
        "İşveren, fazla çalışmayı elektronik bordro ve yazılı onay ile belgelemek "
        "ve takip eden ayın onuna kadar SGK'ya bildirmek zorundadır.\n"
    ),
}

HUKUK_ENVIRONMENT: MockDocument = {
    "document_id": "hukuk-environment",
    "source": "resmi_gazete",
    "title": "Çevre izin belgesi yenileme süresinin kısaltılması",
    "old_text": (
        "MADDE 8 – Çevre izin belgesi beş yıl geçerlidir. Süresi bitmeden "
        "doksan gün önce yenileme başvurusu yapılır.\n"
        "Yaptırım: belgesiz faaliyet halinde idari para cezası uygulanır.\n"
    ),
    "new_text": (
        "MADDE 8 – Çevre izin belgesi üç yıl geçerlidir. Süresi bitmeden "
        "yüz yirmi gün önce yenileme başvurusu yapılır.\n"
        "Sanayi tesisleri emisyon ölçüm raporunu başvuruya eklemek zorundadır.\n"
        "Yaptırım: belgesiz faaliyet halinde faaliyet durdurulur ve idari para "
        "cezası uygulanır.\n"
    ),
}

MULTI_WAGE_TAX: MockDocument = {
    "document_id": "multi-wage-tax",
    "source": "resmi_gazete",
    "title": "Asgari ücret ve ücret istisnası tebliğ değişikliği",
    "old_text": (
        "MADDE 1 – Asgari ücret net 17.002 TL olarak uygulanır.\n"
        "MADDE 2 – Asgari ücrete kadar olan ücretler gelir vergisinden istisna değildir.\n"
        "SGK bildirimi izleyen ayın 23'üne kadar verilir.\n"
    ),
    "new_text": (
        "MADDE 1 – Asgari ücret net 22.104 TL olarak uygulanır. İşveren farkı "
        "bir sonraki bordroda ödemek zorundadır.\n"
        "MADDE 2 – Asgari ücrete kadar olan ücretler gelir vergisinden istisna edilir.\n"
        "SGK bildirimi izleyen ayın 26'sına kadar verilir. Geç bildirimde idari "
        "para cezası uygulanır.\n"
    ),
}

UN_ASSET_FREEZE: MockDocument = {
    "document_id": "un-asset-freeze",
    "source": "resmi_gazete",
    "title": "Malvarlığının Dondurulması Hakkında Cumhurbaşkanı Kararı",
    "old_text": None,
    "new_text": (
        "Birleşmiş Milletler Güvenlik Konseyi'nin 1267 sayılı kararı uyarınca "
        "ekli listedeki kişi ve kuruluşların malvarlığının dondurulması "
        "hakkında karar yürürlüğe girer.\n"
    ),
}

TEKNOKENT_BOUNDARY: MockDocument = {
    "document_id": "teknokent-boundary",
    "source": "resmi_gazete",
    "title": "Teknoloji Geliştirme Bölgesi Sınır ve Koordinat Değişikliği",
    "old_text": None,
    "new_text": (
        "Ekli krokiye göre teknokent / teknoloji geliştirme bölgesi sınır ve "
        "koordinatları yeniden belirlenmiştir. İmar planı ve belediye sınır "
        "düzenlemesi bu kararla birlikte uygulanır.\n"
    ),
}

KDV_RATE: MockDocument = {
    "document_id": "kdv-rate",
    "source": "resmi_gazete",
    "title": "Katma Değer Vergisi (KDV) tebliğ değişikliği",
    "old_text": None,
    "new_text": (
        "MADDE 1 – İmalatta uygulanan KDV oranı yüzde 20'den yüzde 18'e indirilir. "
        "Mükellefler e-fatura ve muhasebe kayıtlarını yeni orana göre tutar. "
        "Kamu ihale bedelleri yeni KDV dahil hesaplanır.\n"
    ),
}

ENERGY_TARIFF: MockDocument = {
    "document_id": "energy-tariff",
    "source": "resmi_gazete",
    "title": "Sanayi elektrik tarifesinin güncellenmesi",
    "old_text": None,
    "new_text": (
        "MADDE 1 – Sanayi abone grubu elektrik tarifesi kilovatsaat başına "
        "yüzde 12 artırılır. OSB ve imalatçı işverenler enerji maliyetini "
        "yeni tarifeye göre faturalandırmak zorundadır.\n"
    ),
}

WORK_PERMIT: MockDocument = {
    "document_id": "work-permit",
    "source": "resmi_gazete",
    "title": "Yabancı uyruklu çalışanlara çalışma izni usul değişikliği",
    "old_text": None,
    "new_text": (
        "MADDE 1 – İmalat işyerlerinde yabancı uyruklu işçi için çalışma izni "
        "başvurusu e-Devlet üzerinden verilir. İşveren izin belgesini özlük "
        "dosyasında saklamak zorundadır.\n"
    ),
}

TEKNOKENT_INCENTIVE: MockDocument = {
    "document_id": "teknokent-incentive",
    "source": "resmi_gazete",
    "title": "Teknoloji Geliştirme Bölgesi kurumlar vergisi istisnası",
    "old_text": None,
    "new_text": (
        "MADDE 1 – Teknokent / teknoloji geliştirme bölgesinde elde edilen "
        "kazançlar kurumlar vergisinden istisna edilir. İstisna oranı yüzde "
        "100 olarak uygulanır.\n"
    ),
}

OTV_RATE: MockDocument = {
    "document_id": "otv-rate",
    "source": "resmi_gazete",
    "title": "Özel Tüketim Vergisi (ÖTV) oranının güncellenmesi",
    "old_text": None,
    "new_text": (
        "MADDE 1 – Motorin özel tüketim vergisi (ÖTV) oranı yüzde 2,5 olarak "
        "uygulanır. İthalatçı ve imalatçı işverenler gümrük ve muhasebe "
        "kayıtlarını yeni tarife üzerinden tutmak zorundadır.\n"
    ),
}

MOCK_DOCUMENTS: dict[str, MockDocument] = {
    NOISE_APPOINTMENT["document_id"]: NOISE_APPOINTMENT,
    IK_OVERTIME["document_id"]: IK_OVERTIME,
    HUKUK_ENVIRONMENT["document_id"]: HUKUK_ENVIRONMENT,
    MULTI_WAGE_TAX["document_id"]: MULTI_WAGE_TAX,
    UN_ASSET_FREEZE["document_id"]: UN_ASSET_FREEZE,
    TEKNOKENT_BOUNDARY["document_id"]: TEKNOKENT_BOUNDARY,
    OTV_RATE["document_id"]: OTV_RATE,
    KDV_RATE["document_id"]: KDV_RATE,
    ENERGY_TARIFF["document_id"]: ENERGY_TARIFF,
    WORK_PERMIT["document_id"]: WORK_PERMIT,
    TEKNOKENT_INCENTIVE["document_id"]: TEKNOKENT_INCENTIVE,
}

DEFAULT_DOCUMENT_ID = "ik-overtime"


def list_documents() -> list[str]:
    return list(MOCK_DOCUMENTS)


def get_document(document_id: str) -> MockDocument:
    try:
        return MOCK_DOCUMENTS[document_id]
    except KeyError as exc:
        known = ", ".join(list_documents())
        raise KeyError(f"Unknown mock document '{document_id}'. Known ids: {known}") from exc

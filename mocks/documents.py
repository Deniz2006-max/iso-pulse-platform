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

MOCK_DOCUMENTS: dict[str, MockDocument] = {
    NOISE_APPOINTMENT["document_id"]: NOISE_APPOINTMENT,
    IK_OVERTIME["document_id"]: IK_OVERTIME,
    HUKUK_ENVIRONMENT["document_id"]: HUKUK_ENVIRONMENT,
    MULTI_WAGE_TAX["document_id"]: MULTI_WAGE_TAX,
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

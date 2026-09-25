from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from config.routing import core_departments
from config.settings import settings
from schemas.outputs import (
    DeliveryPayload,
    Department,
    DepartmentAnalysis,
    RelevanceResult,
    RouteDecision,
    Urgency,
    VerificationResult,
)

T = TypeVar("T", bound=BaseModel)

_NOISE_HINTS = (
    "atanmıştır",
    "atama kararı",
    "ihale",
    "sözleşmesi imzalanacaktır",
)

_URGENCY_BY_DOC: dict[str, Urgency] = {
    "ik-overtime": "medium",
    "hukuk-environment": "critical",
    "multi-wage-tax": "critical",
    "demo-4857-maternity": "medium",
    "demo-5510-manufacturing": "medium",
    "demo-6698-processing": "critical",
}


def complete(
    schema: type[T],
    system_prompt: str,
    user_prompt: str,
    context: dict[str, Any] | None = None,
) -> T:
    """Return a Pydantic instance. Mock by default; live LLM when configured."""
    if settings.use_mock_llm:
        return _mock_complete(schema, context or {})
    return _live_complete(schema, system_prompt, user_prompt)


def _live_complete(schema: type[T], system_prompt: str, user_prompt: str) -> T:
    from langchain_core.messages import HumanMessage, SystemMessage

    from config.llm import get_chat_model

    llm = get_chat_model()
    result = llm.with_structured_output(schema).invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    )
    if not isinstance(result, schema):
        return schema.model_validate(result)
    return result


def _mock_complete(schema: type[T], context: dict[str, Any]) -> T:
    if schema is RelevanceResult:
        return _mock_relevance(context)  # type: ignore[return-value]
    if schema is RouteDecision:
        return _mock_route(context)  # type: ignore[return-value]
    if schema is DepartmentAnalysis:
        return _mock_analysis(context)  # type: ignore[return-value]
    if schema is VerificationResult:
        return _mock_verification(context)  # type: ignore[return-value]
    if schema is DeliveryPayload:
        return _mock_delivery(context)  # type: ignore[return-value]
    raise TypeError(f"No mock response registered for {schema.__name__}")


def _blob(context: dict[str, Any]) -> str:
    return f"{context.get('title', '')}\n{context.get('new_text', '')}".lower()


def _mock_relevance(context: dict[str, Any]) -> RelevanceResult:
    text = _blob(context)
    if any(hint in text for hint in _NOISE_HINTS):
        return RelevanceResult(
            is_relevant=False,
            reason="Bireysel atama veya ihale ilanı; sanayici yükümlülüğü değişmiyor.",
        )
    return RelevanceResult(
        is_relevant=True,
        reason="Metin işveren yükümlülüğü, süre, bildirim veya yaptırım değiştiriyor.",
    )


def _mock_route(context: dict[str, Any]) -> RouteDecision:
    departments = core_departments(_blob(context)) or ["hukuk"]
    return RouteDecision(
        departments=departments,
        reason="Yalnızca doğrudan değişen çekirdek alana yönlendirildi: "
        + ", ".join(departments),
    )


def _mock_analysis(context: dict[str, Any]) -> DepartmentAnalysis:
    department: Department = context.get("department", "hukuk")
    document_id = context.get("document_id", "")
    chunk_ids = list(context.get("rag_chunk_ids") or [])
    builders = {
        "ik": _ik_analysis,
        "hukuk": _hukuk_analysis,
        "mali": _mali_analysis,
    }
    return builders[department](document_id, chunk_ids)


def _ik_analysis(document_id: str, chunk_ids: list[str]) -> DepartmentAnalysis:
    if document_id == "demo-4857-maternity":
        return DepartmentAnalysis(
            department="ik",
            summary=(
                "İş Kanunu m.74 analık izni korunur; doğum sonrası 10 iş günü "
                "ücretli babalık izni eklenir."
            ),
            obligation_change=(
                "İşveren, aynı işyerindeki baba işçiye on iş günü ücretli babalık "
                "izni vermek, işe dönüşte eşdeğer pozisyonu korumak ve izinleri "
                "özlük dosyası ile bordroya işlemek zorundadır."
            ),
            operational_impact=(
                "İK izin politikasını, vardiya planını ve bordro kodlarını güncellemeli; "
                "üye işletmeler işe dönüş protokolünü 15 gün önceden kurgulamalıdır."
            ),
            rag_chunk_ids=chunk_ids,
            citations=["Law No. 4857, Article 74", "on iş günü ücretli babalık izni"],
            confidence=0.91,
        )
    if document_id == "demo-5510-manufacturing":
        return DepartmentAnalysis(
            department="ik",
            summary=(
                "İmalat işyerlerinde 5510 geçici 108 prim teşviki iki yıldan altı yıla çıkar."
            ),
            obligation_change=(
                "Teşvik, süresinde verilen aylık prim ve hizmet belgesi ile e-bildirge "
                "kaydı şartına bağlanır. SGK bildirimi gecikirse teşvik düşer."
            ),
            operational_impact=(
                "İK ve SGK operasyonu e-bildirge takvimini ve teşvik yararlanma "
                "kontrol listesini imalat işyerleri için güncellemelidir."
            ),
            rag_chunk_ids=chunk_ids,
            citations=["Law No. 5510, Provisional Article 108", "e-bildirge"],
            confidence=0.9,
        )
    if document_id == "multi-wage-tax":
        return DepartmentAnalysis(
            department="ik",
            summary=(
                "Net asgari ücret 17.002 TL'den 22.104 TL'ye çıkar; fark bir sonraki "
                "bordroda ödenir. SGK bildirimi ayın 26'sına kayar."
            ),
            obligation_change=(
                "İşveren asgari ücret farkını izleyen bordroda ödemek ve SGK "
                "bildirimini ayın 26'sına kadar vermek zorundadır. Geç bildirimde "
                "idari para cezası uygulanır."
            ),
            operational_impact=(
                "İK bordro takvimini, sözleşme/ücret skalasını ve SGK e-bildirge "
                "kapanışını güncellemelidir."
            ),
            rag_chunk_ids=chunk_ids,
            citations=["MADDE 1", "SGK bildirimi izleyen ayın 26'sına kadar"],
            confidence=0.9,
        )
    return DepartmentAnalysis(
        department="ik",
        summary=(
            "Yıllık fazla çalışma tavanı 270 saatten 360 saate çıkar. Belgeleme "
            "elektronik bordro ve yazılı onaya bağlanır; SGK bildirimi ayın 10'una kadar."
        ),
        obligation_change=(
            "Sanayicinin hukuki tavanı genişler ancak operasyonel yükümlülük artar: "
            "elektronik belgeleme ve takip eden ayın onuna kadar SGK bildirimi zorunludur."
        ),
        operational_impact=(
            "PDKS/bordro yazılımı, fazla mesai onay akışı ve SGK dosyalama tarihi "
            "güncellenmelidir."
        ),
        rag_chunk_ids=chunk_ids,
        citations=["MADDE 41", "üç yüz altmış saat", "SGK'ya bildirmek"],
        confidence=0.88,
    )


def _hukuk_analysis(document_id: str, chunk_ids: list[str]) -> DepartmentAnalysis:
    if document_id == "demo-6698-processing":
        return DepartmentAnalysis(
            department="hukuk",
            summary=(
                "KVKK m.5'e işverenler için kayıt, aydınlatma ve 12 aylık silme "
                "yükümlülüğü eklenir."
            ),
            obligation_change=(
                "PDKS, kamera ve erişim kontrolünde dayanak şartı yazılı kayıt altına "
                "alınmalı; aydınlatma işe girişte tebliğ edilmeli; amaç sona erince "
                "veri 12 ay içinde silinmeli, yok edilmeli veya anonimleştirilmelidir."
            ),
            operational_impact=(
                "Üye sanayi işletmeleri VERBIS/aydınlatma metinlerini, saklama "
                "envanterini ve silme prosedürünü güncellemelidir. Aykırılıkta Kurul "
                "idari para cezası uygulayabilir."
            ),
            rag_chunk_ids=chunk_ids,
            citations=["Law No. 6698, Article 5", "aydınlatma metni", "on iki ay"],
            confidence=0.92,
        )
    return DepartmentAnalysis(
        department="hukuk",
        summary=(
            "Çevre izin belgesi geçerliliği 5 yıldan 3 yıla iner; yenileme 120 gün "
            "önce yapılmalı ve emisyon raporu eklenmelidir. Belgesiz faaliyette "
            "durdurma yaptırımı eklenir."
        ),
        obligation_change=(
            "Sanayici daha sık yenileme, daha erken başvuru ve emisyon ölçüm raporu "
            "sunmak zorundadır. Aksi halde faaliyet durdurulabilir."
        ),
        operational_impact=(
            "İzin takvimi, çevre danışmanı sözleşmeleri ve emisyon ölçüm planı "
            "yeniden kurulmalıdır."
        ),
        rag_chunk_ids=chunk_ids,
        citations=["MADDE 8", "üç yıl", "yüz yirmi gün", "faaliyet durdurulur"],
        confidence=0.87,
    )


def _mali_analysis(document_id: str, chunk_ids: list[str]) -> DepartmentAnalysis:
    if document_id == "demo-5510-manufacturing":
        return DepartmentAnalysis(
            department="mali",
            summary=(
                "İmalat sektöründe işveren hissesi prim teşviki altı yıla uzar; "
                "teşvik kodunun bordro ve muhasebede gösterilmesi zorunludur."
            ),
            obligation_change=(
                "Maliye birimi teşvik kodunu bordro/muhasebe kayıtlarında ayrı izlemek "
                "ve 31/12/2027 (uzatılırsa 2028) vadesine kadar yararlanma şartlarını "
                "denetlemek zorundadır."
            ),
            operational_impact=(
                "Maliyet modeli, prim tahakkuku ve teşvik mutabakatı güncellenmeli; "
                "İSO üyesi imalatçılar bütçe simülasyonunu yenilemelidir."
            ),
            rag_chunk_ids=chunk_ids,
            citations=["Law No. 5510, Article 81", "işveren hissesi prim teşviki"],
            confidence=0.89,
        )
    return DepartmentAnalysis(
        department="mali",
        summary=(
            "Asgari ücrete kadar ücretler gelir vergisinden istisna edilir; net "
            "asgari ücret 22.104 TL olur."
        ),
        obligation_change=(
            "Maliye birimi stopaj/istisna hesaplarını yeni tutara göre kurmak ve "
            "asgari ücret farkını bordroya yansıtmak zorundadır."
        ),
        operational_impact=(
            "Ücret motoru, muhtasar ve istisna kodları güncellenmeli; ilk bordroda "
            "fark kontrolü yapılmalıdır."
        ),
        rag_chunk_ids=chunk_ids,
        citations=["MADDE 2", "gelir vergisinden istisna edilir", "22.104 TL"],
        confidence=0.86,
    )


def _mock_verification(context: dict[str, Any]) -> VerificationResult:
    analyses = context.get("analyses") or {}
    if not analyses:
        return VerificationResult(
            passed=False,
            hallucination_score=0.6,
            needs_review=True,
            unsupported_claims=["Analiz boş; kaynak metinle karşılaştırılamadı."],
            notes="Uzman düğümü çıktısı yok.",
        )
    return VerificationResult(
        passed=True,
        hallucination_score=0.08,
        needs_review=False,
        unsupported_claims=[],
        notes="Özetler MADDE metinleri ve diff ile örtüşüyor.",
    )


def _mock_delivery(context: dict[str, Any]) -> DeliveryPayload:
    document_id = str(context.get("document_id", "unknown"))
    departments = list(context.get("departments") or [])
    analyses = context.get("analyses") or {}
    needs_review = bool(context.get("needs_review", False))
    hallucination_score = float(context.get("hallucination_score", 0.08))
    titles = {
        "ik-overtime": "Fazla çalışma tavanı ve SGK bildirim yükümlülüğü",
        "hukuk-environment": "Çevre izni süresi kısaldı, durdurma yaptırımı eklendi",
        "multi-wage-tax": "Asgari ücret, vergi istisnası ve SGK süresi değişti",
        "demo-4857-maternity": "Analık izni korunur, ücretli babalık izni eklenir",
        "demo-5510-manufacturing": "İmalat prim teşviki altı yıla uzatıldı",
        "demo-6698-processing": "KVKK işveren veri işleme şartları sıkılaştı",
    }
    summaries = {
        "ik-overtime": (
            "Yıllık fazla mesai 360 saate çıktı; elektronik belgeleme ve ayın 10'una "
            "kadar SGK bildirimi zorunlu."
        ),
        "hukuk-environment": (
            "İzin 3 yıl; 120 gün önce yenileme ve emisyon raporu şart. Belgesiz "
            "faaliyette durdurma riski var."
        ),
        "multi-wage-tax": (
            "Net asgari ücret 22.104 TL; asgari ücret istisnası geliyor. SGK "
            "bildirimi ayın 26'sına kaydı."
        ),
        "demo-4857-maternity": (
            "4857 m.74: on iş günü ücretli babalık izni ve işe dönüşte pozisyon "
            "koruma yükümlülüğü eklendi."
        ),
        "demo-5510-manufacturing": (
            "5510 geçici 108: imalat prim teşviki altı yıl; e-bildirge ve teşvik "
            "kodu şart."
        ),
        "demo-6698-processing": (
            "6698 m.5: işverenler aydınlatma, dayanak kaydı ve 12 aylık silme "
            "yükümlülüğüne tabi."
        ),
    }
    return DeliveryPayload(
        document_id=document_id,
        source=str(context.get("source", "resmi_gazete")),
        title=titles.get(document_id, str(context.get("title", "Mevzuat değişikliği"))),
        summary=summaries.get(
            document_id,
            "Sanayiciyi ilgilendiren yükümlülük değişikliği tespit edildi.",
        ),
        urgency=_URGENCY_BY_DOC.get(document_id, "low"),
        departments=departments,
        needs_review=needs_review,
        hallucination_score=hallucination_score,
        analyses=analyses,
    )

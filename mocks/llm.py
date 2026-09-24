from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from config.settings import settings
from schemas.outputs import (
    DeliveryPayload,
    Department,
    DepartmentAnalysis,
    OrientationReport,
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
_IK_HINTS = (
    "fazla çalışma",
    "asgari ücret",
    "sgk",
    "bordro",
    "iş kanunu",
)
_HUKUK_HINTS = (
    "çevre",
    "izin belgesi",
    "lisans",
    "faaliyet durdur",
    "emisyon",
)
_MALI_HINTS = (
    "vergi",
    "istisna",
    "fatura",
    "stopaj",
    "tevkifat",
)

_URGENCY_BY_DOC: dict[str, Urgency] = {
    "ik-overtime": "medium",
    "hukuk-environment": "critical",
    "multi-wage-tax": "critical",
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
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required when ISO_PULSE_USE_MOCK_LLM=false."
        )
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.model_name,
        temperature=settings.temperature,
        api_key=settings.openai_api_key,
    )
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
    if schema is OrientationReport:
        return _mock_orientation_report(context)  # type: ignore[return-value]
    raise TypeError(f"No mock response registered for {schema.__name__}")


def _mock_orientation_report(context: dict[str, Any]) -> OrientationReport:
    correct = int(context.get("correct") or 0)
    total = int(context.get("total_questions") or 0)
    incorrect = int(context.get("incorrect") or max(total - correct, 0))
    missed = [str(item) for item in (context.get("missed_prompts") or []) if item]
    if missed:
        gaps = [f"Tekrar edilmeli: {prompt}" for prompt in missed[:5]]
        recommendation = (
            "Yanlış yanıtlanan başlıkları İK ile gözden geçirin; "
            "ardından işe fiilen başlayabilirsiniz."
        )
    else:
        gaps = ["Kritik bir bilgi açığı görünmüyor."]
        recommendation = (
            "Oryantasyon başarılı; süreçlere güvenle devam edilebilir."
        )
    return OrientationReport(
        summary=(
            f"Oryantasyon tamamlandı. {total} sorudan {correct} doğru, "
            f"{incorrect} yanlış yanıtlandı."
        ),
        strengths=[
            "Eğitim adımları sırayla tamamlandı.",
            "Quiz sorularının tamamı cevaplandı.",
        ],
        gaps=gaps,
        recommendation=recommendation,
    )


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
    text = _blob(context)
    departments: list[Department] = []
    if any(hint in text for hint in _IK_HINTS):
        departments.append("ik")
    if any(hint in text for hint in _HUKUK_HINTS):
        departments.append("hukuk")
    if any(hint in text for hint in _MALI_HINTS):
        departments.append("mali")
    if not departments:
        departments = ["hukuk"]
    return RouteDecision(
        departments=departments,
        reason="Anahtar yükümlülük alanlarına göre yönlendirildi: "
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
    del document_id
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
    del document_id
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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from schemas.outputs import Department


class LawChunk(TypedDict):
    """One Chroma-like chunk. Only is_active=True rows are retrieved."""

    chunk_id: str
    department: Department
    text: str
    is_active: bool
    article: str


_SEED_CHUNKS: list[LawChunk] = [
    {
        "chunk_id": "ik-isk-41-active",
        "department": "ik",
        "is_active": True,
        "article": "İş Kanunu m.41",
        "text": (
            "Yürürlükteki İş Kanunu m.41: fazla çalışmanın yıllık üst sınırı, "
            "yazılı/elektronik belgeleme ve SGK'ya bildirim yükümlülüğü."
        ),
    },
    {
        "chunk_id": "ik-isk-41-passive",
        "department": "ik",
        "is_active": False,
        "article": "İş Kanunu m.41 (eski)",
        "text": (
            "Pasif versiyon: fazla çalışma süresi bir yılda iki yüz yetmiş saati "
            "aşamaz. Bu kayıt is_active=false olduğu için RAG'e girmez."
        ),
    },
    {
        "chunk_id": "ik-sgk-board-active",
        "department": "ik",
        "is_active": True,
        "article": "SGK bildirim usulü",
        "text": (
            "İşveren ücret ve fazla çalışma bildirimlerini SGK'ya süresi içinde "
            "vermekle yükümlüdür. Geç bildirim idari para cezasına yol açabilir."
        ),
    },
    {
        "chunk_id": "hukuk-cevre-8-active",
        "department": "hukuk",
        "is_active": True,
        "article": "Çevre İzin Yönetmeliği m.8",
        "text": (
            "Çevre izin belgesinin geçerlilik süresi, yenileme başvuru penceresi "
            "ve belgesiz faaliyette durdurma ile idari para cezası yaptırımı."
        ),
    },
    {
        "chunk_id": "hukuk-cevre-8-passive",
        "department": "hukuk",
        "is_active": False,
        "article": "Çevre İzin Yönetmeliği m.8 (eski)",
        "text": "Pasif versiyon: belge beş yıl geçerlidir, doksan gün önce yenilenir.",
    },
    {
        "chunk_id": "mali-gv-istisna-active",
        "department": "mali",
        "is_active": True,
        "article": "Gelir Vergisi ücret istisnası",
        "text": (
            "Asgari ücrete kadar olan ücretlerin gelir vergisi istisnası ve "
            "bordro/stopaj hesaplarına etkisi."
        ),
    },
    {
        "chunk_id": "mali-asgari-teblig-active",
        "department": "mali",
        "is_active": True,
        "article": "Asgari ücret tebliği",
        "text": (
            "Yürürlükteki net asgari ücret tutarı ve işverenin fark ödemesini "
            "izleyen bordroda yansıtma yükümlülüğü."
        ),
    },
]


def _overlap_score(query: str, chunk: LawChunk) -> int:
    tokens = {part for part in query.lower().replace("'", " ").split() if len(part) > 3}
    haystack = f"{chunk['text']} {chunk['article']}".lower()
    return sum(1 for token in tokens if token in haystack)


@dataclass
class InMemoryChromaRetriever:
    """Stand-in for ChromaDB. Swap this class for a real collection later."""

    chunks: list[LawChunk] = field(default_factory=lambda: list(_SEED_CHUNKS))

    def retrieve(
        self,
        query: str,
        department: Department,
        k: int = 3,
    ) -> list[LawChunk]:
        eligible = [
            chunk
            for chunk in self.chunks
            if chunk["is_active"] and chunk["department"] == department
        ]
        ranked = sorted(
            eligible,
            key=lambda chunk: _overlap_score(query, chunk),
            reverse=True,
        )
        return ranked[:k]


retriever = InMemoryChromaRetriever()

from __future__ import annotations

import pymupdf

from db.models import EmployeeProfile, OrientationResult
from schemas.outputs import OrientationReport

_LEFT = 56.0
_TOP = 56.0
_SIZE_TITLE = 18.0
_SIZE_HEADING = 13.0
_SIZE_BODY = 11.0
_LINE_GAP = 4.0


def report_from_result(result: OrientationResult) -> OrientationReport:
    stored = (result.scores_json or {}).get("report")
    if isinstance(stored, dict):
        return OrientationReport.model_validate(stored)
    return OrientationReport(
        summary=result.report_summary or "Oryantasyon raporu henüz özetlenmedi.",
        strengths=[],
        gaps=[],
        recommendation="",
    )


def _wrap(font: pymupdf.Font, text: str, fontsize: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for raw in (text.splitlines() or [""]):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.text_length(trial, fontsize) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]


def render_report_pdf(employee: EmployeeProfile, result: OrientationResult) -> bytes:
    report = report_from_result(result)
    scores = result.scores_json or {}
    font = pymupdf.Font("notos")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="Noto", fontbuffer=font.buffer)
    max_width = page.rect.width - 2 * _LEFT
    y = _TOP

    def write(text: str, *, size: float = _SIZE_BODY, gap_after: float = 8.0) -> None:
        nonlocal y
        for line in _wrap(font, text, size, max_width):
            if y > page.rect.height - 56:
                return
            page.insert_text((_LEFT, y), line, fontname="Noto", fontsize=size)
            y += size + _LINE_GAP
        y += gap_after

    completed = (
        result.completed_at.strftime("%d.%m.%Y %H:%M UTC")
        if result.completed_at
        else "-"
    )
    correct = scores.get("correct", 0)
    total = scores.get("total_questions", 0)

    write("İSO PULSE — Oryantasyon Raporu", size=_SIZE_TITLE, gap_after=12)
    write(f"{employee.full_name}  ·  {employee.department}")
    write(employee.email)
    write(f"Tamamlanma: {completed}    Skor: {correct}/{total}", gap_after=14)
    write("Özet", size=_SIZE_HEADING, gap_after=4)
    write(report.summary, gap_after=12)
    write("Güçlü yönler", size=_SIZE_HEADING, gap_after=4)
    for item in report.strengths:
        write(f"• {item}", gap_after=2)
    y += 8
    write("Gelişim alanları", size=_SIZE_HEADING, gap_after=4)
    for item in report.gaps:
        write(f"• {item}", gap_after=2)
    y += 8
    write("Öneri", size=_SIZE_HEADING, gap_after=4)
    write(report.recommendation)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

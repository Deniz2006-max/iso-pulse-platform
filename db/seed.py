from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from sqlalchemy import func, select, text

from db.models import (
    EmployeeProfile,
    OrientationAnswer,
    OrientationQuestion,
    OrientationResult,
    OrientationVideo,
    OrientationWatchEvent,
)
from db.session import session_scope

MODULES: list[dict] = [
    {
        "title": "Şirket tanıtımı",
        "description": "İSO Vakfı misyonu, organizasyon yapısı ve kurumsal iletişim kanallarına giriş (mock adım).",
        "source_url": None,
        "duration_seconds": 420,
        "sort_order": 1,
        "is_required": True,
        "questions": [
            {
                "prompt": "İSO Vakfı’nın temel amacı aşağıdakilerden hangisidir?",
                "choices": [
                    "Sanayiye nitelikli insan kaynağı kazandırmak",
                    "Borsa işlemlerini düzenlemek",
                    "Belediye ruhsatlarını onaylamak",
                    "Uluslararası gümrük tarifelerini belirlemek",
                ],
                "correct_index": 0,
                "sort_order": 1,
            },
            {
                "prompt": "Yeni çalışanlar kurumsal duyuruları öncelikle hangi kanaldan takip etmelidir?",
                "choices": [
                    "Kişisel sosyal medya hesapları",
                    "İç iletişim platformu ve resmi e-posta",
                    "Sadece koridor panoları",
                    "Dış basın bültenleri",
                ],
                "correct_index": 1,
                "sort_order": 2,
            },
            {
                "prompt": "Oryantasyon sürecinde ilk başvurulacak birim hangisidir?",
                "choices": [
                    "Satın alma",
                    "Bilgi işlem depo",
                    "İnsan kaynakları",
                    "Dış ilişkiler",
                ],
                "correct_index": 2,
                "sort_order": 3,
            },
        ],
    },
    {
        "title": "İş güvenliği",
        "description": "İşyeri güvenlik kuralları, acil durum ve kişisel koruyucu donanım (mock adım).",
        "source_url": None,
        "duration_seconds": 540,
        "sort_order": 2,
        "is_required": True,
        "questions": [
            {
                "prompt": "İş kazası veya ramak kala durumunda ilk yapılması gereken nedir?",
                "choices": [
                    "Olayı sosyal medyada paylaşmak",
                    "Güvenli alanı sağlamak ve ilgili birime bildirmek",
                    "Vardiya bitene kadar beklemek",
                    "Sadece takım arkadaşına sözlü söylemek",
                ],
                "correct_index": 1,
                "sort_order": 1,
            },
            {
                "prompt": "Kişisel koruyucu donanım (KKD) ne zaman kullanılmalıdır?",
                "choices": [
                    "Yalnızca denetim günlerinde",
                    "Yalnızca yöneticiler için",
                    "İlgili iş ve sahada her zaman",
                    "Sadece kış aylarında",
                ],
                "correct_index": 2,
                "sort_order": 2,
            },
        ],
    },
    {
        "title": "İK süreçleri",
        "description": "İzin, mesai ve performans süreçlerinin temel kuralları (mock adım).",
        "source_url": None,
        "duration_seconds": 360,
        "sort_order": 3,
        "is_required": True,
        "questions": [
            {
                "prompt": "Yıllık izin talebi nasıl iletilir?",
                "choices": [
                    "Sözlü olarak herhangi bir meslektaşa",
                    "İç kanal / İK izin formu üzerinden",
                    "Kişisel WhatsApp grubundan",
                    "Maaş bordrosuna not düşerek",
                ],
                "correct_index": 1,
                "sort_order": 1,
            },
            {
                "prompt": "Fazla mesai kaydı için doğru yaklaşım hangisidir?",
                "choices": [
                    "Önceden onay alınır ve sisteme işlenir",
                    "Ay sonunda toplu tahmin yazılır",
                    "Kayıt tutulmasına gerek yoktur",
                    "Sadece e-posta imzasında belirtilir",
                ],
                "correct_index": 0,
                "sort_order": 2,
            },
            {
                "prompt": "Oryantasyon quiz’ini tamamlamadan sonraki eğitim adımı ne olur?",
                "choices": [
                    "Otomatik olarak açılır",
                    "Yönetici adına tamamlanmış sayılır",
                    "Kilitli kalır; sorular cevaplanmalıdır",
                    "Sadece PDF indirilebilir",
                ],
                "correct_index": 2,
                "sort_order": 3,
            },
        ],
    },
]

NEW_EMPLOYEE = {
    "email": "ayse.demir@iso.org.tr",
    "full_name": "Ayşe Demir",
    "hire_date": date(2026, 9, 15),
    "department": "İnsan Kaynakları",
}

COMPLETED_EMPLOYEE = {
    "email": "mehmet.kaya@iso.org.tr",
    "full_name": "Mehmet Kaya",
    "hire_date": date(2025, 3, 3),
    "department": "Üretim",
}


def _already_seeded(session) -> bool:
    count = session.scalar(select(func.count()).select_from(OrientationVideo))
    return bool(count)


def _reset(session) -> None:
    session.execute(
        text(
            "TRUNCATE employee_profiles, orientation_videos, orientation_questions, "
            "orientation_watch_events, orientation_answers, orientation_results "
            "RESTART IDENTITY CASCADE"
        )
    )


def seed(*, reset: bool = False) -> None:
    with session_scope() as session:
        if reset:
            _reset(session)
            session.flush()
        elif _already_seeded(session):
            print("Orientation seed already present; skipping. Use --reset to recreate.")
            return

        videos: list[OrientationVideo] = []
        for module in MODULES:
            video = OrientationVideo(
                title=module["title"],
                description=module["description"],
                source_url=module["source_url"],
                duration_seconds=module["duration_seconds"],
                sort_order=module["sort_order"],
                is_required=module["is_required"],
            )
            for question in module["questions"]:
                video.questions.append(OrientationQuestion(**question))
            session.add(video)
            videos.append(video)

        new_hire = EmployeeProfile(**NEW_EMPLOYEE)
        completed = EmployeeProfile(**COMPLETED_EMPLOYEE)
        session.add_all([new_hire, completed])
        session.flush()

        now = datetime.now(timezone.utc)
        by_module: list[dict] = []
        total_correct = 0
        total_questions = 0

        for video in videos:
            session.add(
                OrientationWatchEvent(
                    employee_id=completed.id,
                    video_id=video.id,
                    completed_at=now,
                )
            )
            module_correct = 0
            for question in video.questions:
                # One intentional miss on the last question of the last module.
                miss = video.sort_order == 3 and question.sort_order == 3
                selected = (question.correct_index + 1) % len(question.choices) if miss else question.correct_index
                is_correct = selected == question.correct_index
                session.add(
                    OrientationAnswer(
                        employee_id=completed.id,
                        question_id=question.id,
                        selected_index=selected,
                        is_correct=is_correct,
                        answered_at=now,
                    )
                )
                if is_correct:
                    module_correct += 1
                    total_correct += 1
                total_questions += 1
            by_module.append(
                {
                    "video_id": video.id,
                    "title": video.title,
                    "correct": module_correct,
                    "total": len(video.questions),
                }
            )

        session.add(
            OrientationResult(
                employee_id=completed.id,
                scores_json={
                    "total_questions": total_questions,
                    "correct": total_correct,
                    "incorrect": total_questions - total_correct,
                    "by_module": by_module,
                    "report": {
                        "summary": (
                            "Oryantasyon tamamlandı. "
                            f"{total_questions} sorudan {total_correct} doğru, "
                            f"{total_questions - total_correct} yanlış yanıtlandı."
                        ),
                        "strengths": [
                            "Eğitim adımları sırayla tamamlandı.",
                            "Quiz sorularının tamamı cevaplandı.",
                        ],
                        "gaps": [
                            "Tekrar edilmeli: Oryantasyon quiz’ini tamamlamadan "
                            "sonraki eğitim adımı ne olur?"
                        ],
                        "recommendation": (
                            "Yanlış yanıtlanan başlıkları İK ile gözden geçirin; "
                            "ardından işe fiilen başlayabilirsiniz."
                        ),
                    },
                },
                report_summary=(
                    "Oryantasyon tamamlandı. "
                    f"{total_questions} sorudan {total_correct} doğru, "
                    f"{total_questions - total_correct} yanlış yanıtlandı."
                ),
                completed_at=now,
            )
        )

        print(
            "Seeded "
            f"{len(videos)} modules, "
            f"{sum(len(v.questions) for v in videos)} questions, "
            "2 employees "
            f"(new={new_hire.email}, completed={completed.email})."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed orientation mock modules and employees.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate orientation tables and re-seed.",
    )
    args = parser.parse_args(argv)
    seed(reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

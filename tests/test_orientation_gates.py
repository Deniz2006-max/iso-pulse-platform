from __future__ import annotations

import pytest

from orientation.service import (
    all_questions_answered,
    can_unlock_step,
    marked_complete,
    previous_required_step,
    quiz_available,
)
from tests.helpers import add_step, answer_questions, complete_step


def test_first_required_step_is_unlocked_for_new_employee(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    add_step(session, title="İş güvenliği", sort_order=2)

    assert can_unlock_step(employee.id, first.id, session) is True
    assert can_unlock_step(employee.id, first, session) is True
    assert quiz_available(employee.id, first.id, session) is False


def test_second_step_locked_until_previous_video_completed(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    second = add_step(session, title="İş güvenliği", sort_order=2)

    answer_questions(session, employee.id, first)
    assert marked_complete(employee.id, first, session) is False
    assert can_unlock_step(employee.id, second.id, session) is False


def test_second_step_locked_until_all_previous_questions_answered(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1, question_count=3)
    second = add_step(session, title="İş güvenliği", sort_order=2)

    complete_step(session, employee.id, first)
    answer_questions(session, employee.id, first, limit=2)

    assert marked_complete(employee.id, first, session) is True
    assert all_questions_answered(employee.id, first, session) is False
    assert can_unlock_step(employee.id, second.id, session) is False

    answer_questions(session, employee.id, first, skip=2, limit=1)
    assert all_questions_answered(employee.id, first, session) is True
    assert can_unlock_step(employee.id, second.id, session) is True


def test_incorrect_answers_still_unlock_next_step(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    second = add_step(session, title="İş güvenliği", sort_order=2)

    complete_step(session, employee.id, first)
    answer_questions(session, employee.id, first, correct=False)

    assert can_unlock_step(employee.id, second.id, session) is True


def test_third_step_stays_locked_until_second_quiz_done(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    second = add_step(session, title="İş güvenliği", sort_order=2)
    third = add_step(session, title="İK süreçleri", sort_order=3)

    complete_step(session, employee.id, first)
    answer_questions(session, employee.id, first)
    assert can_unlock_step(employee.id, second.id, session) is True
    assert can_unlock_step(employee.id, third.id, session) is False
    assert quiz_available(employee.id, second.id, session) is False

    complete_step(session, employee.id, second)
    assert quiz_available(employee.id, second.id, session) is True
    assert can_unlock_step(employee.id, third.id, session) is False

    answer_questions(session, employee.id, second)
    assert can_unlock_step(employee.id, third.id, session) is True


def test_previous_required_step_skips_optional_modules(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    add_step(session, title="Ek kaynak", sort_order=2, is_required=False, question_count=1)
    third = add_step(session, title="İş güvenliği", sort_order=3)

    prev = previous_required_step(third, session)
    assert prev is not None
    assert prev.id == first.id

    complete_step(session, employee.id, first)
    answer_questions(session, employee.id, first)
    assert can_unlock_step(employee.id, third.id, session) is True


def test_step_with_no_questions_unlocks_after_complete(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1, question_count=0)
    second = add_step(session, title="İş güvenliği", sort_order=2)

    complete_step(session, employee.id, first)
    assert all_questions_answered(employee.id, first, session) is True
    assert can_unlock_step(employee.id, second.id, session) is True


def test_quiz_not_available_on_locked_step_even_if_marked_complete(session, employee):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1)
    second = add_step(session, title="İş güvenliği", sort_order=2)

    complete_step(session, employee.id, second)
    assert can_unlock_step(employee.id, second.id, session) is False
    assert quiz_available(employee.id, second.id, session) is False

    complete_step(session, employee.id, first)
    answer_questions(session, employee.id, first)
    assert quiz_available(employee.id, second.id, session) is True


def test_unknown_step_raises_lookup_error(session, employee):
    with pytest.raises(LookupError):
        can_unlock_step(employee.id, 999, session)

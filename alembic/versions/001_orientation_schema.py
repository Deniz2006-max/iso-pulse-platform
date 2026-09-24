"""Create orientation schema tables.

Revision ID: 001_orientation
Revises:
Create Date: 2026-09-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_orientation"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("department", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("email", name="uq_employee_profiles_email"),
    )
    op.create_table(
        "orientation_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_table(
        "orientation_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("choices", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "correct_index >= 0",
            name="ck_orientation_questions_correct_index",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["orientation_videos.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_orientation_questions_video_id",
        "orientation_questions",
        ["video_id"],
    )
    op.create_table(
        "orientation_watch_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employee_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["orientation_videos.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "employee_id",
            "video_id",
            name="uq_orientation_watch_events_employee_video",
        ),
    )
    op.create_index(
        "ix_orientation_watch_events_employee_id",
        "orientation_watch_events",
        ["employee_id"],
    )
    op.create_index(
        "ix_orientation_watch_events_video_id",
        "orientation_watch_events",
        ["video_id"],
    )
    op.create_table(
        "orientation_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "selected_index >= 0",
            name="ck_orientation_answers_selected_index",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employee_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["orientation_questions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "employee_id",
            "question_id",
            name="uq_orientation_answers_employee_question",
        ),
    )
    op.create_index(
        "ix_orientation_answers_employee_id",
        "orientation_answers",
        ["employee_id"],
    )
    op.create_index(
        "ix_orientation_answers_question_id",
        "orientation_answers",
        ["question_id"],
    )
    op.create_table(
        "orientation_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("scores_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report_summary", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employee_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("employee_id", name="uq_orientation_results_employee_id"),
    )


def downgrade() -> None:
    op.drop_table("orientation_results")
    op.drop_index("ix_orientation_answers_question_id", table_name="orientation_answers")
    op.drop_index("ix_orientation_answers_employee_id", table_name="orientation_answers")
    op.drop_table("orientation_answers")
    op.drop_index("ix_orientation_watch_events_video_id", table_name="orientation_watch_events")
    op.drop_index(
        "ix_orientation_watch_events_employee_id",
        table_name="orientation_watch_events",
    )
    op.drop_table("orientation_watch_events")
    op.drop_index("ix_orientation_questions_video_id", table_name="orientation_questions")
    op.drop_table("orientation_questions")
    op.drop_table("orientation_videos")
    op.drop_table("employee_profiles")

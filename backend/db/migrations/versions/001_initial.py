"""001 initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── employee_profiles ────────────────────────────────────────────────────
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ad_soyad", sa.String(120), nullable=False),
        sa.Column("sube", sa.String(100)),
        sa.Column("ise_giris_tarihi", sa.Date, nullable=False),
        sa.Column("dogum_tarihi", sa.Date),
        sa.Column("email", sa.String(200)),
        sa.Column("yonetici_id", sa.String(36), sa.ForeignKey("employee_profiles.id")),
        sa.Column("is_hr", sa.Boolean, default=False),
        sa.Column("is_yonetici", sa.Boolean, default=False),
        sa.Column("aktif", sa.Boolean, default=True),
        sa.Column("olusturma", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── leave_balance ────────────────────────────────────────────────────────
    op.create_table(
        "leave_balance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employee_profiles.id"), nullable=False),
        sa.Column("yil", sa.Integer, nullable=False),
        sa.Column("onceki_yildan", sa.Numeric(5, 1), default=0),
        sa.Column("yillik_hak", sa.Numeric(5, 1), nullable=False),
        sa.Column("idari_eklenen", sa.Numeric(5, 1), default=0),
        sa.Column("kullanilan", sa.Numeric(5, 1), default=0),
        sa.Column("olusturma", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("guncelleme", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "yil", name="uq_employee_yil"),
    )

    # ── leave_requests ───────────────────────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employee_profiles.id"), nullable=False),
        sa.Column("balance_id", sa.String(36), sa.ForeignKey("leave_balance.id")),
        sa.Column("izin_turu", sa.String(30), nullable=False),
        sa.Column("cikis_tarihi", sa.Date, nullable=False),
        sa.Column("giris_tarihi", sa.Date, nullable=False),
        sa.Column("sure_gun", sa.Numeric(5, 2)),
        sa.Column("neden", sa.Text),
        sa.Column("durum", sa.String(20), default="beklemede"),
        sa.Column("ret_nedeni", sa.Text),
        sa.Column("yonetici_id", sa.String(36), sa.ForeignKey("employee_profiles.id")),
        sa.Column("olusturma", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("guncelleme", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── mevzuat_kayitlar (outpulse) ──────────────────────────────────────────
    op.create_table(
        "mevzuat_kayitlar",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kaynak", sa.String(50), nullable=False),
        sa.Column("baslik", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("icerik_hash", sa.String(64)),
        sa.Column("ozet", sa.Text),
        sa.Column("kategori", sa.String(50)),
        sa.Column("yayin_tarihi", sa.Date),
        sa.Column("chroma_id", sa.String(100)),
        sa.Column("bildirim_gonderildi", sa.Boolean, default=False),
        sa.Column("olusturma", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── İndeksler ────────────────────────────────────────────────────────────
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_requests_durum", "leave_requests", ["durum"])
    op.create_index("ix_leave_requests_cikis_tarihi", "leave_requests", ["cikis_tarihi"])
    op.create_index("ix_mevzuat_hash", "mevzuat_kayitlar", ["icerik_hash"])


def downgrade() -> None:
    op.drop_table("mevzuat_kayitlar")
    op.drop_table("leave_requests")
    op.drop_table("leave_balance")
    op.drop_table("employee_profiles")

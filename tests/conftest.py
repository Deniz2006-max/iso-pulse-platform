from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, EmployeeProfile


def _use_sqlite_json() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()


@pytest.fixture
def session() -> Iterator[Session]:
    _use_sqlite_json()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def employee(session: Session) -> EmployeeProfile:
    profile = EmployeeProfile(
        email="ayse.demir@iso.org.tr",
        full_name="Ayşe Demir",
        hire_date=date(2026, 9, 15),
        department="İnsan Kaynakları",
    )
    session.add(profile)
    session.flush()
    return profile

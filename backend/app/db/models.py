from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceStatusState(Base):
    __tablename__ = "service_status_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecognizedBlank(Base):
    __tablename__ = "recognized_blanks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Header cells
    variant_01: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_02: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_03: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_04: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_01: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_02: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_03: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_04: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_05: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_06: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_07: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_08: Mapped[str | None] = mapped_column(Text, nullable=True)

    reg_number_01: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_02: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_03: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_04: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_05: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_06: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_07: Mapped[str | None] = mapped_column(Text, nullable=True)
    reg_number_08: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Answers grid: 10 rows × 9 columns
    answer_r01_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r01_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r02_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r02_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r03_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r03_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r04_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r04_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r05_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r05_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r06_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r06_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r07_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r07_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r08_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r08_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r09_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r09_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    answer_r10_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_r10_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Replacement grid: 10 rows × 9 columns
    repl_r01_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r01_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r02_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r02_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r03_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r03_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r04_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r04_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r05_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r05_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r06_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r06_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r07_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r07_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r08_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r08_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r09_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r09_c09: Mapped[str | None] = mapped_column(Text, nullable=True)

    repl_r10_c01: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c02: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c03: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c04: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c05: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c06: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c07: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c08: Mapped[str | None] = mapped_column(Text, nullable=True)
    repl_r10_c09: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

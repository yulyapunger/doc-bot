from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Manager(Base):
    __tablename__ = "managers"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class TourTemplate(Base):
    __tablename__ = "tour_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    hotel: Mapped[str] = mapped_column(String(255), nullable=False)
    check_in_date: Mapped[str | None] = mapped_column(String(20))   # ДД.ММ.ГГГГ
    check_out_date: Mapped[str | None] = mapped_column(String(20))
    nights: Mapped[int | None] = mapped_column(Integer)
    room_type: Mapped[str | None] = mapped_column(String(100))
    room_count: Mapped[str | None] = mapped_column(String(10))      # "1" или "½"
    meal_type: Mapped[str | None] = mapped_column(String(50))
    transfer: Mapped[str] = mapped_column(String(50), default="none")
    insurance: Mapped[bool] = mapped_column(Boolean, default=False)
    additional_conditions: Mapped[str | None] = mapped_column(Text)
    payment_deadline: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(BigInteger)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="tour_template")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    contract_date: Mapped[str] = mapped_column(String(20), nullable=False)   # ДД.ММ.ГГГГ
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False)   # individual / legal
    tour_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tour_templates.id"))
    manager_telegram_id: Mapped[int] = mapped_column(BigInteger)
    gdrive_file_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tour_template: Mapped["TourTemplate | None"] = relationship(back_populates="contracts")


class ContractCounter(Base):
    __tablename__ = "contract_counter"

    # "individual" или "legal"
    contract_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False)

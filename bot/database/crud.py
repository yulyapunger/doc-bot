from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Contract, ContractCounter, Manager, TourTemplate


# ── Managers ──────────────────────────────────────────────────────────────────

async def is_manager(session: AsyncSession, telegram_id: int) -> bool:
    result = await session.execute(
        select(Manager).where(Manager.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none() is not None


async def add_manager(session: AsyncSession, telegram_id: int, name: str) -> Manager:
    manager = Manager(telegram_id=telegram_id, name=name)
    session.add(manager)
    await session.commit()
    return manager


# ── Contract counter ───────────────────────────────────────────────────────────

async def counter_initialized(session: AsyncSession, contract_type: str) -> bool:
    result = await session.execute(
        select(ContractCounter).where(ContractCounter.contract_type == contract_type)
    )
    return result.scalar_one_or_none() is not None


async def init_counter(session: AsyncSession, contract_type: str, start_value: int) -> None:
    counter = ContractCounter(contract_type=contract_type, current_value=start_value)
    session.add(counter)
    await session.commit()


async def get_next_number(session: AsyncSession, contract_type: str) -> int:
    """Возвращает текущее значение счётчика (не инкрементирует)."""
    result = await session.execute(
        select(ContractCounter).where(ContractCounter.contract_type == contract_type)
    )
    counter = result.scalar_one()
    return counter.current_value


async def increment_counter(session: AsyncSession, contract_type: str) -> int:
    """Инкрементирует счётчик и возвращает новое значение."""
    result = await session.execute(
        select(ContractCounter).where(ContractCounter.contract_type == contract_type)
    )
    counter = result.scalar_one()
    counter.current_value += 1
    await session.commit()
    return counter.current_value


# ── Tour templates ─────────────────────────────────────────────────────────────

async def get_all_templates(session: AsyncSession) -> list[TourTemplate]:
    result = await session.execute(
        select(TourTemplate).order_by(TourTemplate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_template(session: AsyncSession, template_id: int) -> TourTemplate | None:
    result = await session.execute(
        select(TourTemplate).where(TourTemplate.id == template_id)
    )
    return result.scalar_one_or_none()


async def create_template(session: AsyncSession, data: dict, created_by: int) -> TourTemplate:
    template = TourTemplate(**data, created_by=created_by)
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def update_template(session: AsyncSession, template_id: int, data: dict) -> TourTemplate:
    await session.execute(
        update(TourTemplate).where(TourTemplate.id == template_id).values(**data)
    )
    await session.commit()
    return await get_template(session, template_id)


async def delete_template(session: AsyncSession, template_id: int) -> None:
    result = await session.execute(
        select(TourTemplate).where(TourTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template:
        await session.delete(template)
        await session.commit()


# ── Contracts ──────────────────────────────────────────────────────────────────

async def save_contract(session: AsyncSession, data: dict) -> Contract:
    contract = Contract(**data)
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    return contract


async def update_gdrive_id(session: AsyncSession, contract_id: int, gdrive_file_id: str) -> None:
    await session.execute(
        update(Contract)
        .where(Contract.id == contract_id)
        .values(gdrive_file_id=gdrive_file_id)
    )
    await session.commit()

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State


async def advance(state: FSMContext, new_state: State) -> None:
    """Запомнить текущее состояние в истории переходов и перейти в новое."""
    current = await state.get_state()
    if current is not None:
        data = await state.get_data()
        history = data.get("_history", [])
        history.append(current)
        await state.update_data(_history=history)
    await state.set_state(new_state)

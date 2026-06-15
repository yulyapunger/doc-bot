import asyncio

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

ALBUM_WAIT_SECONDS = 1.0


async def collect_album_photos(message: Message, state: FSMContext, bot: Bot) -> list[bytes] | None:
    """Собирает фото из альбома (media group) в один список.

    Telegram присылает каждое фото альбома отдельным сообщением, и без этой
    дедупликации каждое из них запускало бы обработку заново. Для одиночного
    фото сразу возвращает список из одного элемента. Для альбома возвращает
    None для всех сообщений, кроме последнего, у которого возвращает байты
    всех фото альбома.
    """
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    data = await bot.download_file(file.file_path)
    photo_bytes = data.read()

    if not message.media_group_id:
        return [photo_bytes]

    key = message.media_group_id
    fsm_data = await state.get_data()
    albums = fsm_data.get("_albums", {})
    items = albums.get(key, []) + [photo_bytes]
    albums[key] = items
    await state.update_data(_albums=albums)

    await asyncio.sleep(ALBUM_WAIT_SECONDS)

    fsm_data = await state.get_data()
    albums = fsm_data.get("_albums", {})
    current_items = albums.get(key, [])
    if len(current_items) != len(items):
        return None

    albums.pop(key, None)
    await state.update_data(_albums=albums)
    return current_items

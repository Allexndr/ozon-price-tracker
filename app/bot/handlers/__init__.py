from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message


router = Router()
#  Это, чтобы засунуть в главный роутер другие роутеры в будущем, если нужно будет добавить
#  Что-либо по типу новых команд или инлайн кнопок
#  from .parser import router as parser_router
#  router.include_routers(parser_router)


@router.message(CommandStart())
async def start_handler(message: Message):
    # По этой команде нужно чтобы парсер начал работу
    # parser = Parser()
    # parser.start_work()
    await message.answer("Начал работу")

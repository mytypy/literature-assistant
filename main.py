import logging
import asyncio


from aiogram import Dispatcher, Bot
from aiogram.types import Message
from aiogram.filters.command import CommandStart
from chat.user import router as user_router
from api import ModelManager
from models.model import AppSettings


dp = Dispatcher()
dp.include_router(user_router)


@dp.message(CommandStart())
async def start(message: Message):
    await message.reply(
        text='''
Привет! 👋
Я — литературный бот-консультант.

Помогаю:

->    разобрать текст и идею,

->    улучшить стиль и логику,

->    подобрать образы, метафоры и ритм,

->    отредактировать рассказ, стих или эссе,

->    дать честный и понятный ответ без воды.

Присылай текст или опиши задачу — разберём по строкам, как хороший редактор, а не как школьный учебник 🙂        
'''
    )


async def main():
    app = AppSettings()
    bot = Bot(token=app.TOKEN)
    
    ModelManager()
    logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
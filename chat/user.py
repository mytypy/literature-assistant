import asyncio
import logging

from aiogram import Router, F
from aiogram.utils.chat_action import ChatActionSender
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from telegramify_markdown import markdownify
from api import Model, ModelManager


router = Router(name=__name__)


class WaitMessage(StatesGroup):
    wait = State()
    
    
def convert_markdown_to_telegram(text: str) -> str:
    try:
        return markdownify(text, max_line_length=None, normalize_whitespace=False)
    except Exception:
        return text or "На данный момент я испытываю технические трудности. Если что-то не так, то обратитесь к @mytypy"
    
    
async def set_or_wait(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await message.answer(
            text='Пожалуйста подожди, пока что я обрабатываю твой прошлый вопрос ;)'
        )
        return 'Sended'
    else:
        await state.set_state(WaitMessage.wait)
        
            
@router.message(F.text)
async def handle_message(message: Message, state: FSMContext):
    await message.answer(
        text='На данный момент, у нас небольшие технические неполадки 😔'
    )
    return
    result = await set_or_wait(message=message, state=state)

    if result == 'Sended':
        return
    
    manager = ModelManager()
    
    model: Model|False = manager.availible_model
    logging.info(model.for_use)
    
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id, interval=3, initial_sleep=1):
        if model.for_use is False:
            for _ in range(10):
                ok = await manager.next_model_or_no()
                if ok:
                    model = manager.availible_model
                    break
            else:
                await message.answer(
                    'К сожалению, на данный момент модели недоступны. Подождите 1 день.'
                )
                return
        
        async with asyncio.Semaphore(5):
            response = await model.send_message(message=message.text, user_id=message.from_user.id)
            formated = await asyncio.to_thread(convert_markdown_to_telegram, response)
            
            await state.clear()
            await message.answer(
                text=formated,
                parse_mode='MarkdownV2'
            )
    

@router.message(F.photo)
async def handle_photo(message: Message):
    await message.answer(
        text='Извини, но я пока что не научился обрабатывать фотографии. Я ещё учусь это делать :)'
    )
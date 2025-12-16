from pprint import pprint
import asyncio
import logging
import httpx
import json
import redis.asyncio as aioredis
from constants import SYSTEM_PROMPT
from models.model import AppSettings


class Memory:
    __instance = None
    MAX_MESSAGES = 30
    
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.__instance.redis = aioredis.Redis(host='redis', decode_responses=True)
        
        return cls.__instance
    
    async def save_message(self, user_id: int, role: str, message: str):
        data = {"role": role, "text": message}
        
        await self.redis.rpush(f'history:{user_id}', json.dumps(data, ensure_ascii=False))
        await self.redis.ltrim(f'history:{user_id}', -self.MAX_MESSAGES, -1)
    
    def _history(self, raw: list):
        messages = []
        
        for item in raw:
            msg = json.loads(item)
            messages.append({
                "role": msg["role"],
                "parts": [{"text": msg["text"]}]
            })
        return messages
            
    async def get_history(self, user_id):
        raw = await self.redis.lrange(f"history:{user_id}", 0, -1)
        messages = await asyncio.to_thread(self._history, raw)
        logging.info(f'{messages}')
        
        return messages
        
        
class Model:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.available_models = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite"
        ]
        self.current_model = self.available_models[0]
        self.for_use = True
        
    async def __request(self, messages: list[dict]):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.current_model}:generateContent"
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=messages
            )
            logging.info(f"STATUS: {resp.status_code}")
            
            if resp.status_code != 200:
                await self.__delete()
                return dict()
                # return await self.__request(messages=messages)

            return resp.json()
                

    
    async def __delete(self):
        logging.info(f'{self.current_model, self.available_models}')
        self.available_models.remove(self.current_model)
        
        if len(self.available_models) == 0:
            self.for_use = False
            self.available_models = None
        else:
            self.current_model = self.available_models[0]
            logging.info(self.current_model)
            
    async def _convert(self, message: str, user_id: int):
        memory = Memory()
        
        history = await memory.get_history(user_id=user_id)
        user = {
            "role": "user",
            "parts": [
                { "text": message }
            ]
            }
        history.append(user)
        
        content = {
            "systemInstruction": {
            "parts": [
                { "text": SYSTEM_PROMPT }
            ]
        },
        "contents": history,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 6000
            }
        }
        
        return content
        
    async def send_message(self, message: str, user_id: int):
        content = await self._convert(message, user_id=user_id)
        logging.info(f'Пытаемся отправить: {message}')
        response = await self.__request(messages=content)
        candidates: dict = response.get('candidates')
        
        if candidates:
            payload = candidates[0]['content']
            text = payload['parts'][0]['text']
            memory = Memory()
            await memory.save_message(user_id=user_id, role='user', message=message)
            await memory.save_message(user_id=user_id, role='model', message=text)
            
            logging.info(f'Пользователь {user_id} получил такой ответ: {text}')
            
            return text
        else:
            return 'На данный момент я испытываю технические трудности. Если что-то не так, то обратитесь к @mytypy'
    
    def __repr__(self):
        return f'<Token: {self.api_key} | Availible: {self.for_use}>'


class ModelManager:
    __instance = None
    _is_init = None

    RESTORE_DELAY = 60 * 60 * 24  # 24 часа

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        if self._is_init is None:
            settings = AppSettings()
            self.__api_keys = tuple(settings.TOKENS.split(','))

            self.classes = [Model(token) for token in self.__api_keys]
            self.timeout = {}       # key -> model
            self.restore_tasks = {} # key -> asyncio.Task
            self.availible_model = self.classes[0]

            self._is_init = True

    async def next_model_or_no(self):
        """Выдаёт следующую модель и ставит задачу вернуть текущую через сутки"""
        logging.info('Выдаём всем новый токен')
        current = self.availible_model
        logging.info(f'Убираем: {current}')
        self.classes.remove(current)

        key = current.api_key
        self.timeout[key] = current

        # Создаём фоновую задачу возврата
        self.restore_tasks[key] = asyncio.create_task(self._auto_restore_model(key))

        if not self.classes:
            logging.warning('Все токены закончились!')
            return
        
        self.availible_model = self.classes[0]
        return True

    async def _auto_restore_model(self, key: str):
        """Задача: через 24 часа вернуть модель обратно"""
        logging.info(f'Вернем {key} через 24 часа')
        await asyncio.sleep(self.RESTORE_DELAY)
        await self.return_model(key)

    async def return_model(self, key):
        """Возвращает модель вручную или после таймера"""
        if key not in self.timeout:
            return

        model = self.timeout.pop(key)
        self.classes.append(model)

        task = self.restore_tasks.pop(key, None)
        
        if task and not task.done():
            logging.info(f'Вернули {key}')
            task.cancel()
        
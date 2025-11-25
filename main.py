from pprint import pprint
import asyncio
import logging
import httpx
import json
import redis.asyncio as aioredis
from constants import SYSTEM_PROMPT


class Memory:
    __instance = None
    MAX_MESSAGES = 30
    
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.__instance.redis = aioredis.Redis(host='localhost', decode_responses=True)
        
        return cls.__instance
    
    async def save_message(self, user_id: int, role: str, message: str):
        data = {"role": role, "text": message}
        
        await self.redis.rpush(f'history:{user_id}', json.dumps(data, ensure_ascii=False))
        await self.redis.ltrim(f'history:{user_id}', -self.MAX_MESSAGES, -1)
    
    async def get_history(self, user_id):
        raw = await self.redis.lrange(f"history:{user_id}", 0, -1)

        messages = []
        for item in raw:
            msg = json.loads(item)
            messages.append({
                "role": msg["role"],
                "parts": [{"text": msg["text"]}]
            })
            
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
            try:
                resp = await client.post(
                    url,
                    headers={"x-goog-api-key": self.api_key},
                    json=messages
                )

                logging.info(f"STATUS: {resp.status_code}")

                return resp.json()
            except Exception as er:
                logging.error(repr(er))
                await self.__delete()
                return dict()

    
    async def __delete(self):
        self.available_models.remove(self.current_model)
        
        if len(self.available_models) == 0:
            self.for_use = False
        else:
            self.current_model = self.available_models[0]
    
    async def _convert(self, message: str):
        content = {
            "systemInstruction": {
            "parts": [
                { "text": SYSTEM_PROMPT }
            ]
        },
        "contents": [
            {
            "role": "user",
            "parts": [
                { "text": message}
            ]
            }
        ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 12000
            }
        }
        
        return content
        
    async def send_message(self, message: str):
        content = await self._convert(message)
        logging.info(f'Пытаемся отправить: {message}')
        response = await self.__request(messages=content)
        candidates: dict = response.get('candidates')
        
        if candidates:
            payload = candidates[0]['content']
            text = payload['parts'][0]['text']
            print(text)
        else:
            print('Ошибка')
    
    def __repr__(self):
        return f'<Token: {self.api_key} | Availible: {self.for_use}>'


class ModelManager:
    __instance = None
    _is_init = None
    
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
                    
        return cls.__instance
    
    def __init__(self):
        if self._is_init is None:
            self.__api_keys = (
            
            )
    
            self.classes = [Model(token) for token in self.__api_keys]
            self.availible_model = self.classes[0]
            
    
async def main():
    manager = ModelManager()
    memory = Memory()
    
    model = manager.availible_model
    response = await model.send_message('Как определить, что диалог звучит неестественно?')
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
    asyncio.run(main())
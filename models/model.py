from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    TOKEN: str
    TOKENS: str
    
    model_config = SettingsConfigDict(env_file='.env', env_prefix='APP_')
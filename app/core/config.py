from pydantic_settings import BaseSettings
from urllib.parse import quote_plus



class Settings(BaseSettings):
    # BD externa (solo lectura)
    db_externa_host: str
    db_externa_port: int = 3306
    db_externa_user: str
    db_externa_password: str
    db_externa_name: str

    # BD de sueldos (solo lectura)
    db_sueldos_host: str
    db_sueldos_port: int = 3306
    db_sueldos_user: str
    db_sueldos_password: str
    db_sueldos_name: str

    # BD propia
    db_propia_host: str = "localhost"
    db_propia_port: int = 3306
    db_propia_user: str
    db_propia_password: str
    db_propia_name: str

    # App
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # CORS
    frontend_url: str = "http://localhost:5173"

    # Asistente de ayuda de uso (OpenAI). Vacío = asistente deshabilitado
    # (el endpoint responde 503 en vez de romper el arranque de la app).
    openai_api_key: str = ""
    asistente_modelo: str = "gpt-4o-mini"

    @property
    def url_sueldos(self) -> str:
        password = quote_plus(self.db_sueldos_password)
        return (
        f"mysql+pymysql://{self.db_sueldos_user}:{password}"
        f"@{self.db_sueldos_host}:{self.db_sueldos_port}/{self.db_sueldos_name}"
        f"?charset=utf8mb4"
    )

    @property
    def url_externa(self) -> str:
        return (
            f"mysql+pymysql://{self.db_externa_user}:{self.db_externa_password}"
            f"@{self.db_externa_host}:{self.db_externa_port}/{self.db_externa_name}"
            f"?charset=utf8mb4"
        )

    @property
    def url_propia(self) -> str:
        return (
            f"mysql+pymysql://{self.db_propia_user}:{self.db_propia_password}"
            f"@{self.db_propia_host}:{self.db_propia_port}/{self.db_propia_name}"
            f"?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

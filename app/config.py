import os


class Settings:
    """Configuracion leida del fichero de entorno."""

    app_name: str = os.getenv("APP_NAME", "Cloud Activity 3 API")
    app_version: str = os.getenv("APP_VERSION", "0.3.0")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "postgres://cloud:cloud@db:5432/cloud")
    generate_schemas: bool = os.getenv("GENERATE_SCHEMAS", "true").lower() == "true"


settings = Settings()

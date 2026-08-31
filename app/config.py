import os


class Settings:
    """Configuracion leida del fichero de entorno."""

    app_name: str = os.getenv("APP_NAME", "Cloud Activity 4 API")
    app_version: str = os.getenv("APP_VERSION", "0.4.0")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "postgres://cloud:cloud@db:5432/cloud")
    generate_schemas: bool = os.getenv("GENERATE_SCHEMAS", "true").lower() == "true"

    # Sesiones: redis para aprovechar el TTL y compartir estado entre workers, postgres como
    # alternativa equivalente.
    session_backend: str = os.getenv("SESSION_BACKEND", "redis").lower()
    redis_url: str = os.getenv("REDIS_URL", "redis://cache:6379/0")
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

    # Almacenamiento de objetos. Con MinIO en local y con AWS en produccion solo cambia el endpoint.
    s3_bucket: str = os.getenv("S3_BUCKET", "files")
    s3_endpoint_url: str | None = os.getenv("S3_ENDPOINT_URL") or None
    s3_public_endpoint_url: str | None = os.getenv("S3_PUBLIC_ENDPOINT_URL") or None
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "minio")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "minio123")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    s3_url_expiration_seconds: int = int(os.getenv("S3_URL_EXPIRATION_SECONDS", "900"))


settings = Settings()

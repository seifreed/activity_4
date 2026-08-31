from functools import lru_cache

from app.authentication.dependency_injection.container import get_authentication_service
from app.config import settings
from app.files.domain.ports import ObjectStorage
from app.files.domain.services import FileService
from app.files.persistence.identity import AuthenticationUserResolver
from app.files.persistence.object_storage import S3ObjectStorage
from app.files.persistence.pdf import PypdfMerger
from app.files.persistence.repositories import TortoiseFileRepository


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    return S3ObjectStorage(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        public_endpoint_url=settings.s3_public_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        url_expiration_seconds=settings.s3_url_expiration_seconds,
    )


@lru_cache(maxsize=1)
def get_file_service() -> FileService:
    """Singleton que enlaza la API con el dominio de ficheros."""
    return FileService(
        files=TortoiseFileRepository(),
        storage=get_object_storage(),
        merger=PypdfMerger(),
        users=AuthenticationUserResolver(get_authentication_service()),
    )

from functools import lru_cache

from app.authentication.dependency_injection.container import get_authentication_service
from app.files.domain.services import FileService
from app.files.persistence.identity import AuthenticationUserResolver
from app.files.persistence.pdf import PypdfMerger
from app.files.persistence.repositories import TortoiseFileRepository


@lru_cache(maxsize=1)
def get_file_service() -> FileService:
    """Singleton que enlaza la API con el dominio de ficheros."""
    return FileService(
        files=TortoiseFileRepository(),
        merger=PypdfMerger(),
        users=AuthenticationUserResolver(get_authentication_service()),
    )

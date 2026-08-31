from abc import ABC, abstractmethod

from app.files.domain.entities import StoredFile


class FileRepository(ABC):
    """Puerto de salida hacia el almacen de ficheros."""

    @abstractmethod
    async def create(self, owner_id: int, name: str, description: str | None) -> int: ...

    @abstractmethod
    async def list_for_owner(self, owner_id: int) -> list[StoredFile]: ...

    @abstractmethod
    async def get_for_owner(self, file_id: int, owner_id: int) -> StoredFile | None: ...

    @abstractmethod
    async def set_content(self, file_id: int, content: bytes) -> None: ...

    @abstractmethod
    async def delete(self, file_id: int) -> bool: ...


class PdfMerger(ABC):
    """Puerto de salida hacia la herramienta que fusiona PDFs."""

    @abstractmethod
    def merge(self, documents: list[bytes]) -> bytes: ...


class UserResolver(ABC):
    """Puerto de entrada al modulo de autenticacion.

    Ficheros solo necesita saber a que usuario pertenece un token, no como se gestionan
    las sesiones, asi que depende de esta abstraccion y no del servicio de autenticacion.
    """

    @abstractmethod
    async def external_id_for(self, token: str) -> int: ...

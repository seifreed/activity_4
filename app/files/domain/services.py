from uuid import uuid4

from app.files.domain.entities import StoredFile
from app.files.domain.errors import FileNotFound, FileWithoutContent, NotEnoughFilesToMerge
from app.files.domain.ports import FileRepository, ObjectStorage, PdfMerger, UserResolver

MINIMUM_FILES_TO_MERGE = 2


class FileService:
    """Logica de gestion de ficheros.

    Coordina los metadatos y el almacenamiento de objetos: la fila y el objeto se crean y se
    borran juntos, pero cada uno vive en el sistema que mejor le va.
    """

    def __init__(
        self,
        files: FileRepository,
        storage: ObjectStorage,
        merger: PdfMerger,
        users: UserResolver,
    ):
        self._files = files
        self._storage = storage
        self._merger = merger
        self._users = users

    async def list_files(self, token: str) -> list[StoredFile]:
        owner_id = await self._users.external_id_for(token)
        return await self._files.list_for_owner(owner_id)

    async def create(self, token: str, name: str, description: str | None) -> int:
        owner_id = await self._users.external_id_for(token)
        return await self._files.create(owner_id, name, description)

    async def get(self, token: str, file_id: int) -> StoredFile:
        owner_id = await self._users.external_id_for(token)
        return await self._owned(file_id, owner_id)

    async def read_content(self, token: str, file_id: int) -> bytes | None:
        stored = await self.get(token, file_id)
        return None if not stored.has_content else await self._storage.get(stored.object_key)

    async def shareable_url(self, token: str, file_id: int) -> str | None:
        stored = await self.get(token, file_id)
        if not stored.has_content:
            return None
        return await self._storage.shareable_url(stored.object_key, stored.name)

    async def set_content(self, token: str, file_id: int, content: bytes) -> None:
        owner_id = await self._users.external_id_for(token)
        stored = await self._owned(file_id, owner_id)

        key = self._object_key(owner_id, file_id)
        await self._storage.put(key, content)
        await self._files.attach_object(file_id, key, len(content))

        # Al reemplazar el contenido, el objeto anterior se queda huerfano.
        if stored.has_content and stored.object_key != key:
            await self._storage.delete(stored.object_key)

    async def delete(self, token: str, file_id: int) -> None:
        owner_id = await self._users.external_id_for(token)
        stored = await self._owned(file_id, owner_id)

        await self._files.delete(file_id)
        if stored.has_content:
            await self._storage.delete(stored.object_key)

    async def merge(self, token: str, file_ids: list[int], name: str | None) -> int:
        if len(file_ids) < MINIMUM_FILES_TO_MERGE:
            raise NotEnoughFilesToMerge()

        owner_id = await self._users.external_id_for(token)
        sources = [await self._owned(file_id, owner_id) for file_id in file_ids]
        for source in sources:
            if not source.has_content:
                raise FileWithoutContent(source.id)

        documents = [await self._storage.get(source.object_key) for source in sources]
        merged = self._merger.merge(documents)

        merged_id = await self._files.create(
            owner_id,
            name or "-".join(source.name.removesuffix(".pdf") for source in sources) + ".pdf",
            "Fusion de los ficheros " + ", ".join(str(source.id) for source in sources),
        )
        await self.set_content(token, merged_id, merged)
        return merged_id

    async def _owned(self, file_id: int, owner_id: int) -> StoredFile:
        """Los ficheros de otros usuarios se tratan como inexistentes.

        Con un 403 se estaria confirmando que ese identificador esta ocupado.
        """
        stored = await self._files.get_for_owner(file_id, owner_id)
        if stored is None:
            raise FileNotFound(file_id)
        return stored

    def _object_key(self, owner_id: int, file_id: int) -> str:
        """Clave con el propietario delante para poder aislar por prefijo en el bucket."""
        return f"{owner_id}/{file_id}/{uuid4().hex}"

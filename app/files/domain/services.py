from app.files.domain.entities import StoredFile
from app.files.domain.errors import FileNotFound, FileWithoutContent, NotEnoughFilesToMerge
from app.files.domain.ports import FileRepository, PdfMerger, UserResolver

MINIMUM_FILES_TO_MERGE = 2


class FileService:
    """Logica de gestion de ficheros.

    Todas las operaciones parten del token: se resuelve el propietario y a partir de ahi
    ningun fichero de otro usuario es alcanzable.
    """

    def __init__(self, files: FileRepository, merger: PdfMerger, users: UserResolver):
        self._files = files
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

    async def set_content(self, token: str, file_id: int, content: bytes) -> None:
        owner_id = await self._users.external_id_for(token)
        await self._owned(file_id, owner_id)
        await self._files.set_content(file_id, content)

    async def delete(self, token: str, file_id: int) -> None:
        owner_id = await self._users.external_id_for(token)
        await self._owned(file_id, owner_id)
        await self._files.delete(file_id)

    async def merge(self, token: str, file_ids: list[int], name: str | None) -> int:
        if len(file_ids) < MINIMUM_FILES_TO_MERGE:
            raise NotEnoughFilesToMerge()

        owner_id = await self._users.external_id_for(token)
        sources = [await self._owned(file_id, owner_id) for file_id in file_ids]
        for source in sources:
            if not source.has_content:
                raise FileWithoutContent(source.id)

        merged = self._merger.merge([source.content for source in sources])
        merged_id = await self._files.create(
            owner_id,
            name or "-".join(source.name.removesuffix(".pdf") for source in sources) + ".pdf",
            "Fusion de los ficheros " + ", ".join(str(source.id) for source in sources),
        )
        await self._files.set_content(merged_id, merged)
        return merged_id

    async def _owned(self, file_id: int, owner_id: int) -> StoredFile:
        """Los ficheros de otros usuarios se tratan como inexistentes.

        Con un 403 se estaria confirmando que ese identificador esta ocupado.
        """
        stored = await self._files.get_for_owner(file_id, owner_id)
        if stored is None:
            raise FileNotFound(file_id)
        return stored

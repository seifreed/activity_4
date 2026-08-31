from pydantic import BaseModel, Field


class FileMetadataRequest(BaseModel):
    name: str = Field(description="Nombre del fichero")
    description: str | None = Field(default=None, description="Descripcion libre")


class FileSummary(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None = None
    size: int = Field(description="Tamano del contenido en bytes, 0 si aun no se ha subido")
    has_content: bool
    object_key: str | None = Field(
        default=None, description="Clave del objeto en el almacenamiento de S3"
    )


class FileDetail(FileSummary):
    content: str | None = Field(
        default=None, description="Contenido del fichero codificado en base64"
    )
    download_url: str | None = Field(
        default=None,
        description="Enlace temporal a S3 para descargar el fichero sin pasar por la API",
    )


class FileCreatedResponse(BaseModel):
    id: int


class MergeRequest(BaseModel):
    file_ids: list[int] = Field(min_length=2, description="Identificadores de los PDFs a fusionar")
    name: str | None = Field(default=None, description="Nombre del PDF resultante")


class MessageResponse(BaseModel):
    detail: str

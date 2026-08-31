from tortoise import fields
from tortoise.models import Model


class File(Model):
    """Fichero persistido.

    El propietario se guarda por su identificador externo, que es el que viaja por la API.
    """

    id = fields.IntField(pk=True)
    owner = fields.ForeignKeyField(
        "models.User",
        related_name="files",
        to_field="external_id",
        source_field="owner_external_id",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    content = fields.BinaryField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "files"

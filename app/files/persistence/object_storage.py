import asyncio
from functools import partial

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.files.domain.ports import ObjectStorage


class S3ObjectStorage(ObjectStorage):
    """Adaptador sobre S3, valido tambien para MinIO y cualquier otro servicio compatible.

    boto3 es sincrono, asi que cada llamada se lanza en el executor por defecto para no bloquear
    el bucle de eventos mientras dura la transferencia.
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        public_endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str,
        url_expiration_seconds: int,
    ):
        self._bucket = bucket
        self._url_expiration_seconds = url_expiration_seconds
        self._client = self._build_client(endpoint_url, access_key, secret_key, region)
        # Las URLs compartibles se firman contra la direccion publica, que es la que ve el
        # navegador. Dentro de la red de docker el servicio responde con otro nombre.
        self._public_client = (
            self._client
            if not public_endpoint_url or public_endpoint_url == endpoint_url
            else self._build_client(public_endpoint_url, access_key, secret_key, region)
        )

    @staticmethod
    def _build_client(endpoint_url: str | None, access_key: str, secret_key: str, region: str):
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_bucket(self) -> None:
        """Crea el bucket si no existe, para que el proyecto arranque sin preparacion manual."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    async def put(self, key: str, content: bytes) -> None:
        await self._run(
            partial(self._client.put_object, Bucket=self._bucket, Key=key, Body=content)
        )

    async def get(self, key: str) -> bytes:
        response = await self._run(partial(self._client.get_object, Bucket=self._bucket, Key=key))
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        await self._run(partial(self._client.delete_object, Bucket=self._bucket, Key=key))

    async def shareable_url(self, key: str, filename: str) -> str:
        return await self._run(
            partial(
                self._public_client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=self._url_expiration_seconds,
            )
        )

    @staticmethod
    async def _run(call):
        return await asyncio.get_running_loop().run_in_executor(None, call)

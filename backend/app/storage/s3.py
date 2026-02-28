import base64
import io
import json
from contextlib import asynccontextmanager
from typing import Any, BinaryIO, Optional

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logger import logger


def _metadata_value_to_ascii(val: Any) -> str:
    """
    Convert metadata value to ASCII-only string. S3 metadata allows only ASCII.
    Non-ASCII strings are base64-encoded (UTF-8) with 'b64:' prefix.
    """
    s = str(val) if not isinstance(val, str) else val
    if s.isascii():
        return s
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    """Ensure all metadata values are ASCII-only (required by S3)."""
    return {k: _metadata_value_to_ascii(v) for k, v in metadata.items()}


class S3Storage:
    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.public_url = settings.S3_PUBLIC_URL
        self.access_key_id = settings.S3_ACCESS_KEY_ID
        self.secret_access_key = settings.S3_SECRET_ACCESS_KEY
        self.region = settings.S3_REGION
        self.bucket_name = settings.S3_BUCKET_NAME
        self.use_ssl = settings.S3_USE_SSL

        self.session = aioboto3.Session()

    @asynccontextmanager
    async def get_client(self):
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
            use_ssl=self.use_ssl,
        ) as client:
            yield client

    async def ensure_bucket_exists(self):
        try:
            async with self.get_client() as client:
                await client.head_bucket(Bucket=self.bucket_name)
                logger.debug(f"Bucket {self.bucket_name} already exists")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                async with self.get_client() as client:
                    await client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket {self.bucket_name}")
            else:
                logger.error(f"Error checking bucket: {e}")
                raise

        if settings.S3_PUBLIC_READ:
            await self._ensure_public_read_policy()

    async def _ensure_public_read_policy(self):
        """Включает публичное чтение объектов бакета (для бессрочных ссылок)."""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket_name}/*",
                }
            ],
        }
        try:
            async with self.get_client() as client:
                await client.put_bucket_policy(
                    Bucket=self.bucket_name, Policy=json.dumps(policy)
                )
                logger.info(f"Bucket {self.bucket_name}: public read policy set")
        except ClientError as e:
            logger.warning("Could not set bucket public read policy: %s", e)

    async def upload_file(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        await self.ensure_bucket_exists()

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = _sanitize_metadata(metadata)

        async with self.get_client() as client:
            await client.upload_fileobj(
                file_obj, self.bucket_name, object_key, ExtraArgs=extra_args
            )

        logger.info(f"Uploaded file to s3://{self.bucket_name}/{object_key}")
        return f"{self.endpoint_url}/{self.bucket_name}/{object_key}"

    async def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        file_obj = io.BytesIO(data)
        return await self.upload_file(file_obj, object_key, content_type, metadata)

    async def download_file(self, object_key: str) -> bytes:
        async with self.get_client() as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=object_key)
            return await response["Body"].read()

    async def download_file_stream(self, object_key: str):
        async with self.get_client() as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=object_key)
            async for chunk in response["Body"]:
                yield chunk

    async def delete_file(self, object_key: str) -> bool:
        try:
            async with self.get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=object_key)
                logger.info(f"Deleted file s3://{self.bucket_name}/{object_key}")
                return True
        except ClientError as e:
            logger.error(f"Error deleting file: {e}")
            return False

    async def file_exists(self, object_key: str) -> bool:
        try:
            async with self.get_client() as client:
                await client.head_object(Bucket=self.bucket_name, Key=object_key)
                return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise

    async def get_file_url(self, object_key: str, expires_in: Optional[int] = None) -> str:
        if settings.S3_PUBLIC_READ:
            return f"{self.public_url.rstrip('/')}/{self.bucket_name}/{object_key}"
        # Прокси через backend: без аутентификации запрос в S3 не идёт.
        return f"/api/files/{object_key}"

    async def list_files(self, prefix: str = "") -> list[dict]:
        files = []
        async with self.get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.bucket_name, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    files.append(
                        {
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"].isoformat(),
                        }
                    )
        return files


_storage_instance: Optional[S3Storage] = None


async def get_s3_client() -> S3Storage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = S3Storage()
        await _storage_instance.ensure_bucket_exists()
    return _storage_instance

"""
MinIO Object Storage Service — stores and retrieves call audio recordings.
Uses asyncio.to_thread() to run the synchronous minio SDK without blocking the event loop.
"""
import asyncio
import logging
from io import BytesIO
from typing import Optional
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOStorageService:
    """Async-safe wrapper around the synchronous MinIO Python SDK."""

    def __init__(self):
        self._client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        # Presigned URLs are opened by the browser, not by this process, so
        # they must be signed against the host the browser can actually reach.
        # The AWS v4 signature covers the host header, so rewriting the URL
        # after signing would invalidate it - a second client is needed.
        public_endpoint = settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT
        public_secure = (
            settings.MINIO_PUBLIC_SECURE
            if settings.MINIO_PUBLIC_SECURE is not None
            else settings.MINIO_SECURE
        )
        self._public_client = (
            self._client
            if public_endpoint == settings.MINIO_ENDPOINT
            and public_secure == settings.MINIO_SECURE
            else Minio(
                endpoint=public_endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=public_secure,
                # Pinned so the SDK never makes a live region lookup against
                # the public host - that host is only reachable from the
                # browser, not from inside this container, and the lookup would
                # fail with connection refused before any URL was signed.
                region=settings.MINIO_REGION,
            )
        )
        self._bucket = settings.MINIO_BUCKET

    def _ensure_bucket_sync(self) -> None:
        """Create the bucket if it does not exist yet (synchronous)."""
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info(f"MinIO: Created bucket '{self._bucket}'")
        except S3Error as e:
            logger.error(f"MinIO: Failed to ensure bucket '{self._bucket}': {e}")
            raise

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket_sync)

    def _upload_sync(self, key: str, file_bytes: bytes, content_type: str) -> str:
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type,
        )
        return key

    async def upload_audio(
        self,
        key: str,
        file_bytes: bytes,
        content_type: str = "audio/mpeg",
    ) -> str:
        """
        Upload audio bytes to MinIO under the given key.
        Returns the stored object key (same as input key).
        Key format: {org_id}/{transcript_id}{extension}
        """
        await self.ensure_bucket()
        stored_key = await asyncio.to_thread(self._upload_sync, key, file_bytes, content_type)
        logger.info(f"MinIO: Uploaded audio '{stored_key}' ({len(file_bytes)} bytes)")
        return stored_key

    def _download_sync(self, key: str) -> bytes:
        response = None
        try:
            response = self._client.get_object(bucket_name=self._bucket, object_name=key)
            return response.read()
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    async def download_audio(self, key: str) -> bytes:
        """Fetch a stored recording. Used by the transcription worker, which
        runs in a separate process from the upload request and so only ever
        has the object key, never the original bytes."""
        data = await asyncio.to_thread(self._download_sync, key)
        logger.info(f"MinIO: Downloaded audio '{key}' ({len(data)} bytes)")
        return data

    def _presigned_url_sync(self, key: str, expiry_seconds: int) -> str:
        url = self._public_client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=key,
            expires=timedelta(seconds=expiry_seconds),
        )
        return url

    async def get_presigned_url(
        self,
        key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Generate a presigned GET URL valid for expiry_seconds (default 1 hour)."""
        url = await asyncio.to_thread(self._presigned_url_sync, key, expiry_seconds)
        logger.info(f"MinIO: Generated presigned URL for '{key}' (expires in {expiry_seconds}s)")
        return url

    def _delete_sync(self, key: str) -> None:
        self._client.remove_object(bucket_name=self._bucket, object_name=key)

    async def delete_audio(self, key: str) -> None:
        """Delete an audio file from MinIO. Silently ignores if the file doesn't exist."""
        try:
            await asyncio.to_thread(self._delete_sync, key)
            logger.info(f"MinIO: Deleted audio '{key}'")
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"MinIO: Audio '{key}' not found for deletion (already gone?)")
            else:
                logger.error(f"MinIO: Failed to delete '{key}': {e}")
                raise

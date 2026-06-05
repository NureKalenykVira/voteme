import asyncio

import cloudinary
import cloudinary.uploader

from app.core.config import settings


def init_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


async def upload_image(contents: bytes, folder: str, public_id: str) -> str:
    result = await asyncio.to_thread(
        cloudinary.uploader.upload,
        contents,
        folder=folder,
        public_id=public_id,
        resource_type="image",
        overwrite=True,
    )
    return result["secure_url"]

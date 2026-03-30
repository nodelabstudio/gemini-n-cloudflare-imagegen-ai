import os
import io

import cloudinary
import cloudinary.uploader


def configure_cloudinary():
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        raise ValueError("CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET must be set.")
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)


def upload_image(image_bytes: bytes, public_id: str) -> str:
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        public_id=public_id,
        folder="cloudfire",
        resource_type="image",
    )
    return result["secure_url"]


def delete_image(public_id: str) -> None:
    cloudinary.uploader.destroy(public_id, resource_type="image")

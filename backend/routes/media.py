"""Servicio de Cloudinary: subir y borrar archivos.

Centraliza la integracion con Cloudinary para que los routers no dependan
directamente del SDK. Las imagenes se suben como resource_type=image y los
videos como resource_type=video, en carpetas digital-signage/screen-N.
"""
import os

import cloudinary
import cloudinary.uploader

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4"}
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB

_configured = False


def configure():
    """Configura el SDK desde variables de entorno (idempotente)."""
    global _configured
    if _configured:
        return
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    _configured = True


def classify(filename: str) -> str | None:
    """Devuelve 'image', 'video' o None segun la extension del archivo."""
    ext = os.path.splitext(filename.lower())[1]
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def upload(file_bytes: bytes, filename: str, screen_id: int, media_type: str) -> dict:
    """Sube un archivo a Cloudinary y devuelve url, public_id y thumbnail.

    Lanza Exception si Cloudinary falla (el router la traduce a HTTP 502).
    """
    configure()
    folder = f"digital-signage/screen-{screen_id}"
    result = cloudinary.uploader.upload(
        file_bytes,
        resource_type=media_type,  # "image" o "video"
        folder=folder,
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    url = result["secure_url"]
    public_id = result["public_id"]

    if media_type == "video":
        # Miniatura: primer frame del video como jpg.
        thumbnail_url = cloudinary.CloudinaryImage(public_id).build_url(
            resource_type="video",
            format="jpg",
            transformation=[{"width": 320, "height": 180, "crop": "fill"}],
        )
    else:
        thumbnail_url = cloudinary.CloudinaryImage(public_id).build_url(
            transformation=[{"width": 320, "height": 180, "crop": "fill"}]
        )

    return {"url": url, "public_id": public_id, "thumbnail_url": thumbnail_url}


def delete(public_id: str, media_type: str):
    """Elimina un archivo de Cloudinary. No lanza si el archivo ya no existe."""
    configure()
    try:
        cloudinary.uploader.destroy(public_id, resource_type=media_type, invalidate=True)
    except Exception:
        # Si falla el borrado remoto igual queremos borrar de la BD; lo dejamos
        # pasar silenciosamente para no bloquear al usuario.
        pass

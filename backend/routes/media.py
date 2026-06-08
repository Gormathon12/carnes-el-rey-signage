"""Servicio de media: compresion con ffmpeg + subida a Cloudinary.

Las imagenes se suben como resource_type=image y los videos como
resource_type=video, en carpetas digital-signage/screen-N.

Los videos grandes se comprimen automaticamente con ffmpeg antes de subirlos,
para que entren en el limite del plan gratis de Cloudinary (100 MB) y para
ahorrar ancho de banda en las TVs. La calidad resultante es mas que suficiente
para carteleria en pantallas 1080p.
"""
import os
import shutil
import subprocess

import cloudinary
import cloudinary.uploader

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}

# Limite de lo que aceptamos del usuario (antes de comprimir).
MAX_FILE_BYTES = 600 * 1024 * 1024  # 600 MB
# Limite duro de Cloudinary en el plan gratis, por archivo.
CLOUDINARY_MAX_BYTES = 100 * 1024 * 1024  # 100 MB
# A partir de este tamano, comprimimos el video antes de subir.
COMPRESS_THRESHOLD_BYTES = 90 * 1024 * 1024  # 90 MB

_configured = False


def configure():
    """Configura el SDK de Cloudinary desde variables de entorno (idempotente)."""
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


def ffmpeg_available() -> bool:
    """Indica si ffmpeg esta instalado en el sistema."""
    return shutil.which("ffmpeg") is not None


def compress_video(input_path: str) -> str:
    """Comprime un video a 1080p H.264 optimizado para carteleria.

    - Reescala a un maximo de 1920px de ancho (mantiene proporcion).
    - H.264 CRF 26 (buena calidad, archivo chico).
    - Sin audio: las TVs reproducen en silencio igual.
    - +faststart para que empiece a reproducir antes (streaming web).

    Devuelve la ruta del archivo comprimido. Lanza CalledProcessError si falla.
    """
    output_path = input_path + ".min.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale='min(1920,iw)':-2",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "26",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def upload_path(file_path: str, screen_id: int, media_type: str) -> dict:
    """Sube un archivo (por ruta) a Cloudinary y devuelve url, public_id y thumb.

    Lanza Exception si Cloudinary falla (el router la traduce a HTTP 502).
    """
    configure()
    folder = f"digital-signage/screen-{screen_id}"

    if media_type == "video":
        # upload_large hace subida por chunks: mas robusto para archivos grandes.
        result = cloudinary.uploader.upload_large(
            file_path,
            resource_type="video",
            folder=folder,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            chunk_size=6 * 1024 * 1024,
        )
    else:
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="image",
            folder=folder,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )

    url = result["secure_url"]
    public_id = result["public_id"]

    if media_type == "video":
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
        # Si falla el borrado remoto igual queremos borrar de la BD.
        pass

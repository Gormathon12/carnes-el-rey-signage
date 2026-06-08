"""Endpoints de playlists e items.

Lectura (items, version) es publica para que las TV puedan consultar sin token.
Escritura (subir, editar, borrar, reordenar, renombrar) requiere admin.
"""
import os
import shutil
import tempfile

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import MediaItem, Screen
from routes import media
from routes.auth import require_admin

router = APIRouter(prefix="/playlists", tags=["playlists"])


# ---------- Schemas ----------
class ScreenSummary(BaseModel):
    id: int
    name: str
    version: str
    item_count: int


class NameUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class ItemUpdate(BaseModel):
    duration: float | None = Field(default=None, gt=0, le=3600)
    active: bool | None = None


class ReorderRequest(BaseModel):
    item_ids: list[int]


# ---------- Helpers ----------
def _get_screen_or_404(db: Session, screen_id: int) -> Screen:
    screen = db.get(Screen, screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail=f"Pantalla {screen_id} no existe")
    return screen


def _version(screen: Screen) -> str:
    return screen.updated_at.isoformat() if screen.updated_at else ""


# ---------- Endpoints publicos (TV + admin) ----------
@router.get("", response_model=list[ScreenSummary])
def list_screens(db: Session = Depends(get_db)):
    """Lista las 10 pantallas con su nombre y version (usado por el admin)."""
    screens = db.query(Screen).order_by(Screen.id).all()
    return [
        ScreenSummary(
            id=s.id,
            name=s.name,
            version=_version(s),
            item_count=len(s.items),
        )
        for s in screens
    ]


@router.get("/{screen_id}/items")
def get_items(screen_id: int, all: bool = False, db: Session = Depends(get_db)):
    """Items ordenados de una playlist.

    Por defecto solo los activos (lo que consume la TV). Con ?all=true
    devuelve tambien los desactivados (lo usa el panel admin).
    """
    screen = _get_screen_or_404(db, screen_id)
    items = sorted(screen.items, key=lambda i: i.order_index)
    if not all:
        items = [i for i in items if i.active]
    return {
        "screen_id": screen_id,
        "name": screen.name,
        "version": _version(screen),
        "items": [i.to_dict() for i in items],
    }


@router.get("/{screen_id}/version")
def get_version(screen_id: int, db: Session = Depends(get_db)):
    """Timestamp de la ultima modificacion; la TV lo compara para refrescar."""
    screen = _get_screen_or_404(db, screen_id)
    return {"screen_id": screen_id, "version": _version(screen)}


# ---------- Endpoints protegidos (admin) ----------
@router.post("/{screen_id}/items", status_code=status.HTTP_201_CREATED)
async def add_item(
    screen_id: int,
    file: UploadFile = File(...),
    duration: float = Form(default=10.0),
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Sube un archivo a la playlist.

    Para videos grandes, los comprime con ffmpeg antes de subir a Cloudinary
    (asi entran en el limite de 100 MB del plan gratis y pesan menos en las TVs).
    """
    screen = _get_screen_or_404(db, screen_id)

    media_type = media.classify(file.filename or "")
    if media_type is None:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Imagenes JPG/PNG o videos MP4.",
        )

    # Guardamos la subida en un archivo temporal en disco (no en memoria), para
    # poder manejar videos grandes sin saturar la RAM del contenedor.
    suffix = os.path.splitext(file.filename or "")[1] or ".bin"
    tmp_paths: list[str] = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            source_path = tmp.name
        tmp_paths.append(source_path)

        size = os.path.getsize(source_path)
        if size == 0:
            raise HTTPException(status_code=400, detail="El archivo esta vacio")
        if size > media.MAX_FILE_BYTES:
            mb = media.MAX_FILE_BYTES // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"El archivo supera los {mb} MB")

        upload_path = source_path

        # Comprimir videos grandes (si ffmpeg esta disponible).
        if media_type == "video" and size > media.COMPRESS_THRESHOLD_BYTES:
            if media.ffmpeg_available():
                try:
                    compressed = media.compress_video(source_path)
                    tmp_paths.append(compressed)
                    upload_path = compressed
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(
                        status_code=500,
                        detail=f"No se pudo optimizar el video: {exc}",
                    )
            elif size > media.CLOUDINARY_MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="El video es muy pesado y no se pudo optimizar. "
                    "Subi uno mas corto o de menor calidad.",
                )

        # Verificacion final contra el limite de Cloudinary.
        if os.path.getsize(upload_path) > media.CLOUDINARY_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Aun optimizado el archivo supera los 100 MB. "
                "Probá con un video mas corto.",
            )

        try:
            uploaded = media.upload_path(upload_path, screen_id, media_type)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de Cloudinary
            raise HTTPException(
                status_code=502, detail=f"Error subiendo a Cloudinary: {exc}"
            )
    finally:
        for path in tmp_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    # El nuevo item va al final.
    max_order = max((i.order_index for i in screen.items), default=-1)
    item = MediaItem(
        screen_id=screen_id,
        media_type=media_type,
        url=uploaded["url"],
        public_id=uploaded["public_id"],
        thumbnail_url=uploaded["thumbnail_url"],
        duration=duration if media_type == "image" else 0.0,
        order_index=max_order + 1,
        active=True,
    )
    db.add(item)
    screen.touch()
    db.commit()
    db.refresh(item)
    return item.to_dict()


@router.put("/{screen_id}/items/{item_id}")
def update_item(
    screen_id: int,
    item_id: int,
    body: ItemUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Edita duracion (solo imagenes) y/o estado activo de un item."""
    screen = _get_screen_or_404(db, screen_id)
    item = db.get(MediaItem, item_id)
    if item is None or item.screen_id != screen_id:
        raise HTTPException(status_code=404, detail="Item no encontrado en esta pantalla")

    if body.duration is not None and item.media_type == "image":
        item.duration = body.duration
    if body.active is not None:
        item.active = body.active

    screen.touch()
    db.commit()
    db.refresh(item)
    return item.to_dict()


@router.delete("/{screen_id}/items/{item_id}")
def delete_item(
    screen_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Borra un item de Cloudinary y de la BD."""
    screen = _get_screen_or_404(db, screen_id)
    item = db.get(MediaItem, item_id)
    if item is None or item.screen_id != screen_id:
        raise HTTPException(status_code=404, detail="Item no encontrado en esta pantalla")

    media.delete(item.public_id, item.media_type)
    db.delete(item)
    screen.touch()
    db.commit()
    return {"deleted": item_id}


@router.put("/{screen_id}/reorder")
def reorder(
    screen_id: int,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Reordena los items segun la lista de IDs recibida."""
    screen = _get_screen_or_404(db, screen_id)
    items_by_id = {i.id: i for i in screen.items}

    if set(body.item_ids) != set(items_by_id.keys()):
        raise HTTPException(
            status_code=400,
            detail="La lista de IDs no coincide con los items de la pantalla",
        )

    for index, item_id in enumerate(body.item_ids):
        items_by_id[item_id].order_index = index

    screen.touch()
    db.commit()
    return {"screen_id": screen_id, "order": body.item_ids}


@router.put("/{screen_id}/name")
def rename(
    screen_id: int,
    body: NameUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Cambia el nombre de la pantalla."""
    screen = _get_screen_or_404(db, screen_id)
    screen.name = body.name.strip()
    screen.touch()
    db.commit()
    return {"screen_id": screen_id, "name": screen.name}

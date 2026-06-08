"""Modelos de datos: Screen (pantalla/playlist) y MediaItem."""
import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base

TOTAL_SCREENS = 10
DEFAULT_IMAGE_DURATION = 10.0  # segundos


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class Screen(Base):
    """Una pantalla = una playlist. Hay 10 fijas (screen_id 1..10)."""

    __tablename__ = "screens"

    id = Column(Integer, primary_key=True)  # 1..10, asignado a mano al crear
    name = Column(String, nullable=False, default="Pantalla")
    # updated_at cambia ante cualquier modificacion de la playlist o sus items.
    # Las TV lo usan como "version" para detectar cambios via polling.
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    items = relationship(
        "MediaItem",
        back_populates="screen",
        cascade="all, delete-orphan",
        order_by="MediaItem.order_index",
    )

    def touch(self):
        """Fuerza el cambio de updated_at (las TV detectan la nueva version)."""
        self.updated_at = _now()


class MediaItem(Base):
    """Un archivo (imagen o video) dentro de una playlist."""

    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    screen_id = Column(Integer, ForeignKey("screens.id"), nullable=False, index=True)

    media_type = Column(String, nullable=False)  # "image" | "video"
    url = Column(String, nullable=False)  # URL segura de Cloudinary
    public_id = Column(String, nullable=False)  # id en Cloudinary (para borrar)
    thumbnail_url = Column(String, nullable=True)  # miniatura para el admin

    # Solo aplica a imagenes. Los videos duran lo que dura el archivo.
    duration = Column(Float, nullable=False, default=DEFAULT_IMAGE_DURATION)

    order_index = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    screen = relationship("Screen", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id,
            "screen_id": self.screen_id,
            "media_type": self.media_type,
            "url": self.url,
            "public_id": self.public_id,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "order_index": self.order_index,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

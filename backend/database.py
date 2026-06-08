"""Configuracion de la base de datos con SQLAlchemy.

Soporta SQLite (por defecto, para local) y PostgreSQL (produccion gratis con
Neon/Render). El motor se elige segun la variable de entorno DATABASE_URL.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _normalize_url(url: str) -> str:
    """Adapta la URL de Postgres al driver psycopg v3 que usamos.

    Proveedores como Neon/Render entregan 'postgres://' o 'postgresql://';
    SQLAlchemy con psycopg3 espera el prefijo 'postgresql+psycopg://'.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(
    os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'signage.db')}")
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# check_same_thread=False es necesario para SQLite con FastAPI (multiples threads).
# pool_pre_ping evita conexiones muertas cuando Neon/Render "duermen" la BD.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency de FastAPI que entrega una sesion y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

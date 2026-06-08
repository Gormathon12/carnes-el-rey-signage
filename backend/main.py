"""Punto de entrada de la app de digital signage 'Carnes el Rey'.

- Crea las tablas si no existen.
- Siembra las 10 pantallas (playlists) vacias al iniciar.
- Expone la API y sirve el frontend estatico (admin y TV).
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from database import Base, SessionLocal, engine  # noqa: E402
from models import TOTAL_SCREENS, Screen  # noqa: E402
from routes import auth, playlists  # noqa: E402

# Nombres por defecto de las pantallas (editables luego desde el admin).
DEFAULT_SCREEN_NAMES = {
    1: "Vidrieras",
    2: "Caja",
    3: "Promociones",
    4: "Mostrador",
    5: "Entrada",
    6: "Ofertas",
    7: "Parrilla",
    8: "Fiambreria",
    9: "Especiales",
    10: "Salida",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))


def seed_screens():
    """Crea las 10 pantallas si todavia no existen (idempotente)."""
    db = SessionLocal()
    try:
        for screen_id in range(1, TOTAL_SCREENS + 1):
            if db.get(Screen, screen_id) is None:
                db.add(
                    Screen(
                        id=screen_id,
                        name=DEFAULT_SCREEN_NAMES.get(screen_id, f"Pantalla {screen_id}"),
                    )
                )
        db.commit()
    finally:
        db.close()


app = FastAPI(title="Carnes el Rey - Digital Signage", version="1.0.0")

# CORS abierto: las TV acceden por IP local y por el dominio de Railway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(playlists.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_screens()


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Servir el frontend ----------
@app.get("/")
def root():
    return RedirectResponse(url="/admin")


@app.get("/admin")
def admin_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin", "index.html"))


@app.get("/tv")
def tv_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "tv", "index.html"))


# Assets estaticos (logos, etc.). Se monta al final para no tapar las rutas API.
assets_dir = os.path.join(FRONTEND_DIR, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

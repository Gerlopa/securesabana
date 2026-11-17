import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from passlib.context import CryptContext

from database import get_db, Incidente, Persona
from email_service import despachar_alerta_incidente

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Vigía Sabana Centro")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class IncidenteCreate(BaseModel):
    modalidad: str
    categoria: str
    lat: float
    lng: float
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    fecha_hora: Optional[datetime] = None


class PanicoCreate(BaseModel):
    lat: float
    lng: float
    comercio: Optional[str] = "Comercio Sabana Centro"
    descripcion: Optional[str] = "Alerta activada mediante Botón de Pánico"


class PersonaCreate(BaseModel):
    nombre: str
    email: str
    password: str
    comercio: Optional[str] = None


@app.get("/")
def servir_inicio():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="No se encontró static/index.html")
    return FileResponse(index_path)


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    total = db.query(func.count(Incidente.id)).scalar()
    return {"status": "ok", "incidentes_registrados": total}


@app.get("/api/incidentes")
def listar_incidentes(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Incidente.id,
            Incidente.modalidad,
            Incidente.categoria,
            Incidente.fecha_hora,
            Incidente.descripcion,
            Incidente.imagen_url,
            func.ST_Y(Incidente.geom).label("lat"),
            func.ST_X(Incidente.geom).label("lng"),
        )
        .order_by(Incidente.fecha_hora.desc())
        .limit(200)
        .all()
    )

    features = []
    for row in filas:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row.lng, row.lat],
                },
                "properties": {
                    "id": row.id,
                    "modalidad": row.modalidad,
                    "categoria": row.categoria,
                    "fecha_hora": row.fecha_hora.isoformat() if row.fecha_hora else None,
                    "descripcion": row.descripcion,
                    "imagen_url": row.imagen_url,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


@app.post("/api/incidentes")
def crear_incidente(datos: IncidenteCreate, db: Session = Depends(get_db)):
    fecha = datos.fecha_hora or datetime.utcnow()
    punto_wkt = f"SRID=4326;POINT({datos.lng} {datos.lat})"

    nuevo = Incidente(
        modalidad=datos.modalidad,
        categoria=datos.categoria,
        fecha_hora=fecha,
        geom=punto_wkt,
        descripcion=datos.descripcion,
        imagen_url=datos.imagen_url,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    despachar_alerta_incidente(
        {
            "categoria": datos.categoria,
            "modalidad": datos.modalidad,
            "fecha_hora": fecha.isoformat(),
            "lat": datos.lat,
            "lng": datos.lng,
            "descripcion": datos.descripcion,
        }
    )

    return {"mensaje": "Incidente registrado", "id": nuevo.id}


@app.post("/api/panico")
def activar_panico(datos: PanicoCreate, db: Session = Depends(get_db)):
    fecha = datetime.utcnow()
    punto_wkt = f"SRID=4326;POINT({datos.lng} {datos.lat})"
    desc = f"[{datos.comercio}] {datos.descripcion}"

    alerta = Incidente(
        modalidad="Botón de Pánico",
        categoria="EMERGENCIA",
        fecha_hora=fecha,
        geom=punto_wkt,
        descripcion=desc,
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)

    enviado = despachar_alerta_incidente(
        {
            "categoria": "EMERGENCIA - PÁNICO",
            "modalidad": "Botón de Pánico",
            "fecha_hora": fecha.isoformat(),
            "lat": datos.lat,
            "lng": datos.lng,
            "descripcion": desc,
        }
    )

    return {
        "mensaje": "Alerta de pánico activada",
        "id": alerta.id,
        "correo_enviado": enviado,
    }


@app.post("/api/registro")
def registrar_persona(datos: PersonaCreate, db: Session = Depends(get_db)):
    existente = db.query(Persona).filter(Persona.email == datos.email).first()
    if existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    persona = Persona(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=pwd_context.hash(datos.password),
        comercio=datos.comercio,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return {"mensaje": "Registro exitoso", "id": persona.id}

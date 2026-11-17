import csv
import hashlib
import io
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from email_service import despachar_alerta_incidente, enviar_correo_recuperacion

from config import APP_BASE_URL
from database import Incidente, Persona, Recuperacion, get_db
from email_service import despachar_alerta_incidente

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Vigía Sabana Centro")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def hashear_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        pwd_bytes = password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


class IncidenteCreate(BaseModel):
    modalidad: str
    categoria: str
    lat: float
    lng: float
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    fecha_hora: Optional[datetime] = None
    es_panico: Optional[bool] = False


class PersonaCreate(BaseModel):
    nombre: str
    email: str
    password: str
    comercio: Optional[str] = None
    recibe_alertas: Optional[bool] = True


class LoginRequest(BaseModel):
    email: str
    password: str


class RecuperacionSolicitar(BaseModel):
    email: str


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
        .order_by(Incidente.id.asc())
        .limit(500)
        .all()
    )

    resultado = []
    for row in filas:
        es_panico = (
            "pánico" in (row.modalidad or "").lower()
            or "panico" in (row.modalidad or "").lower()
        )
        resultado.append(
            {
                "id": row.id,
                "modalidad": row.modalidad,
                "categoria": row.categoria,
                "lat": float(row.lat),
                "lng": float(row.lng),
                "fecha_hora": row.fecha_hora.strftime("%Y-%m-%d %H:%M") if row.fecha_hora else "",
                "descripcion": row.descripcion or "",
                "imagen_url": row.imagen_url,
                "es_panico": es_panico,
            }
        )

    return resultado


@app.post("/api/incidentes")
def crear_incidente(datos: IncidenteCreate, db: Session = Depends(get_db)):
    fecha = datos.fecha_hora or datetime.utcnow()
    punto_wkt = f"SRID=4326;POINT({datos.lng} {datos.lat})"
    modalidad = "Alerta de Pánico" if datos.es_panico else datos.modalidad

    nuevo = Incidente(
        modalidad=modalidad,
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
            "modalidad": modalidad,
            "fecha_hora": fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "lat": datos.lat,
            "lng": datos.lng,
            "descripcion": datos.descripcion,
        }
    )

    return {"mensaje": "Incidente registrado", "id": nuevo.id}


@app.get("/api/incidentes/exportar")
def exportar_incidentes_csv(db: Session = Depends(get_db)):
    filas = (
        db.query(
            Incidente.id,
            Incidente.modalidad,
            Incidente.categoria,
            Incidente.fecha_hora,
            Incidente.descripcion,
            func.ST_Y(Incidente.geom).label("lat"),
            func.ST_X(Incidente.geom).label("lng"),
        )
        .order_by(Incidente.id.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Modalidad", "Categoria", "Latitud", "Longitud", "Fecha_Hora", "Descripcion"])

    for row in filas:
        writer.writerow([
            row.id,
            row.modalidad,
            row.categoria,
            row.lat,
            row.lng,
            row.fecha_hora.isoformat() if row.fecha_hora else "",
            row.descripcion or "",
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidentes_sabana_centro.csv"},
    )


@app.post("/api/personas")
def registrar_persona(datos: PersonaCreate, db: Session = Depends(get_db)):
    try:
        correo_limpio = datos.email.strip().lower()
        existente = db.query(Persona).filter(Persona.email == correo_limpio).first()
        if existente:
            raise HTTPException(status_code=400, detail="El correo ya está registrado en la tabla personas.")

        persona = Persona(
            nombre=datos.nombre.strip(),
            email=correo_limpio,
            password_hash=hashear_password(datos.password),
            rol="comerciante",
            comercio=(datos.comercio or "").strip() or "Comercio registrado",
            recibe_alertas=datos.recibe_alertas if datos.recibe_alertas is not None else True,
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)
        return {"mensaje": "Comercio suscrito correctamente a alertas.", "id": persona.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error registrando persona: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno al guardar: {str(e)}")


@app.post("/api/login")
def iniciar_sesion(datos: LoginRequest, db: Session = Depends(get_db)):
    correo_limpio = datos.email.strip().lower()
    persona = db.query(Persona).filter(Persona.email == correo_limpio).first()
    if not persona or not verificar_password(datos.password, persona.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")

    return {
        "mensaje": f"Bienvenido, {persona.nombre}",
        "usuario": {
            "id": persona.id,
            "nombre": persona.nombre,
            "email": persona.email,
            "comercio": persona.comercio or "Comercio registrado",
            "rol": persona.rol,
        },
    }


@app.post("/api/recuperar/solicitar")
def solicitar_recuperacion(datos: RecuperacionSolicitar, db: Session = Depends(get_db)):
    correo_limpio = datos.email.strip().lower()
    persona = db.query(Persona).filter(Persona.email == correo_limpio).first()
    if not persona:
        raise HTTPException(status_code=404, detail="No existe ningún usuario registrado con ese correo.")

    token_plano = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()

    rec = Recuperacion(
        persona_id=persona.id,
        token_hash=token_hash,
        expira=datetime.utcnow() + timedelta(hours=1),
        usado=False,
    )
    db.add(rec)
    db.commit()

    enlace = f"{APP_BASE_URL}/?token={token_plano}"
    enviado, detalle = enviar_correo_recuperacion(
        nombre=persona.nombre,
        email_usuario=persona.email,
        enlace=enlace,
        token=token_plano,
    )

    if not enviado:
        raise HTTPException(
            status_code=500,
            detail=f"Token guardado en Neon, pero falló el envío SMTP: {detalle}",
        )

    return {"mensaje": f"Correo de recuperación enviado a {persona.email} (con copia de respaldo)."}

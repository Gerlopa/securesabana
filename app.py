from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets
import io
import csv

from database import get_db, IncidenteDB, PersonaDB, RecuperacionDB, LimiteSolicitudDB
from email_service import despachar_alerta_incidente, enviar_correo_recuperacion

app = FastAPI(title="Vigía Sabana Centro - PostGIS API")

class IncidenteCreate(BaseModel):
    modalidad: str
    categoria: str
    lat: float
    lng: float
    descripcion: Optional[str] = "Sin detalles adicionales"
    imagen_url: Optional[str] = None
    es_panico: bool = False

class PersonaCreate(BaseModel):
    nombre: str
    email: str
    password: str
    comercio: Optional[str] = None
    recibe_alertas: bool = True

class SolicitudRecuperacion(BaseModel):
    email: str

class ConfirmarRecuperacion(BaseModel):
    token: str
    nueva_password: str

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def leer_index():
    return FileResponse("static/index.html")

# 1. CONSULTAR INCIDENTES DESDE POSTGIS (Extrayendo lat/lng de geom)
@app.get("/api/incidentes")
async def obtener_incidentes(db: Session = Depends(get_db)):
    resultados = (
        db.query(
            IncidenteDB.id,
            IncidenteDB.modalidad,
            IncidenteDB.categoria,
            IncidenteDB.fecha_hora,
            IncidenteDB.descripcion,
            IncidenteDB.imagen_url,
            func.ST_Y(IncidenteDB.geom).label("lat"),
            func.ST_X(IncidenteDB.geom).label("lng"),
        )
        .order_by(IncidenteDB.id.asc())
        .all()
    )

    return [
        {
            "id": r.id,
            "modalidad": r.modalidad,
            "categoria": r.categoria,
            "fecha_hora": r.fecha_hora.strftime("%Y-%m-%d %H:%M"),
            "descripcion": r.descripcion or "",
            "imagen_url": r.imagen_url,
            "lat": float(r.lat),
            "lng": float(r.lng),
            "es_panico": "pánico" in r.modalidad.lower() or "panico" in r.modalidad.lower()
        }
        for r in resultados
    ]

# 2. GUARDAR INCIDENTE O BOTÓN DE PÁNICO EN POSTGIS + ENVIAR/REENVIAR CORREOS
@app.post("/api/incidentes")
async def crear_incidente(
    data: IncidenteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    ahora = datetime.now()
    modalidad_final = "Alerta de Pánico" if data.es_panico else data.modalidad

    # Construir geometría PostGIS POINT(lng lat) con SRID 4326
    punto_wkt = f"SRID=4326;POINT({data.lng} {data.lat})"

    nuevo = IncidenteDB(
        modalidad=modalidad_final,
        categoria=data.categoria,
        fecha_hora=ahora,
        geom=punto_wkt,
        descripcion=data.descripcion,
        imagen_url=data.imagen_url
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    payload_correo = {
        "id": nuevo.id,
        "modalidad": nuevo.modalidad,
        "categoria": nuevo.categoria,
        "fecha_hora": ahora.strftime("%Y-%m-%d %H:%M"),
        "descripcion": nuevo.descripcion,
        "lat": data.lat,
        "lng": data.lng,
        "es_panico": data.es_panico
    }

    background_tasks.add_task(despachar_alerta_incidente, payload_correo)

    return {"mensaje": "Incidente guardado en PostGIS y alertas enviadas", "data": payload_correo}

# 3. REGISTRAR COMERCIANTE EN TABLA 'personas' PARA RECIBIR ALERTAS
@app.post("/api/personas")
async def registrar_persona(persona: PersonaCreate, db: Session = Depends(get_db)):
    existe = db.query(PersonaDB).filter(PersonaDB.email == persona.email).first()
    if existe:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado.")

    pwd_hash = hashlib.sha256(persona.password.encode()).hexdigest()
    nueva_persona = PersonaDB(
        nombre=persona.nombre,
        email=persona.email,
        password_hash=pwd_hash,
        rol="comerciante",
        comercio=persona.comercio,
        recibe_alertas=persona.recibe_alertas
    )
    db.add(nueva_persona)
    db.commit()
    return {"mensaje": "Comerciante registrado para recibir alertas por correo."}

# 4. SOLICITAR RECUPERACIÓN DE CONTRASEÑA (Usa 'recuperaciones' y 'limites_solicitudes')
@app.post("/api/recuperar/solicitar")
async def solicitar_recuperacion(
    req: SolicitudRecuperacion,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    identity_hash = hashlib.sha256(req.email.lower().encode()).hexdigest()
    ahora_utc = datetime.now(timezone.utc)

    # Verificar límite de solicitudes (1 intento cada 60 segundos)
    limite = db.query(LimiteSolicitudDB).filter(
        LimiteSolicitudDB.scope == "recuperacion_password",
        LimiteSolicitudDB.identity_hash == identity_hash
    ).first()

    if limite and (ahora_utc - limite.ultimo_intento).total_seconds() < 60:
        raise HTTPException(status_code=429, detail="Espera 1 minuto antes de solicitar otro correo.")

    if limite:
        limite.ultimo_intento = ahora_utc
    else:
        db.add(LimiteSolicitudDB(
            scope="recuperacion_password",
            identity_hash=identity_hash,
            ultimo_intento=ahora_utc
        ))
    db.commit()

    persona = db.query(PersonaDB).filter(PersonaDB.email == req.email).first()
    if not persona:
        return {"mensaje": "Si el correo existe, se envió un enlace de recuperación."}

    token_plano = secrets.token_urlsafe(16)
    token_hash = hashlib.sha256(token_plano.encode()).hexdigest()

    rec = RecuperacionDB(
        persona_id=persona.id,
        token_hash=token_hash,
        expira=datetime.now() + timedelta(minutes=30),
        usado=False
    )
    db.add(rec)
    db.commit()

    background_tasks.add_task(enviar_correo_recuperacion, persona.email, persona.nombre, token_plano)
    return {"mensaje": "Correo de recuperación enviado y reenviado a respaldo."}

# 5. EXPORTAR REPORTES DESDE POSTGIS A CSV
@app.get("/api/incidentes/exportar")
async def exportar_csv(db: Session = Depends(get_db)):
    resultados = db.query(
        IncidenteDB.id,
        IncidenteDB.modalidad,
        IncidenteDB.categoria,
        IncidenteDB.fecha_hora,
        IncidenteDB.descripcion,
        func.ST_Y(IncidenteDB.geom).label("lat"),
        func.ST_X(IncidenteDB.geom).label("lng"),
    ).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["ID", "Modalidad", "Categoria", "Fecha_Hora", "Latitud", "Longitud", "Descripcion"])
    for r in resultados:
        writer.writerow([r.id, r.modalidad, r.categoria, r.fecha_hora, r.lat, r.lng, r.descripcion])
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidentes_postgis.csv"}
    )
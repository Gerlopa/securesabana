from sqlalchemy import create_engine, Column, Integer, Text, Boolean, DateTime, ForeignKey, CHAR
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class IncidenteDB(Base):
    __tablename__ = "incidentes"

    id = Column(Integer, primary_key=True, index=True)
    modalidad = Column(Text, nullable=False)
    categoria = Column(Text, nullable=False)
    fecha_hora = Column(DateTime, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    descripcion = Column(Text, nullable=True)
    imagen_url = Column(Text, nullable=True)
    creado = Column(DateTime, server_default=func.now())

class PersonaDB(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    rol = Column(Text, nullable=False, default="comerciante")
    comercio = Column(Text, nullable=True)
    recibe_alertas = Column(Boolean, nullable=False, default=True)
    creado = Column(DateTime, server_default=func.now())

class RecuperacionDB(Base):
    __tablename__ = "recuperaciones"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    token_hash = Column(Text, nullable=False)
    expira = Column(DateTime, nullable=False)
    usado = Column(Boolean, nullable=False, default=False)
    creado = Column(DateTime, server_default=func.now())

class LimiteSolicitudDB(Base):
    __tablename__ = "limites_solicitudes"

    scope = Column(Text, primary_key=True, nullable=False)
    identity_hash = Column(CHAR(64), primary_key=True, nullable=False)
    ultimo_intento = Column(DateTime(timezone=True), nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
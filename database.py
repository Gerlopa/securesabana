from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    CHAR,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geometry
from config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("Falta configurar la variable de entorno DATABASE_URL en Vercel.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Incidente(Base):
    __tablename__ = "incidentes"

    id = Column(Integer, primary_key=True, index=True)
    modalidad = Column(Text, nullable=False)
    categoria = Column(Text, nullable=False)
    fecha_hora = Column(DateTime, nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    descripcion = Column(Text, nullable=True)
    imagen_url = Column(Text, nullable=True)
    creado = Column(DateTime, default=datetime.utcnow)


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    rol = Column(Text, nullable=False, default="comerciante")
    comercio = Column(Text, nullable=True)
    recibe_alertas = Column(Boolean, nullable=False, default=True)
    creado = Column(DateTime, default=datetime.utcnow)


class Recuperacion(Base):
    __tablename__ = "recuperaciones"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, nullable=False)
    expira = Column(DateTime, nullable=False)
    usado = Column(Boolean, nullable=False, default=False)
    creado = Column(DateTime, default=datetime.utcnow)


class LimiteSolicitud(Base):
    __tablename__ = "limites_solicitudes"

    scope = Column(Text, primary_key=True)
    identity_hash = Column(CHAR(64), primary_key=True)
    ultimo_intento = Column(DateTime(timezone=True), nullable=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# File: database/models.py

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, func
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import settings

DATABASE_URL = settings.DATABASE_URL
engine_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=engine_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'
    job_id = Column(String, primary_key=True, index=True)
    status = Column(String, default="in_queue")
    progress = Column(Integer, default=0)
    queue_position = Column(Integer, default=0)
    request_data = Column(Text)
    output_filename = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    start_time = Column(DateTime, nullable=True)

class ApiKey(Base):
    __tablename__ = 'api_keys'
    key = Column(String, primary_key=True, index=True)
    daily_limit = Column(Integer, default=1000)
    minute_limit = Column(Integer, default=10)

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
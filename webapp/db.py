# database connection and sessions

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# dependency: one database session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# create the tables, safe to run on every startup
def init_db():
    from webapp import models

    Base.metadata.create_all(bind=engine)

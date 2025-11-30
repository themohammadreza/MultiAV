from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine

SQLALCHEMY_DATABASE_URL = "postgresql://multiav_user:mohammad@localhost:5432/multiav_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


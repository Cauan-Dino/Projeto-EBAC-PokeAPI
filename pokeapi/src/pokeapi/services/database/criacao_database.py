from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base  
import os

URL_DB = os.getenv('URL_DB')

engine = create_engine(URL_DB,connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
Base = declarative_base()

def sessao_db():
    with SessionLocal() as db:
        yield db
        
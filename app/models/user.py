from sqlalchemy import Column, Integer, String, Date
from app.database.postgres import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role =  Column(String, nullable=False, default = "Paziente")

    via = Column(String, nullable=False)
    numero_civico = Column(String, nullable=False)
    citta = Column(String, nullable=False)
    cap = Column(String, nullable=False)
    data_nascita = Column(Date, nullable=False)
    sesso = Column(String, nullable=False)
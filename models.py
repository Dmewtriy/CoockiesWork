from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    phone_number = Column(String, unique=True, nullable=False, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    telegram_id = Column(Integer, unique=True, nullable=False)
    
    domofons = relationship("Domofon", back_populates="user")

class Domofon(Base):
    __tablename__ = 'domofons'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.tenant_id'), nullable=False)
    domofon_id = Column(Integer, nullable=False)
    domofon_name = Column(String, nullable=False)

    user = relationship("User", back_populates="domofons")
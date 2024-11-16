from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, nullable=False)
    tenant_id = Column(Integer, nullable=False)
    telegram_id = Column(Integer, unique=True, nullable=False)
    apartments = relationship("Apartment", back_populates="user")
    domofons = relationship("Domofon", back_populates="user")

class Apartment(Base):
    __tablename__ = 'apartments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    apartment_number = Column(String)

    user = relationship("User", back_populates="apartments")

class Domofon(Base):
    __tablename__ = 'domofons'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    domofon_name = Column(String)

    user = relationship("User", back_populates="domofons")
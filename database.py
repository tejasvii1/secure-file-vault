import os
from sqlmodel import SQLModel, create_engine, Session

from models import User, File, AuditLog


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///vault.db") # defaults to a SQLite database stored in a file called vault.db;
# setting the DATABASE_URL environment variable points the app at a different database (e.g. inside Docker or on AWS)

engine = create_engine(DATABASE_URL, echo=True) # engine is the connection manager to the database 

# echo = True prints the actual SQL commands to your terminal so you cant see whats happnening under the hood 

def create_db_and_tables(): # function we'll call once on startup to actually create database and files 
    SQLModel.metadata.create_all(engine)

def get_session(): # reusable way to get a database sesion whenever a route needs to read/write data 
    with Session(engine) as session:
        yield session # akes this a generator that FastAPi uses to clean up the session automatically after each request 
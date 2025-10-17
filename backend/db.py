from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/db_6g')
engine = create_engine(DATABASE_URL)
session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()  # Use Base for models

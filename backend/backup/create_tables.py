import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Add root to path

from models import Base  # Now imports from root
from backend.db import engine  # Assuming db.py defines engine

Base.metadata.create_all(engine)
print("Tables created successfully")

from sqlalchemy.ext.declarative import declarative_base
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

Base = declarative_base()

class User(SQLAlchemyBaseUserTableUUID, Base):
    pass

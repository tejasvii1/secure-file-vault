from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

#Optioanl[int] = Field(default = None, primary_key=True) -- unique ID for each row; Optional.default=None because database assigns this automatically when a row is created 
#Field(unqiue=True, index=True) -- no two users can share username/email, and its indexed for fast looups 
#Field(foreign_key="user_id") -- links File or AuditLog row to the User who owns it; how the database enforces this file belongs to this specific user 
#Field(default_factory=datetime.utcnow) -- automatically stamps the current time when a row is created, so you dont have to set it manually


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id")
    filename: str
    stored_path: str
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    size: int
    virustotal_result: Optional[str] = None


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    action: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: str
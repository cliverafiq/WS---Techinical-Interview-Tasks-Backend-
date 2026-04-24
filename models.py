from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from enum import Enum

class Occupation(str, Enum):
    doctor = "Doctor"
    scientist = "Scientist"
    unknown = "Unknown"

class Status(str, Enum):
    processed = "processed"
    dead_letter = "dead_letter"
    pending_review = "pending_review"

class InputRecord(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None

class OutputRecord(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    occupation: Optional[Occupation] = None
    specialty_code: Optional[int] = None
    uuid: Optional[str] = None
    status: Status

class TokenRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# LangGraph state
class GraphState(BaseModel):
    records: list[dict]
    processed: list[dict] = []
    failed: list[dict] = []
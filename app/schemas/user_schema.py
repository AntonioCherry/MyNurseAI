from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str  # "doctor" o "patient"

class UserRead(BaseModel):
    id: int
    username: str
    email: str
    role: str

    class Config:
        orm_mode = True

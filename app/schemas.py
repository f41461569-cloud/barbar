from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BookingCreate(BaseModel):
    time_slot_id: int
    driver_id: int
    cargo_id: Optional[int] = None

class BookingResponse(BaseModel):
    id: int
    time_slot_id: int
    driver_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from datetime import datetime


class BookingCreate(BaseModel):
    time_slot_id: int
    driver_id: int
    cargo_id: Optional[int] = None


class BookingResponse(BaseModel):
    id: int
    time_slot_id: Optional[int] = None
    driver_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverDocumentResponse(BaseModel):
    id: int
    driver_id: int
    doc_type: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    rejection_reason: Optional[str] = None
    version: int
    uploaded_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DriverDocumentsResponse(BaseModel):
    verification_status: str
    documents: list[DriverDocumentResponse]


class AdminDocumentResponse(DriverDocumentResponse):
    driver_name: str


class AdminDocumentListResponse(BaseModel):
    items: list[AdminDocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: Optional[str] = None
    version: Optional[int] = None


CargoTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)
]
CargoPlace = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
]


class CargoCreate(BaseModel):
    title: CargoTitle
    origin: CargoPlace
    destination: CargoPlace
    weight_kg: float = Field(ge=1, le=40_000, allow_inf_nan=False)
    price: float = Field(ge=1, le=1_000_000_000_000, allow_inf_nan=False)

    # `shipper_id` and `status` are server-controlled; anything extra is ignored.
    model_config = ConfigDict(extra="ignore")


class CargoResponse(BaseModel):
    id: int
    shipper_id: int
    title: str
    origin: str
    destination: str
    weight_kg: float
    price: float
    status: str

    model_config = ConfigDict(from_attributes=True)


class CargoListResponse(BaseModel):
    items: list[CargoResponse]
    total: int
    limit: int
    offset: int


class CargoBookingResponse(BaseModel):
    id: int
    cargo_id: int
    driver_id: int
    time_slot_id: Optional[int] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

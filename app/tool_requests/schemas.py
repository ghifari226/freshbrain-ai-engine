from datetime import datetime

from pydantic import BaseModel


class ToolRequestCreate(BaseModel):
    title: str
    description: str
    domain: str


class ToolRequestUpdate(BaseModel):
    title: str
    description: str
    domain: str


class ToolRequestStatusUpdate(BaseModel):
    status: str


class ToolRequestOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    domain: str
    status: str
    created_at: datetime
    updated_at: datetime


class ToolRequestListResponse(BaseModel):
    requests: list[ToolRequestOut]

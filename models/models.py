import uuid
from enum import IntEnum
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class AppointmentStatus(IntEnum):
    active = 1
    reserved = 2
    error = 99

class AppointmentQuery(BaseModel):
    city_id: int
    service_id: int
    facilities_ids: List[int] = []
    doctor_ids: List[int] = []
    doctor_blacklist_ids: List[int] = []
    start_date: Optional[str] = None
    after_hour: Optional[str] = None
    before_hour: Optional[str] = None
    lookup_time_days: Optional[int] = 14

class Appointment(BaseModel):
    id: str = None
    status: AppointmentStatus
    account_email: str
    query: AppointmentQuery
    comment: Optional[str] = None
    next_check: int = 0
    check_frequency: int
    allow_rescheduling: bool = False
    term: Optional[Dict] = None

class LuxmedCredentials(BaseModel):
    email: str
    password: str
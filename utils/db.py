from tinydb import TinyDB, Query
from typing import List, Optional
from models import Appointment, AppointmentStatus, LuxmedCredentials
from datetime import datetime
from uuid import uuid4

# Initialize TinyDB database connection
db = None
appointments_table = None
luxmed_credentials_table = None

# Initialize TinyDB database connection
def init_database(database_path):
    global db, appointments_table, luxmed_credentials_table
    db = TinyDB(database_path)
    appointments_table = db.table('appointments')
    luxmed_credentials_table = db.table('luxmed_credentials')

def list_appointments() -> List[Appointment]:
    return [Appointment(**row) for row in appointments_table.all()]

def get_appointments_to_check() -> List[Appointment]:
    AppointmentQuery = Query()
    results = appointments_table.search((AppointmentQuery.status != AppointmentStatus.reserved) \
                                        & (AppointmentQuery.next_check < datetime.now().timestamp()))
    return [Appointment(**row) for row in results]

def create_appointment(appointment: Appointment) -> Appointment:
    appointment.id = str(uuid4())
    result = appointments_table.insert(appointment.model_dump())
    return get_appointment(appointment.id) if result else None

def get_appointment(appointment_id: str) -> Optional[Appointment]:
    AppointmentQuery = Query()
    result = appointments_table.get(AppointmentQuery.id == appointment_id)
    return Appointment(**result) if result else None

def update_appointment(appointment_id: str, appointment: Appointment) -> Optional[Appointment]:
    AppointmentQuery = Query()
    result = appointments_table.update(appointment.model_dump(), AppointmentQuery.id == appointment_id)
    return get_appointment(appointment_id) if result else None

def delete_appointment(appointment_id: str) -> bool:
    result = appointments_table.remove(id=[appointment_id])
    return bool(result)

def get_luxmed_credentials(email: str) -> Optional[LuxmedCredentials]:
    Credentails = Query()
    result = luxmed_credentials_table.get(Credentails.email == email)
    if not result:
        raise ValueError(f"No credentials found for email: {email}")
    return LuxmedCredentials(**result) if result else None

def create_luxmed_credentials(email: str, password: str) -> LuxmedCredentials:
    credentials = { "email": email, "password": password }
    luxmed_credentials_table.insert(credentials)
    return LuxmedCredentials(**credentials)
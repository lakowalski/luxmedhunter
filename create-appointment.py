from utils.db import * 
from models import *

init_database('database.json')

appointment = Appointment(**{
    "comment": "internistapoz-20250105",
    "status": AppointmentStatus.active,
    "account_email": "user@gmail.com",
    "check_frequency": 300,
    # You can get those ids by reading form data sent to https://portalpacjenta.luxmed.pl/PatientPortal/Reservations/Reservation/PartialSearch
    # on https://portalpacjenta.luxmed.pl/PatientPortal/Reservations/Reservation/Search by dev tools
    "query": {          
        "city_id": 8,             
        "service_id": 9242,
        "facilities_ids": [],
        "doctor_ids": [],
        "doctor_blacklist_ids": [],
        # start_date: "2025-01-20"
        # after_hour: "10:00"
        # before_hour: "12:00"
        "lookup_time_days": 14 # from start date 
    }
})

create_appointment(appointment)
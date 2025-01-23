from datetime import datetime, timedelta
import time
import traceback
from typing import Any, Dict, List
from loguru import logger
import schedule
import json
from .config import load_configuration
from .luxmedapi import LuxmedApi
from .mail import MailHandler
from .db import *

class LuxmedAppointmentHunterError(Exception):
    """Custom Exception for LuxMedAppointmentHunter errors."""
    pass

class LuxmedAppointmentHunter:
    def __init__(self, config_file: str):
        logger.info("Initializing LuxMedAppointmentHunter.")
        self.config = load_configuration(config_file)
        self.sessions = {}

        # init database
        init_database(self.config['database_file'])
        logger.info("Database initiated.")

        # init mail handler
        if self.config['notifications']['mail']['enable']:
            self.mail = MailHandler(self.config['notifications']['mail'])

    def _get_appointments_terms(self, session, params) -> List[Dict]:
        """Fetch and filter appointments based on configuration."""

        date_from = datetime.strptime(params.start_date, "%Y-%m-%d") if params.start_date else datetime.today()
        before_hour = datetime.strptime(params.before_hour, "%H:%M").time() if params.before_hour else None
        after_hour = datetime.strptime(params.after_hour, "%H:%M").time() if params.after_hour else None

        params = {
            "city_id": params.city_id,
            "service_id": params.service_id,
            "facilities_ids": params.facilities_ids if params.facilities_ids else [],
            "doctor_ids": params.doctor_ids if params.doctor_ids else [],
            "doctor_blacklist_ids": params.doctor_blacklist_ids if params.doctor_blacklist_ids else [],
            "language_id": 10,
            "start_date": date_from,
            "lookup_days": params.lookup_time_days,
            "before_hour": before_hour,
            "after_hour": after_hour
        }

        return session.get_appointments_terms(**params)
    
    def _send_notification(self, subject: str, message: str):
        if self.config['notifications']['mail']['enable']:
            self.mail.send_mail(subject, message)

    def _get_session(self, account_email: str):
        if account_email not in self.sessions:
            credentials = get_luxmed_credentials(email = account_email)
            if not credentials:
                raise Exception("Luxmed account not found in the database")
            session = LuxmedApi(email=credentials.email, password=credentials.password)
            self.sessions[account_email] = session

        return self.sessions[account_email]

    def hunt_appointments(self):
        """Hunt for appointments and attempt to reserve them."""
        try:
            appointments = get_appointments_to_check()
            logger.info(f"Found {len(appointments)} appointments to check")

            for appointment in appointments:
                try:
                    logger.info(f"Checking {appointment.id} ({appointment.account_email}, {appointment.comment})...")
                    session = self._get_session(appointment.account_email)
                    terms = self._get_appointments_terms(session, appointment.query)

                    if terms:
                        # Attempt to reserve the first available appointment
                        term = terms[0]
                        lock = session.create_reservation_lock_term(term)

                        # Check related visits
                        related_visits = lock.get('relatedVisits', [])

                        if len(related_visits):
                            # Check is allowing rescheduling
                            if not appointment.allow_rescheduling:
                                logger.error(f"Appointment {appointment.id} ({appointment.comment}) have already scheduled visit and is not allowed to rescheduled. Changing appointment status to ERROR.")
                                appointment.status = AppointmentStatus.error
                                appointment.next_check = 0
                                update_appointment(appointment.id, appointment)
                                continue
                            # Reschedule reservation term
                            reservation = session.change_reservation(term, lock)
                        else: # Create reservation
                            reservation = session.create_reservation(term, lock)

                        appointment.status = AppointmentStatus.reserved
                        appointment.next_check = 0
                        appointment.term = json.loads(json.dumps(term, default=str))
                        update_appointment(appointment.id, appointment)

                        self._send_notification(
                            subject="Appointment Reserved",
                            message=f"Reserved appointment:\n{json.dumps(term, default=str, indent=2)}"
                        )
                        logger.info(
                            "Reserved appointment term: {dateTimeFrom} at {clinic} - {doctorName}", 
                            **term
                        )
                    else:
                        next_check = datetime.now() + timedelta(seconds=appointment.check_frequency)
                        appointment.next_check = int(next_check.timestamp())
                        update_appointment(appointment.id, appointment)
                        logger.info(f"No terms found for appointment {appointment.id} ({appointment.comment}). Next check at {next_check}... ")
                except Exception as e:
                    logger.error("Error reserving appointment: {}", e, exc_info=True)
                    logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error("Error hunting appointments: {}", e, exc_info=True)
            logger.debug(traceback.format_exc())

    def run_scheduler(self, interval: int):
        """Run the appointment hunter on a schedule."""
        self.hunt_appointments()
        schedule.every(interval).seconds.do(self.hunt_appointments)
        while True:
            schedule.run_pending()
            time.sleep(1)
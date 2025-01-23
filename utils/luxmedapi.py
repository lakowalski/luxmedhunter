import datetime
import json
import requests
import jwt
from typing import Any, Dict, List
from loguru import logger

class LuxmedApiError(Exception):
    """Custom Exception for LuxMedApi errors."""
    pass

def decode_jwt_expiration(token: str) -> datetime.datetime:
    try:
        # Decode the JWT without verification (use with trusted tokens only)
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded_token.get("exp")
        if not exp_timestamp:
            raise LuxmedApiError("Token does not contain an expiration date.")
        
        # Convert the expiration timestamp to a datetime object
        return datetime.datetime.fromtimestamp(exp_timestamp, tz=datetime.timezone.utc)
    except jwt.PyJWTError as e:
        raise LuxmedApiError(f"Failed to decode JWT token: {e}")

class LuxmedApi:
    LUXMED_LOGIN_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/Account/LogIn'
    GET_USER_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/UserProfile/GetUser'
    RESERVATION_SEARCH_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/terms/index'
    GET_FORGERY_TOKEN_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/security/getforgerytoken'
    RESERVATION_LOCK_TERM_URL = "https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/reservation/lockterm"
    RESERVATION_CONFIRM_URL = "https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/reservation/confirm"
    RESERVATION_CHANGE_TERM_URL = "https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/reservation/changeterm"

    def __init__(self, email, password):
        logger.info("Initializing LuxMedApi.")
        self.email = email
        self.password = password
        self.token_expiration = None

        self.session = self._create_session()
        self._authenticate()
        
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        return session

    def _authenticate(self):
        """Perform login and store authorization token."""
        payload = {
            "login": self.email,
            "password": self.password,
        }

        response = self.session.post(self.LUXMED_LOGIN_URL, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()

        token = response.json().get("token")
        if not token:
            raise LuxmedApiError("Login failed: Token not received.")
        
        self.session.headers["Authorization-Token"] = f"Bearer {token}"
        self._get_xsrf_token()
        logger.info("Login successful.")

        # Decode JWT token and extract expiration date
        self.token_expiration = decode_jwt_expiration(token)
        logger.info(f"Token expiration date: {self.token_expiration}")

    def _get_xsrf_token(self):
        """Retrieve XSRF token and update session headers."""
        response = self.session.get(self.GET_FORGERY_TOKEN_URL)
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise LuxmedApiError("Failed to retrieve XSRF token.")
        
        self.session.headers["XSRF-TOKEN"] = token
        logger.info("XSRF token retrieved successfully.")
    
    def _ensure_authenticated(self):
        """Check if the token is expired and reauthenticate if necessary."""
        if not self.token_expiration or datetime.datetime.now(datetime.timezone.utc) >= self.token_expiration:
            logger.info("Token expired or not available. Reauthenticating...")
            self._authenticate()

    def _get(self, url: str, **kwargs) -> dict:
        """Make a GET request, ensuring the token is valid."""
        self._ensure_authenticated()
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _post(self, url: str, **kwargs) -> dict:
        """Make a POST request, ensuring the token is valid."""
        self._ensure_authenticated()
        response = self.session.post(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _parse_visits(
            self, data: dict, clinic_ids: List[int], doctor_ids: List[int], 
            doctor_blacklist_ids: List[int], 
            date_from: datetime.datetime = None, date_to: datetime.datetime = None, 
            before_hour: datetime.time = None, after_hour: datetime.time = None
            ) -> List[Dict]:
        """Parse available appointment terms from the response data."""
        appointments = []

        for day_terms in data["termsForService"]["termsForDays"]:
            for term in day_terms["terms"]:
                term_datetime_from = datetime.datetime.fromisoformat(term['dateTimeFrom']).astimezone()
                if doctor_ids and term['doctor']["id"] not in doctor_ids:
                    continue
                if doctor_blacklist_ids and term['doctor']["id"] in doctor_blacklist_ids:
                    continue
                if clinic_ids and term["clinicGroupId"] not in clinic_ids:
                    continue
                if date_from and term_datetime_from < date_from.astimezone():
                    continue
                if date_to and term_datetime_from > date_to.astimezone():
                    continue
                if before_hour and term_datetime_from.time() > before_hour:
                    continue
                if after_hour and term_datetime_from.time() < after_hour:
                    continue

                term.update({
                    "correlationId": data['correlationId'],
                    "dateTimeFrom": term_datetime_from,
                    "dateTimeTo": datetime.datetime.fromisoformat(term['dateTimeTo']).astimezone(),
                    "doctorName": f'{term["doctor"]["academicTitle"]} {term["doctor"]["firstName"]} {term["doctor"]["lastName"]}'
                })
                appointments.append(term)
        return appointments    

    def get_user_info(self) -> dict:
        """Get a information about user"""
        return self._get(url=self.GET_USER_URL, headers={"Content-Type": "application/json"})

    def get_appointments_terms(self, city_id: int, service_id: int, facilities_ids: List[int] = [],
                                doctor_ids: List[int] = [], doctor_blacklist_ids: List[int] = [],
                                start_date: datetime.datetime = None, lookup_days: int = 14, 
                                before_hour: datetime.time = None, after_hour: datetime.time = None,
                                language_id: int = 10
                              ) -> List[Dict]:
        """Fetch and filter appointments based on configuration."""
        date_from = start_date if start_date else datetime.datetime.today()
        date_to = date_from + datetime.timedelta(days=lookup_days)

        params = {
            "searchPlace.id": city_id,
            "searchPlace.type": 0,
            "serviceVariantId": service_id,
            "languageId": language_id,
            "searchDateFrom": date_from.strftime("%Y-%m-%d"),
            "searchDateTo": date_to.strftime("%Y-%m-%d"),
            "searchDatePreset": lookup_days,
            "delocalized": False
        }
        
        if facilities_ids:
            params["facilitiesIds"] = ",".join(map(str, facilities_ids))

        if doctor_ids:
            params["doctorsIds"] = ",".join(map(str, doctor_ids))

        visits = self._get(self.RESERVATION_SEARCH_URL, params=params)

        if visits.get("errors"):
            raise LuxmedApiError(
                f"Unexpected error during term lock: {json.dumps(visits['errors'])}"
            )

        return [
            appointment for appointment \
                in self._parse_visits(
                    visits, 
                    facilities_ids, 
                    doctor_ids,
                    doctor_blacklist_ids,
                    date_from,
                    date_to,
                    before_hour,
                    after_hour
                )
        ]

    def create_reservation_lock_term(self, appointment: dict) -> dict:
        """Lock a term for reservation."""
        date = appointment["dateTimeFrom"] \
            .astimezone(datetime.timezone.utc) \
            .strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        params = {
            "serviceVariantId": appointment["serviceId"],
            "facilityId": appointment["clinicId"],
            "roomId": appointment["roomId"],
            "scheduleId": appointment["scheduleId"],
            "date": date,
            "timeFrom": appointment["dateTimeFrom"].strftime("%H:%M"),
            "timeTo": appointment["dateTimeTo"].strftime("%H:%M"),
            "doctorId": appointment["doctor"]["id"],
        }

        reservation_lock = self._post(
            url=self.RESERVATION_LOCK_TERM_URL,
            json=params,
            headers={"Content-Type": "application/json"},
        )

        if reservation_lock.get("errors"):
            raise LuxmedApiError(
                f"Unexpected error during term lock: {json.dumps(reservation_lock['errors'])}"
            )

        logger.info("Term locked successfully for reservation.")
        return reservation_lock["value"]

    def create_reservation(self, appointment: Dict, lock: Dict) -> Dict:
        """Create reservation for the given appointment."""
        payload = {
            "serviceVariantId": appointment['serviceId'],
            "facilityId": appointment['clinicId'],
            "roomId": appointment['roomId'],
            "scheduleId": appointment['scheduleId'],
            "date": appointment['dateTimeFrom'].astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "timeFrom": appointment['dateTimeFrom'].strftime("%H:%M"),
            "doctorId": appointment['doctor']['id'],
            "temporaryReservationId": lock['temporaryReservationId'],
            "valuation": lock['valuations'][0],
            "referralRequired": False
        }

        reservation = self._post(self.RESERVATION_CONFIRM_URL, json=payload, headers={"Content-Type": "application/json"})
    
        if reservation.get("errors"):
            raise LuxmedApiError(f"Error in reservation creation: {reservation['errors']}")
        
        logger.info("Reservation successful.")
        return reservation
    
    def change_reservation(self, appointment: Dict, lock: Dict) -> Dict:
        """Change reservation term for the given appointment."""
        related_visits = lock.get('relatedVisits', [])
        if not len(related_visits):
            raise LuxmedApiError(f"Error in reservation change: lock does not have related. Lock: {lock}")

        payload = {
            "existingReservationId": related_visits[0]['reservationId'],
            "term": {
                "serviceVariantId": appointment['serviceId'],
                "facilityId": appointment['clinicId'],
                "roomId": appointment['roomId'],
                "scheduleId": appointment['scheduleId'],
                "date": appointment['dateTimeFrom'].astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "timeFrom": appointment['dateTimeFrom'].strftime("%H:%M"),
                "doctorId": appointment['doctor']['id'],
                "temporaryReservationId": lock['temporaryReservationId'],
                "valuation": lock['valuations'][0],
                "referralRequired": False,
                "parentReservationId": related_visits[0]['reservationId']
            }
        }

        reservation = self._post(self.RESERVATION_CHANGE_TERM_URL, json=payload, headers={"Content-Type": "application/json"})
    
        if reservation.get("errors"):
            raise LuxmedApiError(f"Error in reservation creation: {reservation['errors']}")
        
        logger.info("Reservation successful.")
        return reservation
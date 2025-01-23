import argparse
import datetime
import inspect
import json
import logging
import pathlib
import sys
import time
import yaml

from typing import Any
from loguru import logger

import jsonschema
import requests
import schedule

class LuxMedSniper:
    LUXMED_LOGIN_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/Account/LogIn'
    RESERVATION_SEARCH_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/terms/index'
    GET_FORGERY_TOKEN_URL = 'https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/security/getforgerytoken'
    RESERVATION_LOCK_TERM_URL = "https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/reservation/lockterm"
    RESERVATION_CONFIRM_URL = "https://portalpacjenta.luxmed.pl/PatientPortal/NewPortal/reservation/confirm"

    def __init__(self, configuration_files):
        logger.info("LuxMedSniper logger initialized")
        self._loadConfiguration(configuration_files)
        # self._setup_providers()
        self._createSession()
        self._logIn()
        self._getXsrfToken()

    def _createSession(self):
        self.session = requests.Session()

    # def validate(self) -> None:
    #     schema_file = pathlib.Path("schema.json")
    #     with schema_file.open(encoding="utf-8") as f:
    #         schema = json.load(f)
    #     jsonschema.validate(instance=self.config, schema=schema)

    def _loadConfiguration(self, configuration_files):
        def merge(a: dict[str, Any], b: dict[str, Any], error_path: str = "") -> dict[str, Any]:
            for key in b:
                if key in a:
                    if isinstance(a[key], dict) and isinstance(b[key], dict):
                        merge(a[key], b[key], f"{error_path}.{key}")
                    elif a[key] == b[key]:
                        pass
                    else:
                        raise LuxmedSniperError(f"Conflict at {error_path}.{key}")
                else:
                    a[key] = b[key]
            return a

        self.config: dict[str, Any] = {}
        for configuration_file in configuration_files:
            configuration_path = pathlib.Path(configuration_file).expanduser()
            with configuration_path.open(encoding="utf-8") as stream:
                cf = yaml.load(stream, Loader=yaml.FullLoader)
                self.config = merge(self.config, cf)

        # self.validate()

    def _logIn(self):
        json_data = {
            "login": self.config["luxmed"]["email"],
            "password": self.config["luxmed"]["password"],
        }

        response = self.session.post(
            url=LuxMedSniper.LUXMED_LOGIN_URL,
            json=json_data,
            headers={"Content-Type": "application/json"},
        )

        logger.debug("Login response: {}.\nLogin cookies: {}", response.text, response.cookies)

        if response.status_code != requests.codes["ok"]:
            raise LuxmedSniperError(f"Unexpected response {response.status_code}, cannot log in")

        logger.info("Successfully logged in!")

        token = response.json()["token"]
        self.session.headers["Authorization-Token"] = f"Bearer {token}"

    def _getXsrfToken(self):
        response = self.session.get(
            url=LuxMedSniper.GET_FORGERY_TOKEN_URL,
        )

        logger.debug("XSRF Token response: {}.\nXSRF Token cookies: {}", response.text, response.cookies)

        if response.status_code != requests.codes["ok"]:
            raise LuxmedSniperError(f"Unexpected response {response.status_code}, cannot get XSRF Token")

        logger.info("Successfully got XSRF Token!")

        token = response.json()["token"]
        self.session.headers["XSRF-TOKEN"] = token

    def _parseVisitsNewPortal(self, data, clinic_ids: list[int], doctor_ids: list[int]) -> list[dict]:
        appointments = []
        content = data.json()
        for termForDay in content["termsForService"]["termsForDays"]:
            for term in termForDay["terms"]:
                doctor = term['doctor']
                clinic_id = int(term["clinicGroupId"])
                doctor_id = int(doctor["id"])

                if doctor_ids and doctor_id not in doctor_ids:
                    continue
                if clinic_ids and clinic_id not in clinic_ids:
                    continue

                term['correlationId'] = content['correlationId']
                term['dateTimeFrom'] = datetime.datetime.fromisoformat(term['dateTimeFrom']).astimezone()
                term['dateTimeTo'] = datetime.datetime.fromisoformat(term['dateTimeTo']).astimezone()
                term['doctorName'] = f'{doctor["academicTitle"]} {doctor["firstName"]} {doctor["lastName"]}'

                appointments.append(term)

        return appointments

    def _getAppointments(self):
        try:
            (cityId, serviceId, clinicIds, doctorIds) = self.config['luxmedsniper'][
                'doctor_locator_id'].strip().split('*')

            clinicIds = [*filter(lambda x: x != -1, map(int, clinicIds.split(",")))]
            clinic_ids = clinicIds + self.config["luxmedsniper"].get("facilities_ids", [])

            doctor_ids = [*filter(lambda x: x != -1, map(int, doctorIds.split(",")))]
        except ValueError as err:
            raise LuxmedSniperError("DoctorLocatorID seems to be in invalid format") from err

        lookup_days = self.config["luxmedsniper"]["lookup_time_days"]
        date_to = datetime.date.today() + datetime.timedelta(days=lookup_days)

        params = {
            "searchPlace.id": cityId,
            "searchPlace.type": 0,
            "serviceVariantId": serviceId,
            "languageId": 10,
            "searchDateFrom": datetime.date.today().strftime("%Y-%m-%d"),
            "searchDateTo": date_to.strftime("%Y-%m-%d"),
            "searchDatePreset": lookup_days,
            "delocalized": "false",
        }

        if clinic_ids:
            params["facilitiesIds"] = clinic_ids
        if doctor_ids:
            params["doctorsIds"] = doctor_ids

        response = self.session.get(url=LuxMedSniper.RESERVATION_SEARCH_URL, params=params)

        logger.debug(response.text)

        return [
            *filter(
                lambda appointment: appointment["dateTimeFrom"].date() <= date_to,
                self._parseVisitsNewPortal(response, clinic_ids, doctor_ids),
            )
        ]

    def _createReservationLockTerm(self, appointment) -> dict:
        params = {
            "serviceVariantId":appointment['serviceId'],
            "facilityId":appointment['clinicId'],
            "roomId":appointment['roomId'],
            "scheduleId": appointment['scheduleId'],
            "date": appointment['dateTimeFrom'].astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "timeFrom": appointment['dateTimeFrom'].strftime("%H:%M"),
            "timeTo": appointment['dateTimeTo'].strftime("%H:%M"),
            "doctorId":appointment['doctor']['id']
        }

        response = self.session.post(
            url = self.RESERVATION_LOCK_TERM_URL, 
            json = params, 
            headers = {
                "Content-Type": "application/json",
            }
        )

        logger.debug(response.text)

        if response.status_code != requests.codes["ok"]:
            raise LuxmedSniperError(f"Unexpected response {response.status_code}, cannot lock term")

        reservation_lock = response.json()

        if len(reservation_lock['errors']) > 0:
            raise LuxmedSniperError(f"Unexpected error during term lock: {json.dumps(reservation_lock['errors'])}")
    
        return reservation_lock['value']

    def _createReservation(self, appointment, appointment_lock, parameters={}) -> dict:
        # parameters
        allow_rescheduling = parameters.get('AllowRescheduling', False)
        locked_valuation = appointment_lock['valuations'][0]

        # query
        params = {
            "serviceVariantId":appointment['serviceId'],
            "facilityId":appointment['clinicId'],
            "roomId":appointment['roomId'],
            "scheduleId": appointment['scheduleId'],
            "date": appointment['dateTimeFrom'].astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "timeFrom": appointment['dateTimeFrom'].strftime("%H:%M"),
            "doctorId":appointment['doctor']['id'],
            "temporaryReservationId": appointment_lock['temporaryReservationId'],
            "valuation": {
                "productInContractId": appointment_lock['valuations'][0]['productInContractId'],
                "productElementId": appointment_lock['valuations'][0]['productElementId'],
                "valuationType": appointment_lock['valuations'][0]['valuationType'],
                "price": appointment_lock['valuations'][0]['price'],

                "payerId": locked_valuation.get('payerId', None),
                "contractId": locked_valuation.get('contractId', None),
                "productInContractId": locked_valuation.get('productInContractId'),
                "productId": locked_valuation.get('productId', None),
                "productElementId": locked_valuation.get('productElementId'),
                "requireReferralForPP": locked_valuation.get('requireReferralForPP', None),
                "valuationType": locked_valuation.get('valuationType'),
                "price": locked_valuation.get('price'),
                "isReferralRequired": locked_valuation.get('isReferralRequired', None),
                "isExternalReferralAllowed": locked_valuation.get('isExternalReferralAllowed', None),
                "alternativePrice": locked_valuation.get('alternativePrice', None)
            },
            "referralRequired": allow_rescheduling
        }
        
        response = self.session.post(url=self.RESERVATION_CONFIRM_URL, json=params,
            headers = {
                "Content-Type": "application/json",
            })

        logger.debug(response.text)

        if response.status_code != requests.codes["ok"]:
            raise LuxmedSniperError(f"Unexpected response {response.status_code}, cannot create reservation")

        reservation = response.json()

        if len(reservation['errors']) > 0:
            raise LuxmedSniperError(f"Unexpected error during reservation creating: {json.dumps(reservation['errors'])}")
    
        return reservation['value']
    
    def check(self):
        appointments = self._getAppointments()
        
        if not appointments:
            logger.info("No appointments found.")
            return
        for appointment in appointments:
            logger.info(
                "Appointment found! {dateTimeFrom} at {clinic} - {doctorName}".format(
                    **appointment))

    def hunt(self):
        appointments = self._getAppointments()
        
        if not appointments:
            logger.info("No appointments found.")
            return
        else:
            # get first free appointment
            appointment = appointments[0]
            reservation_lock = self._createReservationLockTerm(appointment)
            reservation = self._createReservation(appointment, reservation_lock)

            logger.info(
                "Reserved term! {dateTimeFrom} at {clinic} - {doctorName}".format(
                    **appointment))

def work(config):
    try:
        luxmed_sniper = LuxMedSniper(config)
        # luxmed_sniper.check()
        luxmed_sniper.hunt()

    except LuxmedSniperError as s:
        logger.error(s)

class LuxmedSniperError(Exception):
    pass

def setup_logging():
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists.
            level: str | int
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message.
            frame, depth = inspect.currentframe(), 0
            while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    requests_log = logging.getLogger("urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    loguru_config = {
        "handlers": [
            {"sink": sys.stdout, "level": "INFO"},
            {
                "sink": "debug.log",
                "format": "{time} - {message}",
                "serialize": True,
                "rotation": "1 week",
            },
        ]
    }
    logger.configure(handlers=loguru_config["handlers"])


if __name__ == "__main__":
    setup_logging()

    logger.info("LuxMedSniper - Lux Med Appointment Sniper")
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-c", "--config",
        help="Configuration file path", default=["luxmedSniper.yaml"],
        nargs="*"
    )
    parser.add_argument(
        "-d", "--delay",
        type=int, help="Delay in fetching updates [s]", default=1800
    )
    args = parser.parse_args()
    work(args.config)
    schedule.every(args.delay).seconds.do(work, args.config)
    while True:
        schedule.run_pending()
        time.sleep(1)
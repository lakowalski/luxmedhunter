from utils.config import load_configuration
from utils.db import init_database, create_appointment, get_luxmed_credentials, create_luxmed_credentials, delete_luxmed_credentials, list_user_appointments, delete_appointment
from utils.luxmedapi import LuxmedApi, LuxmedApiError
from models import Appointment, AppointmentStatus, AppointmentQuery
from typing import Dict
import json
import datetime
import click
import getpass

def create_query_from_search_params(params: Dict) -> Dict:
    return {
        "name": params["searchName"],
        "query": AppointmentQuery(
            city_id=params["cityId"],
            service_id=params["serviceVariantId"],
            facilities_ids=params.get("facilitiesIds", []),
            doctor_ids=params.get("doctorsIds", []),
            doctor_blacklist_ids=[],
            start_date=params["searchDateFrom"],
            lookup_time_days=params["searchDatePreset"]
        )
    }

def get_last_search_params(account_email: str) -> Dict:
    credentials = get_luxmed_credentials(email=account_email)
    luxmed_api = LuxmedApi(email=credentials.email, password=credentials.password)
    search_params = luxmed_api.get_recent_search_parameters()
    query_data = create_query_from_search_params(search_params[0])
    return query_data

@click.group()
@click.option('-c', '--config', default="config.yaml", help="Configuration file path")
def cli(config):
    config_data = load_configuration(config)
    init_database(config_data['database_file'])

@cli.command()
@click.argument('account_email')
def get_last_search(account_email: str):
    last_search_params = get_last_search_params(account_email)
    last_search_params["query"] = last_search_params["query"].model_dump()
    print(json.dumps(last_search_params, indent=2))

@cli.command()
@click.argument('account_email')
def create_appointment_from_last_search(account_email: str):
    query_data = get_last_search_params(account_email)
    appointment = Appointment(
        comment=f'{query_data["name"]}-{datetime.datetime.now().strftime("%Y%m%d")}',
        status=AppointmentStatus.active,
        account_email=account_email,
        check_frequency=300,
        query=query_data["query"]
    )
    created_appointment = create_appointment(appointment)
    print(f"Appointment created successfully:\n{json.dumps(created_appointment.model_dump(), indent=2)}")

@cli.command()
@click.argument('account_email')
def create_credentials(account_email: str):
    if get_luxmed_credentials(email=account_email):
        print(f"Error: Credentials for {account_email} already exist.")
        return
    password = getpass.getpass(prompt='Password: ')
    try:
        LuxmedApi(email=account_email, password=password)
        create_luxmed_credentials(email=account_email, password=password)
        print(f"Credentials for {account_email} saved successfully.")
    except LuxmedApiError as e:
        print(f"Failed to create credentials: {e}")

@cli.command()
@click.argument('account_email')
def delete_credentials(account_email: str):
    if not get_luxmed_credentials(email=account_email):
        print(f"Error: Credentials for {account_email} do not exist.")
        return
    delete_luxmed_credentials(email=account_email)
    print(f"Credentials for {account_email} deleted successfully.")

@cli.command()
@click.argument('account_email')
def list_users_appointments(account_email: str):
    appointments = list_user_appointments(email=account_email)
    for appointment in appointments:
        print(json.dumps(appointment.model_dump(), indent=2))

@cli.command(name='delete-appointment')
@click.argument('appointment_id')
def delete_appointment_cmd(appointment_id: str):
    if delete_appointment(appointment_id):
        print(f"Appointment {appointment_id} deleted successfully.")
    else:
        print(f"Error: Appointment {appointment_id} not found.")

if __name__ == '__main__':
    cli()
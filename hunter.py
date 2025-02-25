import logging
import sys
import click
from loguru import logger
from utils.appointmentshunter import LuxmedAppointmentHunter

def setup_logging():
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            level = logger.level(record.levelname).name if record.levelname in logger._levels else record.levelno
            logger.opt(depth=2, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")  # TODO: INFO
    logger.add("debug.log", format="{time} - {message}", rotation="1 week", serialize=True)

@click.command()
@click.option('-c', '--config', default="config.yaml", help="Configuration file path")
@click.option('-d', '--delay', type=int, default=None, help="Delay in fetching updates [s]")
def main(config, delay):
    setup_logging()
    logger.info("LuxMedAppointmentHunter - Appointment Hunting Script")

    hunter = LuxmedAppointmentHunter(config_file=config)
    if delay:
        hunter.run_scheduler(interval=delay)
    else:
        hunter.hunt_appointments()

if __name__ == "__main__":
    main()
import logging
import sys
import argparse
from loguru import logger
from utils.appointmentshunter import LuxmedAppointmentHunter

def setup_logging():
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            level = logger.level(record.levelname).name if record.levelname in logger._levels else record.levelno
            logger.opt(depth=2, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.remove()
    logger.add(sys.stdout, level="DEBUG") ## TODO: INFO
    logger.add("debug.log", format="{time} - {message}", rotation="1 week", serialize=True)

def main():
    setup_logging()
    logger.info("LuxMedAppointmentHunter - Appointment Hunting Script")

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-c", "--config", help="Configuration file path", default="config.yaml", nargs="*")
    parser.add_argument("-d", "--delay", type=int, help="Delay in fetching updates [s]", default=None)
    args = parser.parse_args()

    hunter = LuxmedAppointmentHunter(config_file=args.config)
    if args.delay:
        hunter.run_scheduler(interval=args.delay)
    else:
        hunter.hunt_appointments()
        
if __name__ == "__main__":
    main()
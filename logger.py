import logging
from datetime import datetime


date = datetime.now().strftime("%Y-%m-%d")
logging_file_path = f"{date}.log"
logging.basicConfig(
    filename=logging_file_path,
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def log(type: str, message: str):
    if type == "info":
        logging.info(message)
    elif type == "warning":
        logging.warning(message)
    elif type == "error":
        logging.error(message)
    elif type == "debug":
        logging.debug(message)
    else:
        logging.info(message)  

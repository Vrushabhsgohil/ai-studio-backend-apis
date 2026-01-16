import logging
from app.core.config import settings

class BaseService:
    """
    Base service class with shared logging and configuration access.
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings

    def log_info(self, message: str):
        self.logger.info(message)

    def log_error(self, message: str, error: Exception = None):
        if error:
            self.logger.error(f"{message}: {str(error)}")
        else:
            self.logger.error(message)

    def log_warning(self, message: str):
        self.logger.warning(message)

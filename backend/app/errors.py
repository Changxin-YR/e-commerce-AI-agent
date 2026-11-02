"""Errors safe to show at the local API/CLI boundary."""


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code

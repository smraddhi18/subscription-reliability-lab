"""Application exceptions with stable HTTP status and public error codes."""


class ApplicationError(Exception):
    status_code = 400
    error_code = "application_error"

    def __init__(self, message, *, status_code=None, error_code=None):
        super().__init__(message)
        self.status_code = self.status_code if status_code is None else status_code
        self.error_code = self.error_code if error_code is None else error_code

    def as_payload(self):
        return {"error": str(self), "code": self.error_code}


class DomainError(ApplicationError):
    """Expected request or domain failure safe to return to an API caller."""


class GenericException(ApplicationError):
    """Unexpected application failure represented by a safe generic response."""

    status_code = 500
    error_code = "internal_server_error"

    def __init__(self, message="An unexpected error occurred."):
        super().__init__(message)

class ServiceError(Exception):
    """Raised when a service-layer operation cannot be completed."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code

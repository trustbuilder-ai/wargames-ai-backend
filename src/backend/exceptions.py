class NotFoundError(Exception):
    """Exception raised when a requested resource is not found."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class EvaluationDecodeError(Exception):
    """Exception raised when there is an error decoding the evaluation result."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
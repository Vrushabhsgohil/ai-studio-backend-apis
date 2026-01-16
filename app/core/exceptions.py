class AIStudioError(Exception):
    """Base exception for all AI Studio errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AIServiceError(AIStudioError):
    """Raised when an AI service (OpenAI, Fal, etc.) fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=502)

class ModerationError(AIStudioError):
    """Raised when content fails moderation."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class DatabaseError(AIStudioError):
    """Raised when a database operation fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)

class ValidationError(AIStudioError):
    """Raised when input validation fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

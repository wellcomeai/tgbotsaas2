"""
Custom Exceptions - кастомные исключения приложения
"""


class BotFactoryException(Exception):
    """Base exception for Bot Factory"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ValidationError(BotFactoryException):
    """Validation error"""
    pass


class NotFoundError(BotFactoryException):
    """Resource not found error"""
    pass


class UserNotFoundError(NotFoundError):
    """User not found error"""
    pass


class BotNotFoundError(NotFoundError):
    """Bot not found error"""
    pass


class MessageNotFoundError(NotFoundError):
    """Message not found error"""
    pass


class BroadcastNotFoundError(NotFoundError):
    """Broadcast not found error"""
    pass


class AuthenticationError(BotFactoryException):
    """Authentication error"""
    pass


class AuthorizationError(BotFactoryException):
    """Authorization error"""
    pass


class BotLimitReachedError(ValidationError):
    """Bot limit reached error"""
    pass


class TelegramAPIError(BotFactoryException):
    """Telegram API error"""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.status_code = status_code
        super().__init__(message, error_code)


class RateLimitError(BotFactoryException):
    """Rate limit exceeded error"""
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message)


class ConfigurationError(BotFactoryException):
    """Configuration error"""
    pass


class DatabaseError(BotFactoryException):
    """Database error"""
    pass


class ServiceUnavailableError(BotFactoryException):
    """Service temporarily unavailable"""
    pass


class BusinessLogicError(BotFactoryException):
    """Business logic validation error"""
    pass


class ExternalServiceError(BotFactoryException):
    """External service error"""
    def __init__(self, message: str, service_name: str, error_code: str = None):
        self.service_name = service_name
        super().__init__(message, error_code)

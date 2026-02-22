"""
Structured logging configuration using structlog.

This module sets up JSON-formatted structured logging for production
environments and human-readable logging for development.
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog


class UserFriendlyLogger:
    """
    Enhanced logger that provides user-friendly error messages alongside technical logging.
    """

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def error_with_user_message(self, error: Exception, user_message: str, **kwargs):
        """
        Log an error with both technical details and user-friendly message.

        Args:
            error: The exception that occurred
            user_message: User-friendly message for frontend/API responses
            **kwargs: Additional context for structured logging
        """
        self.logger.error(
            "error_with_user_message",
            error_type=type(error).__name__,
            error_message=str(error),
            user_message=user_message,
            **kwargs
        )

    def warning_with_user_message(self, message: str, user_message: str, **kwargs):
        """
        Log a warning with user-friendly context.

        Args:
            message: Technical warning message
            user_message: User-friendly message
            **kwargs: Additional context
        """
        self.logger.warning(
            "warning_with_user_message",
            message=message,
            user_message=user_message,
            **kwargs
        )

    def info_with_user_context(self, message: str, user_context: str = None, **kwargs):
        """
        Log info with optional user-facing context.

        Args:
            message: Technical message
            user_context: Optional user-friendly context
            **kwargs: Additional context
        """
        self.logger.info(
            "info_with_user_context",
            message=message,
            user_context=user_context,
            **kwargs
        )


def get_user_friendly_logger(name: str) -> UserFriendlyLogger:
    """
    Get a user-friendly logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        UserFriendlyLogger instance
    """
    return UserFriendlyLogger(name)


def setup_logging(log_level: str = "INFO", environment: str = "development") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Application environment (development, production)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Shared processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Environment-specific processors
    if environment == "production":
        # JSON logging for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Pretty console logging for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


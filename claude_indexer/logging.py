"""Centralized logging configuration for the indexer."""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import loguru
    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False


class IndexerLogger:
    """Centralized logger for the indexer with configurable output."""
    
    def __init__(self, level: str = "INFO", quiet: bool = False, verbose: bool = False,
                 log_file: Optional[Path] = None):
        self.level = level
        self.quiet = quiet
        self.verbose = verbose
        self.log_file = log_file
        
        # Determine effective level
        if quiet:
            self.effective_level = "ERROR"
        elif verbose:
            self.effective_level = "DEBUG"
        else:
            self.effective_level = level
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        if LOGURU_AVAILABLE:
            self._setup_loguru()
        else:
            self._setup_stdlib_logging()
    
    def _setup_loguru(self):
        """Setup loguru-based logging."""
        from loguru import logger
        
        # Remove default handler
        logger.remove()
        
        # Console handler
        if not self.quiet:
            logger.add(
                sys.stderr,
                level=self.effective_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                colorize=True
            )
        
        # File handler
        if self.log_file:
            logger.add(
                self.log_file,
                level="DEBUG",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="10 MB",
                retention="7 days"
            )
        
        self.logger = logger
    
    def _setup_stdlib_logging(self):
        """Setup standard library logging."""
        # Create logger
        logger = logging.getLogger("claude_indexer")
        logger.setLevel(getattr(logging, self.effective_level))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler
        if not self.quiet:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(getattr(logging, self.effective_level))
            
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s'
            )
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # File handler
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        self.logger = logger
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        if LOGURU_AVAILABLE:
            self.logger.debug(message, **kwargs)
        else:
            self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        if LOGURU_AVAILABLE:
            self.logger.info(message, **kwargs)
        else:
            self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        if LOGURU_AVAILABLE:
            self.logger.warning(message, **kwargs)
        else:
            self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        if LOGURU_AVAILABLE:
            self.logger.error(message, **kwargs)
        else:
            self.logger.error(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        if LOGURU_AVAILABLE:
            self.logger.exception(message, **kwargs)
        else:
            self.logger.exception(message, **kwargs)


# Global logger instance
_logger: Optional[IndexerLogger] = None


def setup_logging(level: str = "INFO", quiet: bool = False, verbose: bool = False,
                 log_file: Optional[Path] = None) -> IndexerLogger:
    """Setup global logging configuration."""
    global _logger
    _logger = IndexerLogger(level, quiet, verbose, log_file)
    return _logger


def get_logger() -> IndexerLogger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = IndexerLogger()
    return _logger
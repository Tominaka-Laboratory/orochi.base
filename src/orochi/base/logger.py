import sys
import os
import logging

try:
    from loguru import logger

    logger.level("BACKUP", no=100)
    _HAS_LOGURU = True
except ImportError:
    _HAS_LOGURU = False
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(process)d] | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("orochi")



class Logger:
    def __init__(
        self, 
        level: str = "INFO", 
        work_dir: str = None, 
        study_name:str = None, 
        rotation: str = "1 day"
    ):
        """
        Initializes the Logger object.

        Args:
            level (str): The logging level (e.g., "INFO", "DEBUG", "ERROR"). Defaults to "INFO".
            log_dir (str, optional): The directory to store log files. If None, no file output. Defaults to None.
            rotation (str, optional): The rotation interval for log files (e.g., "1 day", "1 week"). If None, no rotation. Defaults to "1 day".
        """
        self.level = level.upper()
        self.work_dir = work_dir
        self.study_name = study_name
        self.log_dir = None
        self.rotation = rotation
        self._backup_count = 365 * 5
        self.init_logger()

    def init_logger(self):
        """
        Configures the logger using loguru (or standard logging fallback).
        """
        if not _HAS_LOGURU:
            self.logger = logger
            return

        self.logger = logger.bind(log_dir=self.log_dir)
        self.logger.remove()

        self.logger.add(
            sys.stdout,
            level=self.level,
            format="[<green>{time:YYYY-MM-DD HH:mm:ss}</green>] [{process}] | <level>{level}</level> | <level>{message}</level>",
        )
        if self.log_dir:
            self.logger.add(
                os.path.join(self.log_dir, "_info.log"),
                level="INFO",
                rotation=self.rotation,
                retention=self._backup_count,
                encoding="utf-8",
                format="[{time:YYMMDD HH:mm:ss}] [{process}] | {level} | {message}",
            )
            # self.logger.add(
            #     os.path.join(self.log_dir, "_debug.log"),
            #     level="DEBUG",
            #     rotation=self.rotation,
            #     retention=self._backup_count,
            #     encoding="utf-8",
            #     format="[{time:YYMMDD HH:mm:ss}] [{process}] | {level} | {name}:{function}:{line} {message}",
            # )
            self.logger.add(
                os.path.join(self.log_dir, "_error.log"),
                level="ERROR",
                rotation=self.rotation,
                retention=self._backup_count,
                encoding="utf-8",
                format="[{time:YYMMDD HH:mm:ss}] [{process}]  | {level} | {name}:{function}:{line} {message}",
            )
            # self.logger.add(
            #     os.path.join(self.log_dir, "_params.log"),
            #     level="BACKUP",
            #     #    serialize=True,
            #     rotation=self.rotation,
            #     retention=self._backup_count,
            #     encoding="utf-8",
            #     format="{time:YYMMDDHHmmss}:{message}",
            # )
        # self.logger.debug(f"{__file__}")

    def set_backup_count(self, val):
        """
        Sets the number of backup log files to keep.

        Args:
            val (int): The number of backup log files.
        """
        self._backup_count = val

    def get_backup_count(self):
        """
        Gets the number of backup log files to keep.

        Returns:
            int: The number of backup log files.
        """
        return self._backup_count

    backup_count = property(get_backup_count, set_backup_count)

    def set_fmt(self, fmt):
        """
        Sets the log message format.

        Args:
            fmt (str): The log message format string.
        """
        self.logger.remove()
        self.logger.add(sys.stdout, format=fmt, level=self.level)
        if self.log_dir:
            self.logger.add(
                os.path.join(self.log_dir, "info.log"),
                level="INFO",
                rotation=self.rotation,
                retention=self._backup_count,
                encoding="utf-8",
                format=fmt,
            )
            self.logger.add(
                os.path.join(self.log_dir, "debug.log"),
                level="DEBUG",
                rotation=self.rotation,
                retention=self._backup_count,
                encoding="utf-8",
                format=fmt,
            )
            self.logger.add(
                os.path.join(self.log_dir, "error.log"),
                level="ERROR",
                rotation=self.rotation,
                retention=self._backup_count,
                encoding="utf-8",
                format=fmt,
            )

    def get_fmt(self):
        """
        Gets the log message format.

        Returns:
            str: The log message format string.
        """
        return self.logger._core.formatters[0]._fmt

    fmt = property(get_fmt, set_fmt)

    def info(self, message, *args, **kwargs):
        """
        Logs a message with INFO level.

        Args:
            message (str): The log message.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        self._on_logging()      
        self.logger.info(message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        """
        Logs a message with DEBUG level.

        Args:
            message (str): The log message.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        self._on_logging()
        self.logger.debug(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """
        Logs a message with ERROR level.

        Args:
            message (str): The log message.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        self._on_logging()
        self.logger.error(message, *args, **kwargs)

    def backup(self, message, *args, **kwargs):
        """
        Logs a message with BACKUP level.
        """
        self._on_logging()
        if _HAS_LOGURU:
            self.logger.log("BACKUP", message, *args, **kwargs)
        else:
            self.logger.info(message, *args, **kwargs)


    def _on_logging(self):
        if self.work_dir is not None and self.study_name is not None:
            log_dir = os.path.join(self.work_dir, self.study_name)
            if log_dir != self.log_dir:
                self.log_dir = log_dir
                if not os.path.exists(self.log_dir):
                    os.makedirs(self.log_dir, exist_ok=True)
                self.init_logger()
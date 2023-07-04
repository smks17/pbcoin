import logging
from typing import Optional

import pbcoin.config as conf


class TracebackInfoFilter(logging.Filter):
    """Clear or restore the exception on log records"""
    def __init__(self, clear=True):
        self.clear = clear
    def filter(self, record):
        if self.clear:
            record._exc_info_hidden, record.exc_info = record.exc_info, None
            # clear the exception traceback text cache, if created.
            record.exc_text = None
        elif hasattr(record, "_exc_info_hidden"):
            record.exc_info = record._exc_info_hidden
            del record._exc_info_hidden
        return True


def getLogger(name: str, do_logging: Optional[bool]=None):
    logger = logging.getLogger(name)
    if conf.settings.glob.config:
        if do_logging is None:
            logger.disabled = not conf.settings.logger.do_logging
        else:
            logger.disabled = not do_logging
    else:
        logger.disabled = True
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(conf.settings.logger.log_format,
                                  datefmt=conf.settings.logger.log_date_format)
    logfile = logging.FileHandler(conf.settings.logger.log_filename)
    logfile.setFormatter(formatter)
    logfile.setLevel(conf.settings.logger.log_level)
    logfile.addFilter(TracebackInfoFilter())

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.ERROR)
    console.addFilter(TracebackInfoFilter(False))

    logger.addHandler(console)
    logger.addHandler(logfile)
    return logger


def log_error_message(logger: logging.Logger,
                      hostname: str,
                      req_type: str,
                      res_type: str):
    logger.error(f"Get error from node {hostname}"
                 f"for message {req_type}"
                 f"with err {res_type}")

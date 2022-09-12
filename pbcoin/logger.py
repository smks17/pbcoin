import logging

from .config import LoggerCfg

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


def getLogger(name: str, do_logging=LoggerCfg.do_logging):
    logger = logging.getLogger(name)
    if not do_logging:
        logger.disabled = True
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(LoggerCfg.log_format, datefmt=LoggerCfg.log_date_format)
    logfile = logging.FileHandler(LoggerCfg.log_filename)
    logfile.setFormatter(formatter)
    logfile.setLevel(LoggerCfg.log_level)
    logfile.addFilter(TracebackInfoFilter())

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.ERROR)
    console.addFilter(TracebackInfoFilter(False))

    logger.addHandler(console)
    logger.addHandler(logfile)
    return logger

"""Quiet third party loggers so structured app logs stay readable.

Call quiet_noisy_loggers() at the end of setup_logging(). TQDM_DISABLE hides progress bars that
some embedding wrappers print (must be set before the first bar is created).
"""
import logging
import os

NOISY = ("httpx", "httpx2", "httpcore", "pinecone", "openai", "urllib3", "langsmith")


def quiet_noisy_loggers(level: int = logging.WARNING) -> None:
    os.environ.setdefault("TQDM_DISABLE", "1")
    for name in NOISY:
        logging.getLogger(name).setLevel(level)

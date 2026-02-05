"""Retry logic and error handling utilities."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from functools import wraps


# Common retry decorator for LLM calls
def retry_llm_call(func):
    """
    Retry decorator for LLM API calls.
    
    Retries up to 3 times with exponential backoff.
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )(func)


# Retry decorator for data loading
def retry_data_load(func):
    """
    Retry decorator for data loading operations.
    
    Retries up to 2 times with shorter backoff.
    """
    return retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=1, max=3)
    )(func)

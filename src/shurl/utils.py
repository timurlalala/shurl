from string import ascii_lowercase, ascii_uppercase, digits
from random import choices
from typing import Tuple
from logging import getLogger

logger = getLogger('shurl_utils')

alphabet = ascii_lowercase + ascii_uppercase + digits

def generate_random_string(length:int = 8) -> str:
    return ''.join(choices(alphabet, k=length))

def validate_and_fix_url(url:str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        logger.debug(f"Fixed url to {url}")
    return url
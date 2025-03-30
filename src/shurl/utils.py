from string import ascii_lowercase, ascii_uppercase, digits
from random import choices

alphabet = ascii_lowercase + ascii_uppercase + digits

def generate_random_string(length:int = 8) -> str:
    return ''.join(choices(alphabet, k=length))

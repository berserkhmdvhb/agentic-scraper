from cryptography.fernet import Fernet

from agentic_scraper.core.settings import get_settings

settings = get_settings()

fernet = Fernet(settings.encryption_secret.encode())


def encrypt(plaintext: str) -> str:
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return fernet.decrypt(ciphertext.encode()).decode()

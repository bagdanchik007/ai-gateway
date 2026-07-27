"""Sicherheitsfunktionen rund um API-Keys.

Gespeichert wird ausschließlich der sha256-Hash eines Keys (siehe APIKey-Modell).
Der Klartext-Key wird dem User genau einmal bei der Erzeugung angezeigt und ist
danach nicht mehr rekonstruierbar — analog zum Umgang mit Provider-Keys bei
OpenAI/Stripe/GitHub.
"""

import hashlib
import secrets

API_KEY_PREFIX = "sk-gw"  # "gw" = Gateway — unterscheidet unsere Keys von Provider-Keys in Logs


def generate_api_key() -> tuple[str, str, str]:
    """Erzeugt einen neuen API-Key.

    Rückgabe: (plain_key, key_hash, key_prefix)
    - plain_key: wird dem User einmalig gezeigt, nirgends gespeichert
    - key_hash: sha256-Hexdigest, wird in der DB gespeichert (APIKey.key_hash)
    - key_prefix: die ersten Zeichen im Klartext, für Anzeige/Logs
    """
    token = secrets.token_urlsafe(32)
    plain_key = f"{API_KEY_PREFIX}-{token}"
    key_hash = hash_api_key(plain_key)
    key_prefix = plain_key[:12]  # muss zur Spaltengröße APIKey.key_prefix (VARCHAR(12)) passen
    return plain_key, key_hash, key_prefix


def hash_api_key(plain_key: str) -> str:
    """sha256 statt bcrypt/argon2: der Key selbst ist bereits hochentropisch

    (256 Bit Zufall aus secrets.token_urlsafe). Anders als bei Nutzerpasswörtern
    braucht es keinen absichtlich langsamen Hash, um Brute-Force zu erschweren —
    ein Angreifer müsste ohnehin den vollen 256-Bit-Raum durchsuchen.
    """
    return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()

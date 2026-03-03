import os

# Допоміжна функція для перетворення тексту в числа (наприклад, порту)
def try_parse(type, value: str):
    try:
        return type(value)
    except Exception:
        return None

# Налаштування для бази даних PostgreSQL
# Якщо програма не знайде налаштувань у системі, вона використає значення після 'or'
POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or "localhost"
POSTGRES_PORT = try_parse(int, os.environ.get("POSTGRES_PORT")) or 5432
POSTGRES_USER = os.environ.get("POSTGRES_USER") or "user"
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("POSTGRES_PASS") or "pass"
POSTGRES_DB = os.environ.get("POSTGRES_DB") or "test_db"
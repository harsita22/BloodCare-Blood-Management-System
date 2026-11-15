import os


_REQUIRED_DB_ENV_VARS = (
    "DB_HOST",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "DB_PORT",
)

_missing_db_env_vars = [
    name for name in _REQUIRED_DB_ENV_VARS
    if not os.environ.get(name)
]
if _missing_db_env_vars:
    raise RuntimeError(
        "Missing required database environment variable(s): "
        + ", ".join(_missing_db_env_vars)
    )

try:
    _db_port = int(os.environ["DB_PORT"])
except ValueError:
    raise RuntimeError("DB_PORT must be an integer.") from None

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "port": _db_port,
}

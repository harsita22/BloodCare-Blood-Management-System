import os

def get_env(primary, fallback=None):
    value = os.environ.get(primary)
    if value:
        return value

    if fallback:
        value = os.environ.get(fallback)
        if value:
            return value

    raise RuntimeError(
        f"Missing required environment variable: {primary}"
    )

DB_CONFIG = {
    "host": get_env("DB_HOST", "TIDB_HOST"),
    "user": get_env("DB_USER", "TIDB_USER"),
    "password": get_env("DB_PASSWORD", "TIDB_PASSWORD"),
    "database": get_env("DB_NAME", "TIDB_DATABASE"),
    "port": int(get_env("DB_PORT", "TIDB_PORT")),
}

ssl_ca = os.environ.get("DB_SSL_CA") or os.environ.get("TIDB_SSL_CA")

if ssl_ca:
    DB_CONFIG.update({
        "ssl_ca": ssl_ca,
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    })

import os
import app as bloodcare

DEMO_DATABASE = "blood_management_demo_db"

# Explicitly use LOCAL MySQL for local development.
bloodcare.DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": os.environ["LOCAL_DB_PASSWORD"],
    "database": DEMO_DATABASE,
    "port": 3306
}

print("=" * 45)
print("       BLOODCARE LOCAL DEMO SERVER")
print("=" * 45)
print(f"Database : {DEMO_DATABASE}")
print("Host     : 127.0.0.1")
print("Port     : 5001")
print("Debug    : Disabled")
print("=" * 45)

bloodcare.app.run(
    host="127.0.0.1",
    port=5001,
    debug=False
)

import app as bloodcare

DEMO_DATABASE = "blood_management_demo_db"

# Explicitly select the isolated demo database.
bloodcare.DB_CONFIG = {
    **bloodcare.DB_CONFIG,
    "database": DEMO_DATABASE
}

print("=" * 45)
print("       BLOODCARE DEMO SERVER")
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

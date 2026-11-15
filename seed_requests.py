from datetime import date, datetime, timedelta
import random
import mysql.connector
from config import DB_CONFIG

random.seed(91)
conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()

try:
    cur.execute("SELECT hospital_id FROM hospital")
    hospital_ids = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT blood_group_id FROM blood_group")
    group_ids = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT component_id FROM blood_component")
    component_ids = [r[0] for r in cur.fetchall()]

    if not hospital_ids or not group_ids or not component_ids:
        raise RuntimeError("Hospitals, blood groups, or components are missing.")

    cur.execute("SELECT COUNT(*) FROM hospital_request")
    existing = cur.fetchone()[0]
    needed = max(0, 50 - existing)

    today = date.today()
    urgency_levels = ["Normal", "Urgent", "Emergency"]

    for i in range(needed):
        request_date = datetime.now() - timedelta(days=random.randint(0, 45))
        required_date = today + timedelta(days=random.randint(-5, 14))
        quantity = random.choice([250, 300, 350, 450, 500, 600, 900, 1000])

        cur.execute("""
            INSERT INTO hospital_request
            (hospital_id, blood_group_id, component_id, quantity_ml,
             request_date, emergency_level, request_status, required_date)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
        """, (
            random.choice(hospital_ids),
            random.choice(group_ids),
            random.choice(component_ids),
            quantity,
            request_date,
            random.choices(
                urgency_levels, weights=[5, 3, 2], k=1
            )[0],
            required_date
        ))

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM hospital_request")
    print("Total hospital requests:", cur.fetchone()[0])

    cur.execute("""
        SELECT emergency_level, COUNT(*)
        FROM hospital_request
        GROUP BY emergency_level
        ORDER BY emergency_level
    """)
    print("Requests by urgency:")
    for row in cur.fetchall():
        print(row)

    cur.execute("""
        SELECT request_status, COUNT(*)
        FROM hospital_request
        GROUP BY request_status
    """)
    print("Requests by status:")
    for row in cur.fetchall():
        print(row)

    print("Hospital request demo data generated successfully.")

except Exception:
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()

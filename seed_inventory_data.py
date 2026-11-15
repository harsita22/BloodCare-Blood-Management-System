from datetime import date, timedelta
import random
import mysql.connector
from config import DB_CONFIG

random.seed(73)
conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()

try:
    today = date.today()

    cur.execute("SELECT blood_group_id, blood_group FROM blood_group")
    groups = cur.fetchall()
    group_ids = [g[0] for g in groups]

    cur.execute("SELECT component_id, component_name FROM blood_component")
    components = {name: cid for cid, name in cur.fetchall()}

    cur.execute("SELECT location_id FROM storage_location")
    locations = [row[0] for row in cur.fetchall()]

    # Make inventory units for existing donations that have no unit yet.
    cur.execute("""
        SELECT d.donation_id, d.donor_id, d.donation_date,
               d.component_id, d.quantity_ml, dn.blood_group_id
        FROM donation d
        JOIN donor dn ON dn.donor_id = d.donor_id
        LEFT JOIN blood_unit bu ON bu.donation_id = d.donation_id
        WHERE bu.unit_id IS NULL
    """)
    missing_units = cur.fetchall()

    def create_unit(donation_id, group_id, component_id, collection_date, quantity):
        cur.execute(
            "SELECT component_name FROM blood_component WHERE component_id=%s",
            (component_id,)
        )
        component_name = cur.fetchone()[0]

        # Synthetic demo shelf-life assumptions; not clinical guidance.
        shelf_life = {
            "Whole Blood": 35,
            "RBC": 42,
            "Plasma": 365,
            "Platelets": 5
        }.get(component_name, 30)

        expiry = collection_date + timedelta(days=shelf_life)
        status = "Available" if expiry >= today else "Expired"

        cur.execute("""
            INSERT INTO blood_unit
            (donation_id, blood_group_id, component_id, collection_date,
             expiry_date, quantity_ml, location_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            donation_id, group_id, component_id, collection_date,
            expiry, quantity, random.choice(locations), status
        ))

    for donation_id, donor_id, donation_date, component_id, quantity, group_id in missing_units:
        create_unit(donation_id, group_id, component_id, donation_date, quantity)

    # Generate donations until there are 100 total.
    cur.execute("SELECT COUNT(*) FROM donation")
    donation_count = cur.fetchone()[0]
    needed = max(0, 100 - donation_count)

    # Prefer donors who have not donated before, avoiding duplicate donations
    # for the same donor in this generated batch.
    cur.execute("""
        SELECT dn.donor_id, dn.blood_group_id
        FROM donor dn
        LEFT JOIN donation d ON d.donor_id = dn.donor_id
        WHERE d.donation_id IS NULL
        ORDER BY dn.donor_id
    """)
    donor_rows = cur.fetchall()
    random.shuffle(donor_rows)

    if len(donor_rows) < needed:
        raise RuntimeError(
            f"Need {needed} new donors without donations, but found {len(donor_rows)}. "
            "No new donations were committed."
        )

    component_names = list(components.keys())

    for donor_id, group_id in donor_rows[:needed]:
        component_name = random.choice(component_names)
        component_id = components[component_name]
        donation_date = today - timedelta(days=random.randint(0, 360))

        # Plausible example quantities for a student demo.
        quantity = {
            "Whole Blood": 450,
            "RBC": 300,
            "Plasma": 250,
            "Platelets": 200
        }.get(component_name, 450)

        cur.execute("""
            INSERT INTO donation
            (donor_id, donation_date, component_id, quantity_ml, donation_status)
            VALUES (%s, %s, %s, %s, 'Collected')
        """, (donor_id, donation_date, component_id, quantity))

        donation_id = cur.lastrowid
        create_unit(donation_id, group_id, component_id, donation_date, quantity)

        cur.execute("""
            UPDATE donor SET last_donation_date=%s WHERE donor_id=%s
        """, (donation_date, donor_id))

    conn.commit()

    for table in ["donation", "blood_unit"]:
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        print(f"{table}: {cur.fetchone()[0]} records")

    cur.execute("""
        SELECT status, COUNT(*)
        FROM blood_unit
        GROUP BY status
        ORDER BY status
    """)
    print("Inventory by status:")
    for row in cur.fetchall():
        print(row)

    print("Donation and inventory demo data generated successfully.")

except Exception:
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()

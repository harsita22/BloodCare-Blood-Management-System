import random
from datetime import date, datetime, timedelta

import mysql.connector
from config import DB_CONFIG

random.seed(20261115)
TODAY = date.today()
DB_NAME = "blood_management_demo_db"

FIRST_NAMES = [
    "Arun", "Karthik", "Sanjay", "Vijay", "Ravi", "Pranav", "Rahul",
    "Ajay", "Deepak", "Manoj", "Suresh", "Naveen", "Surya", "Hari",
    "Divya", "Priya", "Ananya", "Kavya", "Meena", "Nisha", "Aishwarya",
    "Keerthana", "Pooja", "Swathi", "Lakshmi", "Harini", "Sneha",
    "Anjali", "Ramya", "Vaishnavi"
]
LAST_NAMES = [
    "Kumar", "Raj", "Sharma", "Reddy", "Iyer", "Nair", "Menon",
    "Das", "Rao", "Patel", "Krishnan", "Pillai", "Singh", "Verma",
    "Balan", "Mohan", "Joseph", "Thomas", "Gupta", "Chandra"
]
CITIES = [
    "Chennai", "Coimbatore", "Madurai", "Trichy", "Salem",
    "Erode", "Tirunelveli", "Vellore", "Thanjavur", "Cuddalore"
]
STREETS = [
    "Anna Nagar", "Gandhi Road", "Lake View Road", "Temple Street",
    "Main Road", "Park Avenue", "Market Street", "Nehru Nagar"
]
HOSPITAL_PREFIXES = [
    "City Care", "Lifeline", "Starlight", "Green Valley",
    "Hope", "Unity", "Prime", "Sunrise", "Apollo", "Central"
]
HOSPITAL_SUFFIXES = [
    "Hospital", "Medical Centre", "Multispeciality Hospital",
    "Healthcare Institute", "General Hospital"
]

GROUPS = [
    (1, "A+"), (2, "A-"), (3, "B+"), (4, "B-"),
    (5, "AB+"), (6, "AB-"), (7, "O+"), (8, "O-")
]
COMPONENTS = [
    (1, "Whole Blood", "Complete blood unit"),
    (2, "RBC", "Red Blood Cells"),
    (3, "Plasma", "Blood plasma"),
    (4, "Platelets", "Platelet component")
]
LOCATIONS = [
    (1, "Blood Bank Room A", "REF-01", "S1"),
    (2, "Blood Bank Room A", "REF-01", "S2"),
    (3, "Blood Bank Room B", "REF-02", "S1")
]

# Demonstration component quantities and approximate shelf-life days.
COMPONENT_DATA = {
    1: (450, 35),
    2: (250, 42),
    3: (250, 365),
    4: (50, 5)
}

def make_name(i):
    return (
        FIRST_NAMES[i % len(FIRST_NAMES)] + " " +
        LAST_NAMES[(i * 7) % len(LAST_NAMES)] +
        (f" {i // len(FIRST_NAMES) + 1}" if i >= len(FIRST_NAMES) else "")
    )

def main():
    conn = mysql.connector.connect(**{**DB_CONFIG, "database": DB_NAME})
    cur = conn.cursor()

    tables = [
        "distribution", "reservation", "matching", "hospital_request",
        "blood_unit", "donation", "donor", "hospital",
        "storage_location", "blood_component", "blood_group"
    ]

    try:
        # Safety: refuse to seed a database that already contains records.
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cur.fetchone()[0]
            if count:
                raise RuntimeError(
                    f"STOP: {table} already contains {count} records. "
                    "No demo data was inserted."
                )

        # Reset AUTO_INCREMENT counters inherited from the source schema.
        for table in tables:
            cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1")

        # Lookup data
        cur.executemany(
            "INSERT INTO blood_group (blood_group_id, blood_group) VALUES (%s,%s)",
            GROUPS
        )
        cur.executemany(
            """INSERT INTO blood_component
               (component_id, component_name, description)
               VALUES (%s,%s,%s)""",
            COMPONENTS
        )
        cur.executemany(
            """INSERT INTO storage_location
               (location_id, location_name, refrigerator_number, shelf_number)
               VALUES (%s,%s,%s,%s)""",
            LOCATIONS
        )

        # 50 synthetic hospitals
        hospitals = []
        for i in range(50):
            city = CITIES[i % len(CITIES)]
            hospital_name = (
                f"{HOSPITAL_PREFIXES[i % len(HOSPITAL_PREFIXES)]} "
                f"{HOSPITAL_SUFFIXES[(i // 3) % len(HOSPITAL_SUFFIXES)]} "
                f"{i + 1:02d}"
            )
            hospitals.append((
                hospital_name,
                f"Demo Contact {i + 1}",
                str(8000000000 + i),
                f"hospital{i + 1:03d}@example.com",
                f"{i + 1}, {STREETS[i % len(STREETS)]}, {city}, Tamil Nadu"
            ))

        cur.executemany(
            """INSERT INTO hospital
               (hospital_name, contact_person, phone, email, address)
               VALUES (%s,%s,%s,%s,%s)""",
            hospitals
        )

        # 300 synthetic donors
        donors = []
        donor_meta = []
        for i in range(300):
            age = random.randint(18, 60)
            group_id = random.randint(1, 8)
            component_id = random.randint(1, 4)
            collection_age = random.randint(0, 90)
            collection_date = TODAY - timedelta(days=collection_age)

            donors.append((
                make_name(i),
                age,
                random.choice(["Male", "Female"]),
                str(9000000000 + i),
                f"donor{i + 1:03d}@example.com",
                f"{random.randint(1, 250)}, "
                f"{STREETS[i % len(STREETS)]}, "
                f"{CITIES[i % len(CITIES)]}, Tamil Nadu",
                group_id,
                collection_date,
                "Eligible" if i % 10 != 0 else "Ineligible"
            ))
            donor_meta.append((group_id, component_id, collection_date))

        cur.executemany(
            """INSERT INTO donor
               (name, age, gender, phone, email, address,
                blood_group_id, last_donation_date, eligibility_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            donors
        )

        # One synthetic donation and one blood unit per donor.
        donations = []
        units = []
        for i, (group_id, component_id, collection_date) in enumerate(donor_meta):
            quantity, shelf_life = COMPONENT_DATA[component_id]
            expired = i < 10

            if expired:
                days_old = shelf_life + random.randint(1, 30)
            else:
                days_old = random.randint(0, max(0, shelf_life - 1))

            actual_collection = TODAY - timedelta(days=days_old)
            expiry_date = actual_collection + timedelta(days=shelf_life)

            donations.append((
                i + 1,
                actual_collection,
                component_id,
                quantity,
                "Collected"
            ))

            if expired:
                status = "Expired"
            else:
                status = "Available"

            units.append((
                i + 1,
                group_id,
                component_id,
                actual_collection,
                expiry_date,
                quantity,
                random.randint(1, 3),
                status
            ))

        cur.executemany(
            """INSERT INTO donation
               (donor_id, donation_date, component_id, quantity_ml, donation_status)
               VALUES (%s,%s,%s,%s,%s)""",
            donations
        )

        cur.executemany(
            """INSERT INTO blood_unit
               (donation_id, blood_group_id, component_id, collection_date,
                expiry_date, quantity_ml, location_id, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            units
        )

        # Select 110 unique, unexpired units for matching demonstrations.
        selected_units = random.sample(range(10, 300), 110)
        distributed_indices = selected_units[:40]
        reserved_indices = selected_units[40:90]
        proposed_indices = selected_units[90:110]

        # Update lifecycle status for allocated units.
        for i in distributed_indices:
            cur.execute(
                "UPDATE blood_unit SET status='Distributed' WHERE unit_id=%s",
                (i + 1,)
            )
        for i in reserved_indices:
            cur.execute(
                "UPDATE blood_unit SET status='Reserved' WHERE unit_id=%s",
                (i + 1,)
            )

        # Create 110 requests, each linked to one selected unit.
        requests = []
        request_unit_pairs = []

        for idx in selected_units:
            unit = units[idx]
            unit_id = idx + 1
            group_id = unit[1]
            component_id = unit[2]
            quantity = unit[5]

            requests.append((
                random.randint(1, 50),
                group_id,
                component_id,
                quantity + 250,
                datetime.now() - timedelta(days=random.randint(0, 30)),
                random.choice(["Normal", "Urgent", "Critical"]),
                "Pending",
                TODAY + timedelta(days=random.randint(1, 14))
            ))
            request_unit_pairs.append((unit_id, quantity))

        # Add 40 extra pending requests for a fuller requests screen.
        for _ in range(40):
            requests.append((
                random.randint(1, 50),
                random.randint(1, 8),
                random.randint(1, 4),
                random.choice([250, 450, 500, 750, 1000]),
                datetime.now() - timedelta(days=random.randint(0, 30)),
                random.choice(["Normal", "Urgent", "Critical"]),
                "Pending",
                TODAY + timedelta(days=random.randint(1, 14))
            ))

        cur.executemany(
            """INSERT INTO hospital_request
               (hospital_id, blood_group_id, component_id, quantity_ml,
                request_date, emergency_level, request_status, required_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            requests
        )

        # Create 110 matching records: 20 Proposed, 50 Matched, 40 Distributed.
        matching_rows = []
        for position, (unit_id, quantity) in enumerate(request_unit_pairs):
            if position < 40:
                match_status = "Distributed"
            elif position < 90:
                match_status = "Matched"
            else:
                match_status = "Proposed"

            matching_rows.append((
                position + 1,
                unit_id,
                quantity,
                datetime.now() - timedelta(days=random.randint(0, 10)),
                match_status
            ))

        cur.executemany(
            """INSERT INTO matching
               (request_id, unit_id, matched_quantity_ml,
                matching_date, matching_status)
               VALUES (%s,%s,%s,%s,%s)""",
            matching_rows
        )

        # 90 reservations: 40 Distributed and 50 still Reserved.
        reservation_rows = []
        for position, (unit_id, quantity) in enumerate(request_unit_pairs[:90]):
            reservation_status = "Distributed" if position < 40 else "Reserved"
            reservation_rows.append((
                position + 1,
                unit_id,
                quantity,
                datetime.now() - timedelta(days=random.randint(0, 7)),
                reservation_status
            ))

        cur.executemany(
            """INSERT INTO reservation
               (request_id, unit_id, reserved_quantity_ml,
                reservation_date, reservation_status)
               VALUES (%s,%s,%s,%s,%s)""",
            reservation_rows
        )

        # 40 complete distributions, linked to their reservation/request/hospital.
        distribution_rows = []
        for position, (unit_id, quantity) in enumerate(request_unit_pairs[:40]):
            hospital_id = requests[position][0]
            distribution_rows.append((
                position + 1,
                unit_id,
                hospital_id,
                quantity,
                datetime.now() - timedelta(days=random.randint(0, 5)),
                f"Demo Receiver {position + 1}"
            ))

        cur.executemany(
            """INSERT INTO distribution
               (request_id, unit_id, hospital_id, distributed_quantity_ml,
                distribution_date, received_by)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            distribution_rows
        )

        conn.commit()

        print("\nDEMO DATA INSERTED SUCCESSFULLY")
        print("=" * 42)
        for table in [
            "blood_group", "blood_component", "storage_location", "hospital",
            "donor", "donation", "blood_unit", "hospital_request",
            "matching", "reservation", "distribution"
        ]:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            print(f"{table:22} {cur.fetchone()[0]:>5}")

        print("\nBLOOD UNIT STATUS")
        cur.execute(
            "SELECT status, COUNT(*) FROM blood_unit GROUP BY status ORDER BY status"
        )
        for status, count in cur.fetchall():
            print(f"{status:22} {count:>5}")

        print("\nMATCHING STATUS")
        cur.execute(
            "SELECT matching_status, COUNT(*) FROM matching "
            "GROUP BY matching_status ORDER BY matching_status"
        )
        for status, count in cur.fetchall():
            print(f"{status:22} {count:>5}")

        print("\nRESERVATION STATUS")
        cur.execute(
            "SELECT reservation_status, COUNT(*) FROM reservation "
            "GROUP BY reservation_status ORDER BY reservation_status"
        )
        for status, count in cur.fetchall():
            print(f"{status:22} {count:>5}")

        print("\nAll records are synthetic demonstration data.")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()


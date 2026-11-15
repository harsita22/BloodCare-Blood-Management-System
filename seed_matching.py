from datetime import date
import random
import mysql.connector
from config import DB_CONFIG

conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()
random.seed(21)

# Simplified ABO/Rh compatibility for RBCs.
# Whole blood uses exact-group matching in this demo.
rbc_compatibility = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}

try:
    cur.execute("SELECT blood_group_id, blood_group FROM blood_group")
    group_name = {gid: name for gid, name in cur.fetchall()}

    cur.execute("SELECT component_id, component_name FROM blood_component")
    component_name = {cid: name for cid, name in cur.fetchall()}

    cur.execute("""
        SELECT r.request_id, r.blood_group_id, r.component_id,
               r.quantity_ml, r.request_status
        FROM hospital_request r
        WHERE r.request_status = 'Pending'
        ORDER BY
          CASE r.emergency_level
            WHEN 'Emergency' THEN 1
            WHEN 'Urgent' THEN 2
            ELSE 3
          END,
          r.request_date
    """)
    requests = cur.fetchall()

    cur.execute("""
        SELECT u.unit_id, u.blood_group_id, u.component_id,
               u.quantity_ml, u.expiry_date
        FROM blood_unit u
        WHERE u.status = 'Available'
          AND u.expiry_date >= %s
        ORDER BY u.expiry_date, u.unit_id
    """, (date.today(),))
    units = cur.fetchall()

    cur.execute("SELECT request_id, unit_id FROM matching")
    existing_pairs = set(cur.fetchall())

    # Avoid assigning the same unit to more than one request.
    cur.execute("SELECT DISTINCT unit_id FROM matching")
    used_units = {row[0] for row in cur.fetchall()}

    new_matches = 0

    for request_id, req_group_id, req_component_id, req_qty, _ in requests:
        req_group = group_name[req_group_id]
        req_component = component_name[req_component_id]

        candidates = []
        for unit_id, unit_group_id, unit_component_id, unit_qty, expiry in units:
            if unit_id in used_units:
                continue
            if (request_id, unit_id) in existing_pairs:
                continue
            if unit_component_id != req_component_id:
                continue

            unit_group = group_name[unit_group_id]

            if req_component == "RBC":
                compatible = unit_group in rbc_compatibility.get(req_group, [])
            elif req_component == "Whole Blood":
                compatible = unit_group == req_group
            else:
                # Conservative demo rule for plasma and platelets:
                # exact blood-group match only.
                compatible = unit_group == req_group

            if compatible and unit_qty > 0:
                candidates.append((unit_id, unit_qty))

        if not candidates:
            continue

        unit_id, unit_qty = candidates[0]
        matched_qty = min(req_qty, unit_qty)

        cur.execute("""
            INSERT INTO matching
            (request_id, unit_id, matched_quantity_ml, matching_status)
            VALUES (%s, %s, %s, 'Matched')
        """, (request_id, unit_id, matched_qty))

        used_units.add(unit_id)
        existing_pairs.add((request_id, unit_id))
        new_matches += 1

    conn.commit()
    print("New matching records created:", new_matches)

    cur.execute("SELECT COUNT(*) FROM matching")
    print("Total matching records:", cur.fetchone()[0])

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()

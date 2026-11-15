from datetime import date, datetime

from flask import Flask, render_template, jsonify, request
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status


# ==========================================
# PAGES
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_stats():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT COUNT(*) AS total_donors
            FROM donor
        """)
        total_donors = cursor.fetchone()["total_donors"]

        cursor.execute("""
            SELECT COUNT(*) AS total_requests
            FROM hospital_request
        """)
        total_requests = cursor.fetchone()["total_requests"]

        cursor.execute("""
            SELECT COUNT(*) AS pending_requests
            FROM hospital_request
            WHERE request_status = 'Pending'
        """)
        pending_requests = cursor.fetchone()["pending_requests"]

        cursor.execute("""
            SELECT COUNT(*) AS total_units
            FROM blood_unit
            WHERE status = 'Available'
              AND expiry_date >= CURDATE()
        """)
        total_units = cursor.fetchone()["total_units"]

        cursor.execute("""
            SELECT COUNT(*) AS total_matches
            FROM matching
        """)
        total_matches = cursor.fetchone()["total_matches"]

        return jsonify({
            "success": True,
            "total_donors": total_donors,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "total_units": total_units,
            "total_matches": total_matches
        })

    except Exception:
        app.logger.exception("Unable to load dashboard statistics")
        return api_error("Unable to load dashboard statistics.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/reports")
def reports():
    return render_template("reports.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/api/reports/summary", methods=["GET"])
def get_reports_summary():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM donor) AS total_donors,
                (SELECT COUNT(*) FROM donation) AS total_donations,
                (SELECT COALESCE(SUM(quantity_ml), 0)
                 FROM donation) AS total_donated_volume_ml,
                (SELECT COUNT(*) FROM blood_unit) AS total_blood_units,
                (SELECT COUNT(*)
                 FROM blood_unit
                 WHERE status = 'Available'
                   AND expiry_date >= CURDATE()) AS available_units,
                (SELECT COUNT(*)
                 FROM blood_unit
                 WHERE status = 'Reserved') AS reserved_units,
                (SELECT COUNT(*)
                 FROM blood_unit
                 WHERE status = 'Distributed') AS distributed_units,
                (SELECT COUNT(*)
                 FROM blood_unit
                 WHERE status = 'Expired'
                    OR expiry_date < CURDATE()) AS expired_units,
                (SELECT COUNT(*) FROM hospital_request) AS total_hospital_requests,
                (SELECT COUNT(*)
                 FROM hospital_request
                 WHERE request_status = 'Pending') AS pending_requests,
                (SELECT COUNT(*) FROM matching) AS total_matching_records,
                (SELECT COUNT(*) FROM reservation) AS total_reservations,
                (SELECT COUNT(*) FROM distribution) AS total_distribution_records,
                (SELECT COALESCE(SUM(distributed_quantity_ml), 0)
                 FROM distribution) AS total_distributed_volume_ml
        """)
        overview = cursor.fetchone()

        cursor.execute("""
            SELECT
                bg.blood_group,
                COUNT(bu.unit_id) AS total_units,
                COALESCE(SUM(
                    CASE
                        WHEN bu.status = 'Available'
                         AND bu.expiry_date >= CURDATE()
                        THEN 1 ELSE 0
                    END
                ), 0) AS available_units,
                COALESCE(SUM(
                    CASE WHEN bu.status = 'Reserved'
                         THEN 1 ELSE 0 END
                ), 0) AS reserved_units,
                COALESCE(SUM(
                    CASE WHEN bu.status = 'Distributed'
                         THEN 1 ELSE 0 END
                ), 0) AS distributed_units,
                COALESCE(SUM(
                    CASE
                        WHEN bu.status = 'Expired'
                          OR bu.expiry_date < CURDATE()
                        THEN 1 ELSE 0
                    END
                ), 0) AS expired_units
            FROM blood_group bg
            LEFT JOIN blood_unit bu
                ON bu.blood_group_id = bg.blood_group_id
            GROUP BY bg.blood_group_id, bg.blood_group
            ORDER BY bg.blood_group_id
        """)
        blood_group_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT
                bc.component_name,
                COUNT(bu.unit_id) AS total_units,
                COALESCE(SUM(
                    CASE
                        WHEN bu.status = 'Available'
                         AND bu.expiry_date >= CURDATE()
                        THEN bu.quantity_ml ELSE 0
                    END
                ), 0) AS available_quantity_ml
            FROM blood_component bc
            LEFT JOIN blood_unit bu
                ON bu.component_id = bc.component_id
            GROUP BY bc.component_id, bc.component_name
            ORDER BY bc.component_id
        """)
        component_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT
                levels.emergency_level,
                COUNT(hr.request_id) AS request_count
            FROM (
                SELECT 'Normal' AS emergency_level
                UNION SELECT 'Urgent'
                UNION SELECT 'Critical'
                UNION SELECT 'Unspecified'
                UNION
                SELECT DISTINCT COALESCE(emergency_level, 'Unspecified')
                FROM hospital_request
            ) AS levels
            LEFT JOIN hospital_request hr
                ON COALESCE(hr.emergency_level, 'Unspecified')
                 = levels.emergency_level
            GROUP BY levels.emergency_level
            ORDER BY
                CASE levels.emergency_level
                    WHEN 'Critical' THEN 1
                    WHEN 'Urgent' THEN 2
                    WHEN 'Normal' THEN 3
                    ELSE 4
                END,
                levels.emergency_level
        """)
        requests_by_emergency_level = cursor.fetchall()

        cursor.execute("""
            SELECT
                statuses.request_status,
                COUNT(hr.request_id) AS request_count
            FROM (
                SELECT 'Pending' AS request_status
                UNION
                SELECT DISTINCT COALESCE(request_status, 'Unspecified')
                FROM hospital_request
            ) AS statuses
            LEFT JOIN hospital_request hr
                ON COALESCE(hr.request_status, 'Unspecified')
                 = statuses.request_status
            GROUP BY statuses.request_status
            ORDER BY statuses.request_status
        """)
        requests_by_status = cursor.fetchall()

        cursor.execute("""
            SELECT
                statuses.matching_status,
                COUNT(m.matching_id) AS matching_count
            FROM (
                SELECT 'Proposed' AS matching_status
                UNION SELECT 'Matched'
                UNION SELECT 'Cancelled'
                UNION SELECT 'Distributed'
                UNION
                SELECT DISTINCT COALESCE(matching_status, 'Unspecified')
                FROM matching
            ) AS statuses
            LEFT JOIN matching m
                ON COALESCE(m.matching_status, 'Unspecified')
                 = statuses.matching_status
            GROUP BY statuses.matching_status
            ORDER BY statuses.matching_status
        """)
        matching_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT
                statuses.reservation_status,
                COUNT(r.reservation_id) AS reservation_count
            FROM (
                SELECT 'Reserved' AS reservation_status
                UNION SELECT 'Cancelled'
                UNION SELECT 'Distributed'
                UNION
                SELECT DISTINCT COALESCE(reservation_status, 'Unspecified')
                FROM reservation
            ) AS statuses
            LEFT JOIN reservation r
                ON COALESCE(r.reservation_status, 'Unspecified')
                 = statuses.reservation_status
            GROUP BY statuses.reservation_status
            ORDER BY statuses.reservation_status
        """)
        reservation_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT
                h.hospital_name,
                COUNT(d.distribution_id) AS distribution_count,
                COALESCE(SUM(d.distributed_quantity_ml), 0)
                    AS distributed_volume_ml
            FROM hospital h
            LEFT JOIN distribution d
                ON d.hospital_id = h.hospital_id
            GROUP BY h.hospital_id, h.hospital_name
            ORDER BY h.hospital_name, h.hospital_id
        """)
        distribution_breakdown = cursor.fetchall()

        return jsonify({
            "success": True,
            "overview": overview,
            "blood_group_breakdown": blood_group_breakdown,
            "component_breakdown": component_breakdown,
            "request_breakdown": {
                "by_emergency_level": requests_by_emergency_level,
                "by_status": requests_by_status
            },
            "matching_breakdown": matching_breakdown,
            "reservation_breakdown": reservation_breakdown,
            "distribution_breakdown": distribution_breakdown
        })

    except Exception:
        app.logger.exception("Unable to load report summary")
        return api_error("Unable to load report summary.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/donors")
def donors():
    return render_template("donors.html")


@app.route("/inventory")
def inventory():
    return render_template("inventory.html")


@app.route("/reservations")
def reservations():
    return render_template("reservations.html")


@app.route("/api/reservations", methods=["GET"])
def get_reservations():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                r.reservation_id,
                r.request_id,
                r.unit_id,
                r.reserved_quantity_ml,
                r.reservation_date,
                r.reservation_status,
                h.hospital_name,
                bg.blood_group,
                bc.component_name
            FROM reservation r
            JOIN hospital_request hr
                ON r.request_id = hr.request_id
            JOIN hospital h
                ON hr.hospital_id = h.hospital_id
            JOIN blood_unit bu
                ON r.unit_id = bu.unit_id
            JOIN blood_group bg
                ON bu.blood_group_id = bg.blood_group_id
            JOIN blood_component bc
                ON bu.component_id = bc.component_id
            ORDER BY r.reservation_date DESC, r.reservation_id DESC
        """)

        reservations = cursor.fetchall()

        for item in reservations:
            if item.get("reservation_date"):
                item["reservation_date"] = item["reservation_date"].strftime(
                    "%Y-%m-%d %H:%M"
                )

        return jsonify({
            "success": True,
            "reservations": reservations,
            "total": len(reservations)
        })

    except Exception:
        app.logger.exception("Unable to load reservations")
        return api_error("Unable to load reservations.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()






@app.route("/api/reservations/<int:reservation_id>/cancel", methods=["POST"])
def cancel_reservation(reservation_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT reservation_id, request_id, unit_id,
                   reserved_quantity_ml, reservation_status
            FROM reservation
            WHERE reservation_id = %s
        """, (reservation_id,))
        reservation = cursor.fetchone()

        if not reservation:
            connection.rollback()
            return api_error("Reservation not found.", 404)

        if reservation["reservation_status"] != "Reserved":
            connection.rollback()
            return api_error("Only active reservations can be cancelled.")

        initial_request_id = reservation["request_id"]
        initial_unit_id = reservation["unit_id"]

        cursor.execute("""
            SELECT request_id, request_status
            FROM hospital_request
            WHERE request_id = %s
            FOR UPDATE
        """, (initial_request_id,))
        hospital_request = cursor.fetchone()

        cursor.execute("""
            SELECT unit_id, quantity_ml, expiry_date, status
            FROM blood_unit
            WHERE unit_id = %s
            FOR UPDATE
        """, (initial_unit_id,))
        unit = cursor.fetchone()

        if not hospital_request or not unit:
            connection.rollback()
            return api_error("Related request or blood unit not found.", 404)

        cursor.execute("""
            SELECT reservation_id, request_id, unit_id,
                   reserved_quantity_ml, reservation_status
            FROM reservation
            WHERE reservation_id = %s
            FOR UPDATE
        """, (reservation_id,))
        reservation = cursor.fetchone()

        if not reservation:
            connection.rollback()
            return api_error("Reservation not found.", 404)

        if reservation["reservation_status"] != "Reserved":
            connection.rollback()
            return api_error("Only active reservations can be cancelled.")

        if (reservation["request_id"] != initial_request_id
                or reservation["unit_id"] != initial_unit_id):
            connection.rollback()
            return api_error(
                "Reservation request or blood unit changed. Please refresh."
            )

        cursor.execute("""
            SELECT reservation_id
            FROM reservation
            WHERE unit_id = %s
              AND reservation_status = 'Reserved'
              AND reservation_id <> %s
            FOR UPDATE
        """, (reservation["unit_id"], reservation_id))
        other_reservations = cursor.fetchall()

        cursor.execute("""
            SELECT matching_id, matched_quantity_ml, matching_status
            FROM matching
            WHERE request_id = %s
              AND unit_id = %s
              AND matching_status = 'Matched'
            FOR UPDATE
        """, (reservation["request_id"], reservation["unit_id"]))
        matches = cursor.fetchall()

        cursor.execute("""
            SELECT distribution_id
            FROM distribution
            WHERE unit_id = %s
            FOR UPDATE
        """, (reservation["unit_id"],))
        distributions = cursor.fetchall()

        if len(matches) != 1:
            connection.rollback()
            return api_error(
                "Could not safely identify exactly one active matching record. "
                "No changes were made."
            )

        match = matches[0]

        if match["matched_quantity_ml"] != reservation["reserved_quantity_ml"]:
            connection.rollback()
            return api_error(
                "Reservation and matching quantities differ. "
                "No changes were made."
            )

        cursor.execute("SELECT CURDATE() AS today")
        today = cursor.fetchone()["today"]
        unit_expired = (
            unit["expiry_date"] is None
            or unit["expiry_date"] < today
        )
        if unit["status"] == "Distributed":
            new_unit_status = "Distributed"
        elif unit_expired:
            new_unit_status = "Expired"
        elif other_reservations:
            new_unit_status = "Reserved"
        elif distributions:
            new_unit_status = unit["status"]
        else:
            new_unit_status = "Available"

        cursor.execute("""
            UPDATE reservation
            SET reservation_status = 'Cancelled'
            WHERE reservation_id = %s
              AND reservation_status = 'Reserved'
        """, (reservation_id,))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Reservation status changed. Please refresh.")

        cursor.execute("""
            UPDATE matching
            SET matching_status = 'Cancelled'
            WHERE matching_id = %s
              AND matching_status = 'Matched'
        """, (match["matching_id"],))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Matching status changed. No changes were saved.")

        if new_unit_status != unit["status"]:
            cursor.execute("""
                UPDATE blood_unit
                SET status = %s
                WHERE unit_id = %s
                  AND status = %s
            """, (
                new_unit_status,
                reservation["unit_id"],
                unit["status"]
            ))

            if cursor.rowcount != 1:
                connection.rollback()
                return api_error(
                    "Blood unit status could not be updated. No changes were saved."
                )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Reservation cancelled.",
            "reservation_id": reservation_id,
            "reservation_status": "Cancelled",
            "matching_id": match["matching_id"],
            "matching_status": "Cancelled",
            "unit_id": reservation["unit_id"],
            "unit_status": new_unit_status
        }), 200

    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Could not cancel reservation")
        return api_error("Could not cancel reservation.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route("/api/matching", methods=["POST"])
def record_proposed_match():
    connection = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        try:
            request_id = int(data.get("request_id"))
            unit_id = int(data.get("unit_id"))
            quantity_ml = int(data.get("matched_quantity_ml"))
        except (TypeError, ValueError):
            return api_error(
                "request_id, unit_id and matched_quantity_ml must be integers."
            )

        if request_id <= 0 or unit_id <= 0 or quantity_ml <= 0:
            return api_error("IDs and quantity must be positive.")

        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT request_id, blood_group_id, component_id,
                   quantity_ml, request_status
            FROM hospital_request
            WHERE request_id = %s
            FOR UPDATE
        """, (request_id,))
        hospital_request = cursor.fetchone()

        if not hospital_request:
            connection.rollback()
            return api_error("Hospital request not found.", 404)

        if hospital_request["request_status"] != "Pending":
            connection.rollback()
            return api_error("Request is not pending.")

        cursor.execute("""
            SELECT unit_id, blood_group_id, component_id,
                   quantity_ml, expiry_date, status
            FROM blood_unit
            WHERE unit_id = %s
            FOR UPDATE
        """, (unit_id,))
        unit = cursor.fetchone()

        if not unit:
            connection.rollback()
            return api_error("Blood unit not found.", 404)

        if unit["status"] != "Available":
            connection.rollback()
            return api_error("Blood unit is not available.")

        if unit["expiry_date"] is None:
            connection.rollback()
            return api_error("Blood unit has no expiry date.")

        cursor.execute("SELECT CURDATE() AS today")
        today = cursor.fetchone()["today"]

        if unit["expiry_date"] < today:
            connection.rollback()
            return api_error("Blood unit is expired.")

        if (
            unit["blood_group_id"] != hospital_request["blood_group_id"]
            or unit["component_id"] != hospital_request["component_id"]
        ):
            connection.rollback()
            return api_error(
                "Blood group and component must match this demo request exactly."
            )

        cursor.execute("""
            SELECT reservation_id
            FROM reservation
            WHERE unit_id = %s
              AND reservation_status = 'Reserved'
            FOR UPDATE
        """, (unit_id,))
        if cursor.fetchall():
            connection.rollback()
            return api_error("This unit is already reserved.")

        cursor.execute("""
            SELECT matching_id
            FROM matching
            WHERE unit_id = %s
              AND matching_status IN ('Proposed', 'Matched')
            FOR UPDATE
        """, (unit_id,))
        if cursor.fetchall():
            connection.rollback()
            return api_error("This unit already has an active matching allocation.")

        cursor.execute("""
            SELECT distribution_id
            FROM distribution
            WHERE unit_id = %s
            FOR UPDATE
        """, (unit_id,))
        if cursor.fetchall():
            connection.rollback()
            return api_error("This unit has already been distributed.")

        cursor.execute("""
            SELECT COALESCE(SUM(m.matched_quantity_ml), 0) AS allocated_ml
            FROM matching m
            WHERE m.request_id = %s
              AND (
                  m.matching_status = 'Proposed'
                  OR (
                      m.matching_status = 'Matched'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM reservation r
                          WHERE r.request_id = m.request_id
                            AND r.unit_id = m.unit_id
                            AND r.reservation_status = 'Reserved'
                      )
                  )
              )
        """, (request_id,))
        matched_ml = cursor.fetchone()["allocated_ml"]

        cursor.execute("""
            SELECT COALESCE(SUM(reserved_quantity_ml), 0) AS reserved_ml
            FROM reservation
            WHERE request_id = %s AND reservation_status = 'Reserved'
        """, (request_id,))
        reserved_ml = cursor.fetchone()["reserved_ml"]

        remaining_ml = (
            hospital_request["quantity_ml"] - matched_ml - reserved_ml
        )

        if remaining_ml <= 0:
            connection.rollback()
            return api_error("No unallocated request quantity remains.")

        if quantity_ml != unit["quantity_ml"]:
            connection.rollback()
            return api_error(
                "A proposed allocation must equal the full blood unit quantity."
            )

        if quantity_ml > remaining_ml:
            connection.rollback()
            return api_error(
                f"Proposed quantity exceeds the remaining request quantity ({remaining_ml} mL)."
            )

        cursor.execute("""
            INSERT INTO matching
                (request_id, unit_id, matched_quantity_ml, matching_status)
            VALUES (%s, %s, %s, 'Proposed')
        """, (request_id, unit_id, quantity_ml))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Proposed match could not be saved. No changes were made.")

        matching_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Proposed match recorded. Stock has not been reserved or distributed.",
            "matching_id": matching_id,
            "request_id": request_id,
            "unit_id": unit_id,
            "matched_quantity_ml": quantity_ml,
            "matching_status": "Proposed"
        }), 201

    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Could not record proposed match")
        return api_error("Could not record proposed match.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/matching-history", methods=["GET"])
def get_matching_history():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                m.matching_id,
                m.request_id,
                m.unit_id,
                m.matched_quantity_ml,
                m.matching_date,
                m.matching_status,
                h.hospital_name,
                bg.blood_group,
                bc.component_name
            FROM matching m
            JOIN hospital_request hr ON m.request_id = hr.request_id
            JOIN hospital h ON hr.hospital_id = h.hospital_id
            JOIN blood_unit bu ON m.unit_id = bu.unit_id
            JOIN blood_group bg ON bu.blood_group_id = bg.blood_group_id
            JOIN blood_component bc ON bu.component_id = bc.component_id
            ORDER BY m.matching_date DESC, m.matching_id DESC
        """)
        matches = cursor.fetchall()

        for match in matches:
            if match.get("matching_date") is not None:
                match["matching_date"] = match["matching_date"].isoformat()

        return jsonify({"success": True, "matches": matches}), 200

    except Exception as error:
        app.logger.exception("Could not retrieve matching history")
        return jsonify({
            "success": False,
            "message": "Could not load matching history."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()




@app.route("/api/matching-approval/<int:matching_id>", methods=["POST"])
def approve_proposed_match(matching_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT matching_id, request_id, unit_id,
                   matched_quantity_ml, matching_status
            FROM matching
            WHERE matching_id = %s
        """, (matching_id,))
        match = cursor.fetchone()

        if not match:
            connection.rollback()
            return api_error("Matching record not found.", 404)

        cursor.execute("""
            SELECT request_id, blood_group_id, component_id,
                   quantity_ml, request_status
            FROM hospital_request
            WHERE request_id = %s
            FOR UPDATE
        """, (match["request_id"],))
        req = cursor.fetchone()

        if not req:
            connection.rollback()
            return api_error("Hospital request not found.", 404)

        cursor.execute("""
            SELECT unit_id, blood_group_id, component_id,
                   quantity_ml, expiry_date, status
            FROM blood_unit
            WHERE unit_id = %s
            FOR UPDATE
        """, (match["unit_id"],))
        unit = cursor.fetchone()

        if not unit:
            connection.rollback()
            return api_error("Blood unit not found.", 404)

        cursor.execute("""
            SELECT reservation_id, request_id, unit_id,
                   reserved_quantity_ml, reservation_status
            FROM reservation
            WHERE unit_id = %s
              AND reservation_status = 'Reserved'
            FOR UPDATE
        """, (unit["unit_id"],))
        active_reservations = cursor.fetchall()

        cursor.execute("""
            SELECT matching_id, request_id, unit_id,
                   matched_quantity_ml, matching_status
            FROM matching
            WHERE matching_id = %s
            FOR UPDATE
        """, (matching_id,))
        match = cursor.fetchone()

        if not match:
            connection.rollback()
            return api_error("Matching record not found.", 404)

        if (match["request_id"] != req["request_id"]
                or match["unit_id"] != unit["unit_id"]):
            connection.rollback()
            return api_error(
                "Matching request or blood unit changed. Please refresh."
            )

        if match["matching_status"] != "Proposed":
            connection.rollback()
            return api_error("Only proposed matches can be approved.")

        if match["matched_quantity_ml"] <= 0:
            connection.rollback()
            return api_error("Proposed quantity must be greater than zero.")

        cursor.execute("""
            SELECT matching_id
            FROM matching
            WHERE unit_id = %s
              AND matching_id <> %s
              AND matching_status IN ('Proposed', 'Matched')
            FOR UPDATE
        """, (unit["unit_id"], matching_id))
        if cursor.fetchall():
            connection.rollback()
            return api_error("Blood unit already has another active matching allocation.")

        if req["request_status"] != "Pending":
            connection.rollback()
            return api_error("Hospital request is not pending.")

        if unit["status"] != "Available":
            connection.rollback()
            return api_error("Blood unit is no longer available.")

        cursor.execute("SELECT CURDATE() AS today")
        today = cursor.fetchone()["today"]

        if unit["expiry_date"] is None or unit["expiry_date"] < today:
            connection.rollback()
            return api_error("Blood unit is expired or has no expiry date.")

        if (unit["blood_group_id"] != req["blood_group_id"]
                or unit["component_id"] != req["component_id"]):
            connection.rollback()
            return api_error("Blood group or component no longer matches.")

        if active_reservations:
            connection.rollback()
            return api_error("Blood unit is already reserved.")

        cursor.execute("""
            SELECT distribution_id
            FROM distribution
            WHERE unit_id = %s
            FOR UPDATE
        """, (unit["unit_id"],))
        if cursor.fetchone():
            connection.rollback()
            return api_error("Blood unit has already been distributed.")

        cursor.execute("""
            SELECT COALESCE(SUM(m.matched_quantity_ml), 0) AS total
            FROM matching m
            WHERE m.request_id = %s
              AND m.matching_id <> %s
              AND (
                  m.matching_status = 'Proposed'
                  OR (
                      m.matching_status = 'Matched'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM reservation r
                          WHERE r.request_id = m.request_id
                            AND r.unit_id = m.unit_id
                            AND r.reservation_status = 'Reserved'
                      )
                  )
              )
        """, (req["request_id"], matching_id))
        other_matches = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COALESCE(SUM(reserved_quantity_ml), 0) AS total
            FROM reservation
            WHERE request_id = %s AND reservation_status = 'Reserved'
        """, (req["request_id"],))
        reserved = cursor.fetchone()["total"]

        remaining = req["quantity_ml"] - other_matches - reserved

        if match["matched_quantity_ml"] != unit["quantity_ml"]:
            connection.rollback()
            return api_error(
                "A proposed allocation must equal the full blood unit quantity."
            )

        if match["matched_quantity_ml"] > remaining:
            connection.rollback()
            return api_error(
                f"Proposed quantity exceeds remaining request quantity ({remaining} mL)."
            )

        cursor.execute("""
            UPDATE matching
            SET matching_status = 'Matched'
            WHERE matching_id = %s AND matching_status = 'Proposed'
        """, (matching_id,))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Matching update failed. No changes were saved.")

        cursor.execute("""
            INSERT INTO reservation
                (request_id, unit_id, reserved_quantity_ml, reservation_status)
            VALUES (%s, %s, %s, 'Reserved')
        """, (
            match["request_id"],
            match["unit_id"],
            match["matched_quantity_ml"]
        ))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Reservation creation failed. No changes were saved.")

        reservation_id = cursor.lastrowid

        cursor.execute("""
            UPDATE blood_unit
            SET status = 'Reserved'
            WHERE unit_id = %s
              AND status = 'Available'
        """, (match["unit_id"],))

        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Blood unit could not be marked as reserved. No changes were saved.")

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Match approved and quantity reserved.",
            "matching_id": matching_id,
            "reservation_id": reservation_id,
            "matching_status": "Matched",
            "reservation_status": "Reserved"
        }), 200

    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Could not approve proposed match")
        return api_error("Could not approve proposed match.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route("/api/matching-candidates/<int:request_id>", methods=["GET"])
def get_matching_candidates(request_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT request_id, blood_group_id, component_id,
                   quantity_ml, request_status
            FROM hospital_request
            WHERE request_id = %s
        """, (request_id,))

        hospital_request = cursor.fetchone()

        if not hospital_request:
            return api_error("Hospital request not found", 404)

        if hospital_request["request_status"] != "Pending":
            return api_error("Request is not pending", 400)

        cursor.execute("""
            SELECT
                bu.unit_id,
                bu.blood_group_id,
                bg.blood_group,
                bu.component_id,
                bc.component_name,
                bu.location_id,
                sl.location_name,
                sl.refrigerator_number,
                sl.shelf_number,
                bu.quantity_ml,
                bu.expiry_date,
                bu.status
            FROM blood_unit bu
            JOIN blood_group bg
                ON bu.blood_group_id = bg.blood_group_id
            JOIN blood_component bc
                ON bu.component_id = bc.component_id
            LEFT JOIN storage_location sl
                ON bu.location_id = sl.location_id
            WHERE bu.status = 'Available'
              AND bu.expiry_date >= CURDATE()
              AND bu.blood_group_id = %s
              AND bu.component_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM matching m
                  WHERE m.unit_id = bu.unit_id
                    AND m.matching_status IN ('Proposed', 'Matched')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM reservation r
                  WHERE r.unit_id = bu.unit_id
                    AND r.reservation_status = 'Reserved'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM distribution d
                  WHERE d.unit_id = bu.unit_id
              )
            ORDER BY bu.expiry_date ASC, bu.unit_id ASC
        """, (
            hospital_request["blood_group_id"],
            hospital_request["component_id"]
        ))

        candidates = cursor.fetchall()

        for unit in candidates:
            if unit.get("expiry_date") is not None:
                unit["expiry_date"] = unit["expiry_date"].isoformat()

        return jsonify({
            "success": True,
            "request_id": request_id,
            "requested_quantity_ml": hospital_request["quantity_ml"],
            "candidate_count": len(candidates),
            "candidates": candidates
        }), 200

    except Exception:
        app.logger.exception("Candidate search failed")
        return api_error("Could not find matching candidates", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/emergency-matching")
def emergency_matching():
    return render_template("matching.html")


@app.route("/hospital-requests")
def hospital_requests():
    return render_template("hospital_requests.html")

@app.route("/api/hospitals", methods=["GET"])
def get_hospitals():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT hospital_id, hospital_name, contact_person,
                   phone, email, address
            FROM hospital
            ORDER BY hospital_id DESC
        """)

        hospitals = cursor.fetchall()

        return jsonify({
            "success": True,
            "hospitals": hospitals
        })

    except Exception:
        app.logger.exception("Unable to load hospitals")
        return api_error("Unable to load hospitals.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/hospitals", methods=["POST"])
def add_hospital():
    connection = None
    cursor = None

    data = request.get_json(silent=True) or {}

    hospital_name = str(data.get("hospital_name") or "").strip()
    contact_person = str(data.get("contact_person") or "").strip()
    phone = str(data.get("phone") or "").strip()
    email = str(data.get("email") or "").strip()
    address = str(data.get("address") or "").strip()

    if not hospital_name or not phone:
        return api_error("Hospital name and phone are required.")

    if len(hospital_name) > 150:
        return api_error("Hospital name must be 150 characters or fewer.")

    if len(contact_person) > 100:
        return api_error("Contact person must be 100 characters or fewer.")

    if len(phone) > 15:
        return api_error("Phone must be 15 characters or fewer.")

    if len(email) > 100:
        return api_error("Email must be 100 characters or fewer.")

    if len(address) > 255:
        return api_error("Address must be 255 characters or fewer.")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO hospital (
                hospital_name, contact_person, phone, email, address
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            hospital_name,
            contact_person or None,
            phone,
            email or None,
            address or None
        ))

        hospital_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Hospital registered successfully.",
            "hospital_id": hospital_id
        }), 201

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to register hospital")
        return api_error("Unable to register hospital.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# HOSPITAL BLOOD REQUESTS
# ==========================================

@app.route("/api/hospital-requests", methods=["POST"])
def add_hospital_request():
    connection = None
    cursor = None
    data = request.get_json(silent=True) or {}

    try:
        hospital_id = int(data.get("hospital_id", ""))
        blood_group_id = int(data.get("blood_group_id", ""))
        component_id = int(data.get("component_id", ""))
        quantity_ml = int(data.get("quantity_ml", ""))
    except (TypeError, ValueError):
        return api_error(
            "Select a hospital, blood group, component, and valid quantity."
        )

    emergency_level = str(
        data.get("emergency_level", "Normal")
    ).strip()

    if min(hospital_id, blood_group_id, component_id) <= 0:
        return api_error("Select valid hospital and blood details.")

    if quantity_ml <= 0:
        return api_error("Quantity must be greater than zero.")

    if emergency_level not in {"Normal", "Urgent", "Critical"}:
        return api_error("Invalid emergency level.")

    required_date = data.get("required_date") or None

    if required_date:
        try:
            required_date = datetime.strptime(
                required_date, "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError):
            return api_error("Enter a valid required date.")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT hospital_id FROM hospital WHERE hospital_id = %s",
            (hospital_id,)
        )
        if not cursor.fetchone():
            return api_error("Hospital not found.", 404)

        cursor.execute(
            "SELECT blood_group_id FROM blood_group WHERE blood_group_id = %s",
            (blood_group_id,)
        )
        if not cursor.fetchone():
            return api_error("Blood group not found.")

        cursor.execute(
            "SELECT component_id FROM blood_component WHERE component_id = %s",
            (component_id,)
        )
        if not cursor.fetchone():
            return api_error("Blood component not found.")

        cursor.execute("""
            INSERT INTO hospital_request (
                hospital_id,
                blood_group_id,
                component_id,
                quantity_ml,
                emergency_level,
                request_status,
                required_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            hospital_id,
            blood_group_id,
            component_id,
            quantity_ml,
            emergency_level,
            "Pending",
            required_date
        ))

        request_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Blood request submitted successfully.",
            "request_id": request_id
        }), 201

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to submit hospital request")
        return api_error("Unable to submit blood request.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/hospital-requests", methods=["GET"])
def get_hospital_requests():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                hr.request_id,
                hr.hospital_id,
                h.hospital_name,
                hr.blood_group_id,
                bg.blood_group,
                hr.component_id,
                bc.component_name,
                hr.quantity_ml,
                hr.emergency_level,
                hr.request_status,
                hr.request_date,
                hr.required_date
            FROM hospital_request hr
            JOIN hospital h
                ON hr.hospital_id = h.hospital_id
            JOIN blood_group bg
                ON hr.blood_group_id = bg.blood_group_id
            JOIN blood_component bc
                ON hr.component_id = bc.component_id
            ORDER BY
                CASE hr.emergency_level
                    WHEN 'Critical' THEN 1
                    WHEN 'Urgent' THEN 2
                    ELSE 3
                END,
                hr.request_id DESC
        """)

        requests_list = cursor.fetchall()

        for item in requests_list:
            for key in ("request_date", "required_date"):
                if item[key] is not None:
                    item[key] = item[key].isoformat()

        return jsonify({
            "success": True,
            "requests": requests_list
        })

    except Exception:
        app.logger.exception("Unable to load hospital requests")
        return api_error("Unable to load hospital requests.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ==========================================
# INVENTORY FORM OPTIONS
# ==========================================

@app.route("/api/inventory-options")
def get_inventory_options():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT d.donor_id, d.name, d.blood_group_id,
                   bg.blood_group
            FROM donor d
            JOIN blood_group bg
                ON d.blood_group_id = bg.blood_group_id
            ORDER BY d.name
        """)
        donors_list = cursor.fetchall()

        cursor.execute("""
            SELECT location_id, location_name,
                   refrigerator_number, shelf_number
            FROM storage_location
            ORDER BY location_id
        """)
        locations = cursor.fetchall()

        return jsonify({
            "success": True,
            "donors": donors_list,
            "locations": locations
        })

    except Exception:
        app.logger.exception("Unable to load inventory options")
        return api_error("Unable to load donors and storage locations.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# BLOOD INVENTORY: LIST
# ==========================================

@app.route("/api/blood-units", methods=["GET"])
def get_blood_units():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                bu.unit_id,
                bu.donation_id,
                dn.donor_id,
                d.name AS donor_name,
                bu.blood_group_id,
                bg.blood_group,
                bu.component_id,
                bc.component_name,
                bu.location_id,
                sl.location_name,
                sl.refrigerator_number,
                sl.shelf_number,
                DATE_FORMAT(
                    bu.collection_date, '%Y-%m-%d'
                ) AS collection_date,
                DATE_FORMAT(
                    bu.expiry_date, '%Y-%m-%d'
                ) AS expiry_date,
                bu.quantity_ml,
                bu.status
            FROM blood_unit bu
            JOIN blood_group bg
                ON bu.blood_group_id = bg.blood_group_id
            JOIN blood_component bc
                ON bu.component_id = bc.component_id
            LEFT JOIN storage_location sl
                ON bu.location_id = sl.location_id
            LEFT JOIN donation dn
                ON bu.donation_id = dn.donation_id
            LEFT JOIN donor d
                ON dn.donor_id = d.donor_id
            ORDER BY bu.unit_id DESC
        """)

        units = cursor.fetchall()

        return jsonify({
            "success": True,
            "blood_units": units
        })

    except Exception:
        app.logger.exception("Unable to retrieve blood inventory")
        return api_error("Unable to load blood inventory.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# VALIDATE INVENTORY FORM DATA
# ==========================================

def validate_blood_unit(data):
    try:
        donor_id = int(data.get("donor_id", ""))
        blood_group_id = int(data.get("blood_group_id", ""))
        component_id = int(data.get("component_id", ""))
        quantity_ml = int(data.get("quantity_ml", ""))

        location_value = data.get("location_id")
        location_id = (
            int(location_value)
            if location_value not in (None, "")
            else None
        )

        collection_date = datetime.strptime(
            str(data.get("collection_date", "")), "%Y-%m-%d"
        ).date()

        expiry_date = datetime.strptime(
            str(data.get("expiry_date", "")), "%Y-%m-%d"
        ).date()

    except (TypeError, ValueError):
        return None, "Enter valid IDs, dates, and a whole-number quantity."

    if min(donor_id, blood_group_id, component_id) <= 0:
        return None, "Select a valid donor, blood group, and component."

    if location_id is not None and location_id <= 0:
        return None, "Select a valid storage location."

    if quantity_ml <= 0:
        return None, "Quantity must be greater than zero."

    if collection_date > date.today():
        return None, "Collection date cannot be in the future."

    if expiry_date <= collection_date:
        return None, "Expiry date must be later than collection date."

    status = str(data.get("status", "Available")).strip()

    if status not in {"Available", "Reserved", "Used", "Expired"}:
        return None, "Select a valid blood unit status."

    return {
        "donor_id": donor_id,
        "blood_group_id": blood_group_id,
        "component_id": component_id,
        "quantity_ml": quantity_ml,
        "location_id": location_id,
        "collection_date": collection_date,
        "expiry_date": expiry_date,
        "status": status
    }, None


# ==========================================
# VALIDATE DONOR AND STORAGE REFERENCES
# ==========================================

def validate_references(cursor, payload):
    cursor.execute("""
        SELECT blood_group_id
        FROM donor
        WHERE donor_id = %s
    """, (payload["donor_id"],))

    donor = cursor.fetchone()

    if not donor:
        return "The selected donor does not exist."

    if donor[0] != payload["blood_group_id"]:
        return "Blood group must match the donor's registered blood group."

    cursor.execute("""
        SELECT component_id
        FROM blood_component
        WHERE component_id = %s
    """, (payload["component_id"],))

    if not cursor.fetchone():
        return "The selected blood component does not exist."

    if payload["location_id"] is not None:
        cursor.execute("""
            SELECT location_id
            FROM storage_location
            WHERE location_id = %s
        """, (payload["location_id"],))

        if not cursor.fetchone():
            return "The selected storage location does not exist."

    return None


# ==========================================
# ADD BLOOD UNIT
# Creates donation and blood unit together
# ==========================================

@app.route("/api/blood-units", methods=["POST"])
def add_blood_unit():
    connection = None
    cursor = None

    data = request.get_json(silent=True) or {}
    payload, error = validate_blood_unit(data)

    if error:
        return api_error(error)

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        reference_error = validate_references(cursor, payload)

        if reference_error:
            return api_error(reference_error)

        # Create a real donation record.
        cursor.execute("""
            INSERT INTO donation (
                donor_id,
                donation_date,
                component_id,
                quantity_ml,
                donation_status
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            payload["donor_id"],
            payload["collection_date"],
            payload["component_id"],
            payload["quantity_ml"],
            "Collected"
        ))

        donation_id = cursor.lastrowid

        # Link the blood unit to that donation.
        cursor.execute("""
            INSERT INTO blood_unit (
                donation_id,
                blood_group_id,
                component_id,
                collection_date,
                expiry_date,
                quantity_ml,
                location_id,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            donation_id,
            payload["blood_group_id"],
            payload["component_id"],
            payload["collection_date"],
            payload["expiry_date"],
            payload["quantity_ml"],
            payload["location_id"],
            payload["status"]
        ))

        unit_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Blood unit saved successfully.",
            "unit_id": unit_id,
            "donation_id": donation_id
        }), 201

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to save blood unit")
        return api_error(
            "Unable to save blood unit. Check the server log for details.",
            500
        )

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# GET ONE BLOOD UNIT
# Used when editing a unit
# ==========================================

@app.route("/api/blood-units/<int:unit_id>", methods=["GET"])
def get_single_blood_unit(unit_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                bu.unit_id,
                bu.donation_id,
                dn.donor_id,
                bu.blood_group_id,
                bu.component_id,
                bu.location_id,
                DATE_FORMAT(
                    bu.collection_date, '%Y-%m-%d'
                ) AS collection_date,
                DATE_FORMAT(
                    bu.expiry_date, '%Y-%m-%d'
                ) AS expiry_date,
                bu.quantity_ml,
                bu.status
            FROM blood_unit bu
            JOIN donation dn
                ON bu.donation_id = dn.donation_id
            WHERE bu.unit_id = %s
        """, (unit_id,))

        unit = cursor.fetchone()

        if not unit:
            return api_error("Blood unit not found.", 404)

        return jsonify({
            "success": True,
            "blood_unit": unit
        })

    except Exception:
        app.logger.exception("Unable to retrieve blood unit")
        return api_error("Unable to retrieve blood unit.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# UPDATE BLOOD UNIT
# ==========================================

@app.route("/api/blood-units/<int:unit_id>", methods=["PUT"])
def update_blood_unit(unit_id):
    connection = None
    cursor = None

    data = request.get_json(silent=True) or {}
    payload, error = validate_blood_unit(data)

    if error:
        return api_error(error)

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT donation_id
            FROM blood_unit
            WHERE unit_id = %s
        """, (unit_id,))

        row = cursor.fetchone()

        if not row:
            return api_error("Blood unit not found.", 404)

        donation_id = row[0]

        reference_error = validate_references(cursor, payload)

        if reference_error:
            return api_error(reference_error)

        # Update the linked donation.
        cursor.execute("""
            UPDATE donation
            SET donor_id = %s,
                donation_date = %s,
                component_id = %s,
                quantity_ml = %s
            WHERE donation_id = %s
        """, (
            payload["donor_id"],
            payload["collection_date"],
            payload["component_id"],
            payload["quantity_ml"],
            donation_id
        ))

        # Update the inventory unit.
        cursor.execute("""
            UPDATE blood_unit
            SET blood_group_id = %s,
                component_id = %s,
                collection_date = %s,
                expiry_date = %s,
                quantity_ml = %s,
                location_id = %s,
                status = %s
            WHERE unit_id = %s
        """, (
            payload["blood_group_id"],
            payload["component_id"],
            payload["collection_date"],
            payload["expiry_date"],
            payload["quantity_ml"],
            payload["location_id"],
            payload["status"],
            unit_id
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Blood unit updated successfully."
        })

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to update blood unit")
        return api_error("Unable to update blood unit.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DELETE BLOOD UNIT
# ==========================================

@app.route("/api/blood-units/<int:unit_id>", methods=["DELETE"])
def delete_blood_unit(unit_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM blood_unit
            WHERE unit_id = %s
        """, (unit_id,))

        if cursor.rowcount == 0:
            connection.rollback()
            return api_error("Blood unit not found.", 404)

        # Keep the donation as historical donor data.
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Blood unit deleted successfully."
        })

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to delete blood unit")
        return api_error(
            "Unable to delete blood unit. It may be referenced by another record.",
            500
        )

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DONORS: LIST
# ==========================================

@app.route("/api/donors", methods=["GET"])
def get_donors():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                d.donor_id,
                d.name,
                d.age,
                d.gender,
                d.phone,
                d.email,
                d.address,
                bg.blood_group,
                d.last_donation_date,
                d.eligibility_status
            FROM donor d
            JOIN blood_group bg
                ON d.blood_group_id = bg.blood_group_id
            ORDER BY d.donor_id DESC
        """)

        donor_list = cursor.fetchall()

        return jsonify({
            "success": True,
            "donors": donor_list
        })

    except Exception:
        app.logger.exception("Unable to retrieve donors")
        return api_error("Unable to load donors.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DONORS: ADD
# ==========================================

@app.route("/api/donors/add", methods=["POST"])
def add_donor():
    connection = None
    cursor = None

    data = request.get_json(silent=True) or {}

    name = data.get("name")
    age = data.get("age")
    gender = data.get("gender")
    blood_group_id = data.get("blood_group_id")
    phone = data.get("phone")
    email = data.get("email")
    address = data.get("address")
    last_donation_date = data.get("last_donation_date") or None
    eligibility_status = data.get("eligibility_status")

    if not name or not age or not blood_group_id or not phone:
        return api_error("Please fill all required fields.")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO donor (
                name, age, gender, phone, email, address,
                blood_group_id, last_donation_date, eligibility_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            name, age, gender, phone, email, address,
            blood_group_id, last_donation_date, eligibility_status
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Donor added successfully."
        })

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to add donor")
        return api_error("Unable to add donor. Check the submitted details.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DONORS: GET ONE
# ==========================================

@app.route("/api/donors/<int:donor_id>", methods=["GET"])
def get_single_donor(donor_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                d.donor_id, d.name, d.age, d.gender,
                d.phone, d.email, d.address,
                d.blood_group_id, bg.blood_group,
                d.last_donation_date, d.eligibility_status
            FROM donor d
            JOIN blood_group bg
                ON d.blood_group_id = bg.blood_group_id
            WHERE d.donor_id = %s
        """, (donor_id,))

        donor = cursor.fetchone()

        if not donor:
            return api_error("Donor not found.", 404)

        return jsonify({
            "success": True,
            "donor": donor
        })

    except Exception:
        app.logger.exception("Unable to retrieve donor")
        return api_error("Unable to retrieve donor.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DONORS: UPDATE
# ==========================================

@app.route("/api/donors/<int:donor_id>", methods=["PUT"])
def update_donor(donor_id):
    connection = None
    cursor = None

    data = request.get_json(silent=True) or {}

    name = data.get("name")
    age = data.get("age")
    gender = data.get("gender")
    blood_group_id = data.get("blood_group_id")
    phone = data.get("phone")
    email = data.get("email")
    address = data.get("address")
    last_donation_date = data.get("last_donation_date") or None
    eligibility_status = data.get("eligibility_status")

    if not name or not age or not blood_group_id or not phone:
        return api_error("Please fill all required fields.")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE donor
            SET name = %s,
                age = %s,
                gender = %s,
                phone = %s,
                email = %s,
                address = %s,
                blood_group_id = %s,
                last_donation_date = %s,
                eligibility_status = %s
            WHERE donor_id = %s
        """, (
            name, age, gender, phone, email, address,
            blood_group_id, last_donation_date,
            eligibility_status, donor_id
        ))

        if cursor.rowcount == 0:
            connection.rollback()
            return api_error("Donor not found or no changes were made.", 404)

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Donor updated successfully."
        })

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to update donor")
        return api_error("Unable to update donor.", 500)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# DONORS: DELETE
# ==========================================

@app.route("/api/donors/<int:donor_id>", methods=["DELETE"])
def delete_donor(donor_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM donor
            WHERE donor_id = %s
        """, (donor_id,))

        if cursor.rowcount == 0:
            connection.rollback()
            return api_error("Donor not found.", 404)

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Donor deleted successfully."
        })

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Unable to delete donor")
        return api_error(
            "Unable to delete donor. This donor may be referenced by donations.",
            500
        )

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# START FLASK
# ==========================================


# ==========================================
# BLOOD DISTRIBUTION
# ==========================================

@app.route("/distribution")
def distribution_page():
    return render_template("distribution.html")


@app.route("/api/distributions", methods=["GET"])
def get_distributions():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.distribution_id, d.request_id, d.unit_id,
                   d.hospital_id, d.distributed_quantity_ml,
                   d.distribution_date, d.received_by,
                   h.hospital_name, bg.blood_group, bc.component_name
            FROM distribution d
            JOIN hospital h ON h.hospital_id = d.hospital_id
            JOIN hospital_request hr ON hr.request_id = d.request_id
            JOIN blood_group bg ON bg.blood_group_id = hr.blood_group_id
            JOIN blood_component bc ON bc.component_id = hr.component_id
            ORDER BY d.distribution_date DESC, d.distribution_id DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row.get("distribution_date"):
                row["distribution_date"] = row["distribution_date"].strftime("%Y-%m-%d %H:%M")
        return jsonify({"success": True, "distributions": rows, "total": len(rows)})
    except Exception:
        app.logger.exception("Unable to load distribution history")
        return api_error("Unable to load distribution history.", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/distributions/eligible", methods=["GET"])
def get_distribution_eligible_reservations():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.reservation_id, r.request_id, r.unit_id,
                   r.reserved_quantity_ml, r.reservation_status,
                   hr.hospital_id, h.hospital_name, bg.blood_group,
                   bc.component_name, bu.status AS unit_status,
                   bu.expiry_date,
                   COALESCE((
                       SELECT SUM(d.distributed_quantity_ml)
                       FROM distribution d
                       WHERE d.request_id = r.request_id
                         AND d.unit_id = r.unit_id
                   ), 0) AS already_distributed_ml
            FROM reservation r
            JOIN hospital_request hr ON hr.request_id = r.request_id
            JOIN hospital h ON h.hospital_id = hr.hospital_id
            JOIN blood_group bg ON bg.blood_group_id = hr.blood_group_id
            JOIN blood_component bc ON bc.component_id = hr.component_id
            JOIN blood_unit bu ON bu.unit_id = r.unit_id
            WHERE r.reservation_status = 'Reserved'
            ORDER BY r.reservation_date, r.reservation_id
        """)
        rows = cursor.fetchall()
        for row in rows:
            row["remaining_reserved_ml"] = (
                row["reserved_quantity_ml"] - row["already_distributed_ml"]
            )
            if row.get("expiry_date"):
                row["expiry_date"] = row["expiry_date"].isoformat()
        return jsonify({"success": True, "reservations": rows})
    except Exception:
        app.logger.exception("Unable to load eligible reservations")
        return api_error("Unable to load eligible reservations.", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/distributions", methods=["POST"])
def create_distribution():
    connection = None
    cursor = None
    try:
        data = request.get_json(silent=True) or {}
        try:
            reservation_id = int(data.get("reservation_id"))
            quantity_ml = int(data.get("distributed_quantity_ml"))
        except (TypeError, ValueError):
            return api_error("Reservation and positive quantity are required.")

        received_by = str(data.get("received_by", "")).strip()
        if quantity_ml <= 0:
            return api_error("Distribution quantity must be greater than zero.")
        if not received_by or len(received_by) > 100:
            return api_error("Enter the recipient's name (maximum 100 characters).")

        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT reservation_id, request_id, unit_id,
                   reserved_quantity_ml, reservation_status
            FROM reservation
            WHERE reservation_id = %s
        """, (reservation_id,))
        res = cursor.fetchone()
        if not res:
            connection.rollback()
            return api_error("Reservation not found.", 404)

        initial_request_id = res["request_id"]
        initial_unit_id = res["unit_id"]

        cursor.execute("""
            SELECT request_id, hospital_id, blood_group_id, component_id,
                   request_status, required_date
            FROM hospital_request
            WHERE request_id = %s
            FOR UPDATE
        """, (initial_request_id,))
        req = cursor.fetchone()
        if not req:
            connection.rollback()
            return api_error("Hospital request not found.", 404)

        cursor.execute("""
            SELECT unit_id, quantity_ml, blood_group_id, component_id,
                   expiry_date, status
            FROM blood_unit
            WHERE unit_id = %s
            FOR UPDATE
        """, (initial_unit_id,))
        unit = cursor.fetchone()
        if not unit:
            connection.rollback()
            return api_error("Blood unit not found.", 404)
        if unit["status"] != "Reserved":
            connection.rollback()
            return api_error("Blood unit is not currently reserved.")

        cursor.execute("""
            SELECT reservation_id, request_id, unit_id,
                   reserved_quantity_ml, reservation_status
            FROM reservation
            WHERE reservation_id = %s
            FOR UPDATE
        """, (reservation_id,))
        res = cursor.fetchone()
        if not res:
            connection.rollback()
            return api_error("Reservation not found.", 404)
        if (res["request_id"] != initial_request_id
                or res["unit_id"] != initial_unit_id):
            connection.rollback()
            return api_error(
                "Reservation request or blood unit changed. Please refresh."
            )
        if res["reservation_status"] != "Reserved":
            connection.rollback()
            return api_error("Only active reservations can be distributed.")

        cursor.execute("""
            SELECT matching_id, request_id, unit_id,
                   matched_quantity_ml, matching_status
            FROM matching
            WHERE request_id = %s
              AND unit_id = %s
              AND matching_status = 'Matched'
            FOR UPDATE
        """, (res["request_id"], res["unit_id"]))
        matches = cursor.fetchall()
        if len(matches) != 1:
            connection.rollback()
            return api_error(
                "Could not safely identify exactly one matching record for this reservation.",
                404
            )
        match = matches[0]
        if match["matching_status"] != "Matched":
            connection.rollback()
            return api_error("Only matched allocations can be distributed.")
        if res["reserved_quantity_ml"] != match["matched_quantity_ml"]:
            connection.rollback()
            return api_error(
                "Reservation and matching quantities differ. No changes were made."
            )

        cursor.execute("SELECT CURDATE() AS today")
        today = cursor.fetchone()["today"]
        if req["request_status"] != "Pending":
            connection.rollback()
            return api_error("The hospital request is not pending.")
        if unit["expiry_date"] is None or unit["expiry_date"] < today:
            connection.rollback()
            return api_error("Expired or undated blood cannot be distributed.")
        if (unit["blood_group_id"] != req["blood_group_id"]
                or unit["component_id"] != req["component_id"]):
            connection.rollback()
            return api_error("Blood group or component does not match the request.")

        cursor.execute("""
            SELECT distribution_id, request_id, distributed_quantity_ml
            FROM distribution
            WHERE unit_id = %s
            FOR UPDATE
        """, (res["unit_id"],))
        distribution_rows = cursor.fetchall()
        already_distributed = sum(
            row["distributed_quantity_ml"]
            for row in distribution_rows
            if row["request_id"] == res["request_id"]
        )
        unit_distributed = sum(
            row["distributed_quantity_ml"]
            for row in distribution_rows
        )
        remaining_reserved = res["reserved_quantity_ml"] - already_distributed
        remaining_unit_quantity = unit["quantity_ml"] - unit_distributed
        if quantity_ml > remaining_reserved:
            connection.rollback()
            return api_error(
                f"Quantity exceeds remaining reserved amount ({remaining_reserved} ml)."
            )
        if quantity_ml > remaining_unit_quantity:
            connection.rollback()
            return api_error(
                f"Quantity exceeds the blood unit's remaining quantity ({remaining_unit_quantity} ml)."
            )

        cursor.execute("""
            INSERT INTO distribution
                (request_id, unit_id, hospital_id,
                 distributed_quantity_ml, received_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            res["request_id"], res["unit_id"], req["hospital_id"],
            quantity_ml, received_by
        ))
        if cursor.rowcount != 1:
            connection.rollback()
            return api_error("Distribution could not be recorded. No changes were saved.")
        distribution_id = cursor.lastrowid

        # Keep partially distributed units reserved; mark fully distributed units.
        if quantity_ml == remaining_reserved:
            cursor.execute("""
                UPDATE blood_unit
                SET status = 'Distributed'
                WHERE unit_id = %s AND status = 'Reserved'
            """, (res["unit_id"],))
            if cursor.rowcount != 1:
                connection.rollback()
                return api_error(
                    "Blood unit status could not be updated. No changes were saved."
                )

            cursor.execute("""
                UPDATE reservation
                SET reservation_status = 'Distributed'
                WHERE reservation_id = %s AND reservation_status = 'Reserved'
            """, (reservation_id,))
            if cursor.rowcount != 1:
                connection.rollback()
                return api_error("Reservation status changed. No changes were saved.")

            cursor.execute("""
                UPDATE matching
                SET matching_status = 'Distributed'
                WHERE request_id = %s AND unit_id = %s
                  AND matching_status = 'Matched'
            """, (res["request_id"], res["unit_id"]))
            if cursor.rowcount != 1:
                connection.rollback()
                return api_error("Matching status changed. No changes were saved.")

        connection.commit()
        return jsonify({
            "success": True,
            "message": "Distribution recorded successfully.",
            "distribution_id": distribution_id,
            "reservation_id": reservation_id,
            "distributed_quantity_ml": quantity_ml
        }), 201
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Unable to record distribution")
        return api_error("Unable to record distribution.", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    app.run(debug=True)

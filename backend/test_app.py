import sys
import os
import time
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def request(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, data=body, timeout=5) as response:
            status_code = response.getcode()
            resp_body = response.read().decode("utf-8")
            try:
                return status_code, json.loads(resp_body)
            except Exception:
                return status_code, resp_body
    except urllib.error.HTTPError as e:
        status_code = e.code
        err_body = e.read().decode("utf-8")
        try:
            return status_code, json.loads(err_body)
        except Exception:
            return status_code, err_body

def run_tests():
    print("=" * 60)
    print("FASTAPI + DUCKDB LIVE SERVER TEST")
    print("=" * 60)

    # 1. Metadata check
    status, meta = request("/api/tables-meta")
    assert status == 200, f"Expected 200, got {status}: {meta}"
    tables = meta["tables"]
    print(f"Metadata verified: {len(tables)} tables loaded")
    assert len(tables) == 13

    # 2. Lookups check
    status, lookups = request("/api/lookups")
    assert status == 200, f"Expected 200, got {status}: {lookups}"
    print("Lookups loaded:", {k: len(v) for k, v in lookups.items()})

    # 3. All 13 tables records verification
    print("\nVerifying all 13 tables via REST API:")
    total = 0
    for tbl in tables.keys():
        status, data = request(f"/api/{tbl}")
        assert status == 200, f"Failed {tbl}: {status} {data}"
        cnt = data["count"]
        total += cnt
        print(f"  • {tbl:<20}: {cnt:>2} records")
    assert total == 115, f"Expected 115 records, got {total}"

    # 4. Student 1001 details & academic performance
    status, st = request("/api/STUDENT/1001")
    assert status == 200, f"Failed getting student 1001: {st}"
    print(f"\nStudent 1001: {st['student_name']} | Academic Performance: {st['academic_performance']}")

    # 5. Full CRUD Cycle on DEPARTMENT
    print("\nTesting CRUD operations on DEPARTMENT...")
    # CREATE
    status, created = request("/api/DEPARTMENT", method="POST", data={
        "dept_id": 999,
        "dept_name": "Artificial Intelligence",
        "hod_name": "Dr. Alan Turing"
    })
    assert status == 201, f"Failed POST: {status} {created}"
    print("  -> POST /api/DEPARTMENT [201 Created]")

    # READ
    status, dept = request("/api/DEPARTMENT/999")
    assert status == 200, f"Failed GET: {status} {dept}"
    assert dept["dept_name"] == "Artificial Intelligence"
    print("  -> GET /api/DEPARTMENT/999 [200 OK]")

    # UPDATE
    status, updated = request("/api/DEPARTMENT/999", method="PUT", data={
        "dept_name": "AI & Robotics",
        "hod_name": "Dr. Alan M. Turing"
    })
    assert status == 200, f"Failed PUT: {status} {updated}"
    assert updated["record"]["dept_name"] == "AI & Robotics"
    print("  -> PUT /api/DEPARTMENT/999 [200 OK]")

    # DELETE
    status, deleted = request("/api/DEPARTMENT/999", method="DELETE")
    assert status == 200, f"Failed DELETE: {status} {deleted}"
    print("  -> DELETE /api/DEPARTMENT/999 [200 OK]")

    # Verify 404
    status, res_404 = request("/api/DEPARTMENT/999")
    assert status == 404, f"Expected 404, got {status}"
    print("  -> Confirmed 404 Not Found after deletion")

    # 6. Constraint Tests
    print("\nTesting Database Constraint Validations:")
    # Duplicate Primary Key
    status, dup_err = request("/api/DEPARTMENT", method="POST", data={
        "dept_id": 1,
        "dept_name": "Duplicate Department",
        "hod_name": "Dr. None"
    })
    assert status == 400, f"Expected 400 for duplicate PK, got {status}"
    print(f"  -> Duplicate PK caught properly [400 Bad Request]: {dup_err.get('detail', '')[:60]}...")

    # Check Constraint Violation
    status, chk_err = request("/api/STUDENT", method="POST", data={
        "student_id": 9999,
        "student_name": "Invalid Gender",
        "gender": "Unknown",
        "program_id": 101,
        "dept_id": 1
    })
    assert status == 400, f"Expected 400 for check constraint, got {status}"
    print(f"  -> Check constraint caught properly [400 Bad Request]: {chk_err.get('detail', '')[:60]}...")

    # Foreign Key Constraint Violation
    status, fk_err = request("/api/PROGRAM", method="POST", data={
        "program_id": 9999,
        "program_name": "Ghost Program",
        "program_level": "UG",
        "dept_id": 99999,
        "duration_years": 4
    })
    assert status == 400, f"Expected 400 for invalid FK, got {status}"
    print(f"  -> Foreign key constraint caught properly [400 Bad Request]: {fk_err.get('detail', '')[:60]}...")

    # 7. Frontend Static Assets
    print("\nVerifying Frontend Delivery:")
    status, html = request("/")
    assert status == 200
    assert "ABC University" in html
    print("  -> index.html served at root '/' [200 OK]")

    status, css = request("/static/css/style.css")
    assert status == 200
    print("  -> style.css served at '/static/css/style.css' [200 OK]")

    status, js = request("/static/js/app.js")
    assert status == 200
    print("  -> app.js served at '/static/js/app.js' [200 OK]")

    print("\n" + "=" * 60)
    print("ALL API AND DATABASE INTEGRATION TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

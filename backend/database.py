import os
import threading
import duckdb
from decimal import Decimal
from datetime import date, datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "university.duckdb")
SCHEMA_SQL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql", "schema.sql")
SEED_SQL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql", "seed.sql")

db_lock = threading.Lock()

# Table definitions and column metadata
TABLES_META = {
    "DEPARTMENT": {
        "pk": "dept_id",
        "columns": [
            {"name": "dept_id", "type": "int", "required": True, "label": "Department ID"},
            {"name": "dept_name", "type": "str", "required": True, "label": "Department Name"},
            {"name": "hod_name", "type": "str", "required": False, "label": "HOD Name"}
        ]
    },
    "PROGRAM": {
        "pk": "program_id",
        "columns": [
            {"name": "program_id", "type": "int", "required": True, "label": "Program ID"},
            {"name": "program_name", "type": "str", "required": True, "label": "Program Name"},
            {"name": "program_level", "type": "enum", "choices": ["UG", "PG", "PhD"], "required": False, "label": "Program Level"},
            {"name": "dept_id", "type": "int", "required": True, "fk": "DEPARTMENT.dept_id", "label": "Department"},
            {"name": "duration_years", "type": "int", "required": True, "label": "Duration (Years)"}
        ]
    },
    "STUDENT": {
        "pk": "student_id",
        "columns": [
            {"name": "student_id", "type": "int", "required": True, "label": "Student ID"},
            {"name": "student_name", "type": "str", "required": True, "label": "Student Name"},
            {"name": "dob", "type": "date", "required": False, "label": "Date of Birth"},
            {"name": "gender", "type": "enum", "choices": ["Male", "Female", "Other"], "required": False, "label": "Gender"},
            {"name": "contact_number", "type": "str", "required": False, "label": "Contact Number"},
            {"name": "email", "type": "str", "required": False, "label": "Email"},
            {"name": "year_of_study", "type": "int", "min": 1, "max": 5, "required": False, "label": "Year of Study"},
            {"name": "program_id", "type": "int", "required": True, "fk": "PROGRAM.program_id", "label": "Program"},
            {"name": "dept_id", "type": "int", "required": True, "fk": "DEPARTMENT.dept_id", "label": "Department"},
            {"name": "academic_performance", "type": "decimal", "required": False, "readonly": True, "label": "Academic Performance (Avg Marks)"}
        ]
    },
    "FACULTY": {
        "pk": "faculty_id",
        "columns": [
            {"name": "faculty_id", "type": "int", "required": True, "label": "Faculty ID"},
            {"name": "faculty_name", "type": "str", "required": True, "label": "Faculty Name"},
            {"name": "dept_id", "type": "int", "required": True, "fk": "DEPARTMENT.dept_id", "label": "Department"},
            {"name": "faculty_type", "type": "enum", "choices": ["Permanent", "Adjunct", "Visiting"], "required": False, "label": "Faculty Type"},
            {"name": "designation", "type": "str", "required": False, "label": "Designation"},
            {"name": "contact_number", "type": "str", "required": False, "label": "Contact Number"},
            {"name": "email", "type": "str", "required": False, "label": "Email"}
        ]
    },
    "COURSE": {
        "pk": "course_id",
        "columns": [
            {"name": "course_id", "type": "int", "required": True, "label": "Course ID"},
            {"name": "course_name", "type": "str", "required": True, "label": "Course Name"},
            {"name": "credits", "type": "int", "required": True, "label": "Credits"},
            {"name": "semester", "type": "int", "required": True, "label": "Semester"},
            {"name": "dept_id", "type": "int", "required": True, "fk": "DEPARTMENT.dept_id", "label": "Department"},
            {"name": "faculty_id", "type": "int", "required": False, "fk": "FACULTY.faculty_id", "label": "Faculty"}
        ]
    },
    "ENROLLMENT": {
        "pk": "enrollment_id",
        "columns": [
            {"name": "enrollment_id", "type": "int", "required": True, "label": "Enrollment ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "course_id", "type": "int", "required": True, "fk": "COURSE.course_id", "label": "Course"},
            {"name": "semester", "type": "int", "required": True, "label": "Semester"},
            {"name": "academic_year", "type": "str", "required": True, "label": "Academic Year (e.g. 2025-2026)"}
        ]
    },
    "ASSESSMENT": {
        "pk": "assessment_id",
        "columns": [
            {"name": "assessment_id", "type": "int", "required": True, "label": "Assessment ID"},
            {"name": "course_id", "type": "int", "required": True, "fk": "COURSE.course_id", "label": "Course"},
            {"name": "assessment_type", "type": "enum", "choices": ["Assignment", "Quiz", "Lab", "Mid-Semester", "End-Semester"], "required": False, "label": "Assessment Type"},
            {"name": "max_marks", "type": "int", "required": True, "label": "Max Marks"}
        ]
    },
    "EXAMINATION_RESULT": {
        "pk": "result_id",
        "columns": [
            {"name": "result_id", "type": "int", "required": True, "label": "Result ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "course_id", "type": "int", "required": True, "fk": "COURSE.course_id", "label": "Course"},
            {"name": "assessment_id", "type": "int", "required": True, "fk": "ASSESSMENT.assessment_id", "label": "Assessment"},
            {"name": "marks_obtained", "type": "decimal", "required": True, "label": "Marks Obtained"},
            {"name": "result_status", "type": "enum", "choices": ["Pass", "Fail"], "required": False, "label": "Result Status"}
        ]
    },
    "ATTENDANCE": {
        "pk": "attendance_id",
        "columns": [
            {"name": "attendance_id", "type": "int", "required": True, "label": "Attendance ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "course_id", "type": "int", "required": True, "fk": "COURSE.course_id", "label": "Course"},
            {"name": "classes_held", "type": "int", "required": True, "label": "Classes Held"},
            {"name": "classes_attended", "type": "int", "required": True, "label": "Classes Attended"},
            {"name": "attendance_percentage", "type": "decimal", "required": False, "label": "Attendance %"}
        ]
    },
    "SCHOLARSHIP": {
        "pk": "scholarship_id",
        "columns": [
            {"name": "scholarship_id", "type": "int", "required": True, "label": "Scholarship ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "scholarship_name", "type": "str", "required": True, "label": "Scholarship Name"},
            {"name": "amount", "type": "decimal", "required": False, "label": "Amount"},
            {"name": "eligibility_criteria", "type": "str", "required": False, "label": "Eligibility Criteria"},
            {"name": "status", "type": "enum", "choices": ["Active", "Inactive", "Pending"], "required": False, "label": "Status"}
        ]
    },
    "HOSTEL": {
        "pk": "hostel_id",
        "columns": [
            {"name": "hostel_id", "type": "int", "required": True, "label": "Hostel ID"},
            {"name": "hostel_name", "type": "str", "required": True, "label": "Hostel Name"},
            {"name": "room_no", "type": "str", "required": True, "label": "Room No"},
            {"name": "student_id", "type": "int", "required": False, "fk": "STUDENT.student_id", "label": "Student (Resident)"}
        ]
    },
    "INTERNSHIP": {
        "pk": "internship_id",
        "columns": [
            {"name": "internship_id", "type": "int", "required": True, "label": "Internship ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "company_name", "type": "str", "required": True, "label": "Company Name"},
            {"name": "duration_weeks", "type": "int", "required": False, "label": "Duration (Weeks)"},
            {"name": "start_date", "type": "date", "required": False, "label": "Start Date"},
            {"name": "end_date", "type": "date", "required": False, "label": "End Date"}
        ]
    },
    "RESEARCH_PROJECT": {
        "pk": "project_id",
        "columns": [
            {"name": "project_id", "type": "int", "required": True, "label": "Project ID"},
            {"name": "student_id", "type": "int", "required": True, "fk": "STUDENT.student_id", "label": "Student"},
            {"name": "faculty_id", "type": "int", "required": True, "fk": "FACULTY.faculty_id", "label": "Faculty (Supervisor)"},
            {"name": "project_title", "type": "str", "required": True, "label": "Project Title"},
            {"name": "start_date", "type": "date", "required": False, "label": "Start Date"},
            {"name": "end_date", "type": "date", "required": False, "label": "End Date"},
            {"name": "status", "type": "enum", "choices": ["Ongoing", "Completed"], "required": False, "label": "Status"}
        ]
    }
}

def get_connection():
    return duckdb.connect(DB_FILE)

def serialize_row(desc, row):
    res = {}
    for i, col in enumerate(desc):
        col_name = col[0]
        val = row[i]
        if isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, (date, datetime)):
            val = val.isoformat()
        res[col_name] = val
    return res

def init_database():
    """Initializes tables from sql/schema.sql and seeds initial data from sql/seed.sql if empty."""
    with db_lock:
        con = get_connection()
        try:
            # 1. Execute schema.sql to ensure all 13 tables exist
            if os.path.exists(SCHEMA_SQL):
                with open(SCHEMA_SQL, "r", encoding="utf-8") as f:
                    schema_content = f.read()
                # Split and execute individual statements
                statements = [s.strip() for s in schema_content.split(";") if s.strip()]
                for stmt in statements:
                    con.execute(stmt)

            # 2. Check if DEPARTMENT table already contains sample data
            table_check = con.execute("SELECT count(*) FROM DEPARTMENT").fetchone()[0]
            if table_check == 0:
                # Seed data from sql/seed.sql
                print("Seeding database with sample records...")
                if os.path.exists(SEED_SQL):
                    with open(SEED_SQL, "r", encoding="utf-8") as f:
                        seed_content = f.read()
                    seed_stmts = [s.strip() for s in seed_content.split(";") if s.strip()]
                    for stmt in seed_stmts:
                        # Skip pure comment statements
                        lines = [l for l in stmt.split("\n") if not l.strip().startswith("--")]
                        clean_stmt = "\n".join(lines).strip()
                        if clean_stmt:
                            con.execute(clean_stmt)
                # Recalculate academic performance
                update_academic_performance_internal(con)
                print("Sample records successfully seeded and academic performance computed!")
            else:
                print(f"Database already populated ({table_check} departments found). Skipping re-seed.")
        finally:
            con.close()

def update_academic_performance_internal(con):
    """Executes the exact academic performance update query adapted to DuckDB."""
    query = """
    UPDATE STUDENT
    SET academic_performance = COALESCE(
        (SELECT ROUND(AVG(er.marks_obtained), 2) FROM EXAMINATION_RESULT er WHERE er.student_id = STUDENT.student_id), 0
    )
    """
    con.execute(query)

def update_academic_performance():
    with db_lock:
        con = get_connection()
        try:
            update_academic_performance_internal(con)
        finally:
            con.close()

def get_all_records(table_name: str):
    table_name = table_name.upper()
    if table_name not in TABLES_META:
        raise ValueError(f"Unknown table: {table_name}")
    pk = TABLES_META[table_name]["pk"]
    with db_lock:
        con = get_connection()
        try:
            cursor = con.execute(f"SELECT * FROM {table_name} ORDER BY {pk}")
            desc = cursor.description
            rows = cursor.fetchall()
            return [serialize_row(desc, row) for row in rows]
        finally:
            con.close()

def get_record_by_id(table_name: str, record_id: int):
    table_name = table_name.upper()
    if table_name not in TABLES_META:
        raise ValueError(f"Unknown table: {table_name}")
    pk = TABLES_META[table_name]["pk"]
    with db_lock:
        con = get_connection()
        try:
            cursor = con.execute(f"SELECT * FROM {table_name} WHERE {pk} = ?", [record_id])
            desc = cursor.description
            row = cursor.fetchone()
            if not row:
                return None
            return serialize_row(desc, row)
        finally:
            con.close()

def insert_record(table_name: str, data: dict):
    table_name = table_name.upper()
    if table_name not in TABLES_META:
        raise ValueError(f"Unknown table: {table_name}")
    
    meta = TABLES_META[table_name]
    cols_meta = meta["columns"]
    
    # Auto-calculate attendance percentage if not supplied or calculated
    if table_name == "ATTENDANCE":
        classes_held = int(data.get("classes_held") or 0)
        classes_attended = int(data.get("classes_attended") or 0)
        if "attendance_percentage" not in data or data["attendance_percentage"] is None:
            if classes_held > 0:
                data["attendance_percentage"] = round((classes_attended / classes_held) * 100, 2)
            else:
                data["attendance_percentage"] = 0.0

    cols_to_insert = []
    placeholders = []
    values = []

    for col in cols_meta:
        col_name = col["name"]
        if col_name in data and data[col_name] is not None:
            val = data[col_name]
            # Convert empty string to None
            if isinstance(val, str) and val.strip() == "":
                if col.get("required"):
                    raise ValueError(f"Field '{col_name}' is required.")
                val = None
            
            if val is not None:
                # Type conversions
                if col["type"] == "int":
                    val = int(val)
                elif col["type"] == "decimal":
                    val = float(val)
                cols_to_insert.append(col_name)
                placeholders.append("?")
                values.append(val)
        elif col.get("required") and not col.get("readonly"):
            raise ValueError(f"Field '{col_name}' is required.")

    if not cols_to_insert:
        raise ValueError("No valid fields provided for insertion.")

    sql = f"INSERT INTO {table_name} ({', '.join(cols_to_insert)}) VALUES ({', '.join(placeholders)})"

    with db_lock:
        con = get_connection()
        try:
            con.execute(sql, values)
            if table_name == "EXAMINATION_RESULT":
                update_academic_performance_internal(con)
        finally:
            con.close()

    pk_val = data.get(meta["pk"])
    return get_record_by_id(table_name, pk_val)

def update_record(table_name: str, record_id: int, data: dict):
    table_name = table_name.upper()
    if table_name not in TABLES_META:
        raise ValueError(f"Unknown table: {table_name}")

    meta = TABLES_META[table_name]
    pk = meta["pk"]
    cols_meta = meta["columns"]

    # Auto-calculate attendance percentage
    if table_name == "ATTENDANCE":
        if "classes_held" in data and "classes_attended" in data:
            classes_held = int(data.get("classes_held") or 0)
            classes_attended = int(data.get("classes_attended") or 0)
            if classes_held > 0:
                data["attendance_percentage"] = round((classes_attended / classes_held) * 100, 2)
            else:
                data["attendance_percentage"] = 0.0

    set_clauses = []
    values = []

    for col in cols_meta:
        col_name = col["name"]
        if col_name == pk or col.get("readonly"):
            continue
        if col_name in data:
            val = data[col_name]
            if isinstance(val, str) and val.strip() == "":
                if col.get("required"):
                    raise ValueError(f"Field '{col_name}' is required.")
                val = None
            if val is not None:
                if col["type"] == "int":
                    val = int(val)
                elif col["type"] == "decimal":
                    val = float(val)
            set_clauses.append(f"{col_name} = ?")
            values.append(val)

    if not set_clauses:
        raise ValueError("No fields provided to update.")

    values.append(record_id)
    sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {pk} = ?"

    with db_lock:
        con = get_connection()
        try:
            con.execute(sql, values)
            if table_name == "EXAMINATION_RESULT":
                update_academic_performance_internal(con)
        finally:
            con.close()

    return get_record_by_id(table_name, record_id)

def delete_record(table_name: str, record_id: int):
    table_name = table_name.upper()
    if table_name not in TABLES_META:
        raise ValueError(f"Unknown table: {table_name}")
    pk = TABLES_META[table_name]["pk"]

    with db_lock:
        con = get_connection()
        try:
            con.execute(f"DELETE FROM {table_name} WHERE {pk} = ?", [record_id])
            if table_name == "EXAMINATION_RESULT":
                update_academic_performance_internal(con)
        finally:
            con.close()
    return True

def get_foreign_key_lookups():
    """Returns key-value pairs of foreign entities for UI dropdowns."""
    with db_lock:
        con = get_connection()
        try:
            departments = con.execute("SELECT dept_id, dept_name FROM DEPARTMENT ORDER BY dept_id").fetchall()
            programs = con.execute("SELECT program_id, program_name, dept_id FROM PROGRAM ORDER BY program_id").fetchall()
            students = con.execute("SELECT student_id, student_name, dept_id FROM STUDENT ORDER BY student_id").fetchall()
            faculty = con.execute("SELECT faculty_id, faculty_name, dept_id FROM FACULTY ORDER BY faculty_id").fetchall()
            courses = con.execute("SELECT course_id, course_name, dept_id FROM COURSE ORDER BY course_id").fetchall()
            assessments = con.execute("SELECT assessment_id, course_id, assessment_type, max_marks FROM ASSESSMENT ORDER BY assessment_id").fetchall()

            return {
                "departments": [{"id": d[0], "label": f"{d[0]} - {d[1]}"} for d in departments],
                "programs": [{"id": p[0], "label": f"{p[0]} - {p[1]}"} for p in programs],
                "students": [{"id": s[0], "label": f"{s[0]} - {s[1]}"} for s in students],
                "faculty": [{"id": f[0], "label": f"{f[0]} - {f[1]}"} for f in faculty],
                "courses": [{"id": c[0], "label": f"{c[0]} - {c[1]}"} for c in courses],
                "assessments": [{"id": a[0], "label": f"{a[0]} - Course {a[1]} ({a[2]}, Max: {a[3]})"} for a in assessments]
            }
        finally:
            con.close()

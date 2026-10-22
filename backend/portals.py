import math
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from database import (
    get_connection,
    db_lock,
    serialize_row,
    update_academic_performance_internal
)
from auth import (
    require_role,
    hash_password,
    log_audit
)

student_router = APIRouter(prefix="/api/student", tags=["student"])
faculty_router = APIRouter(prefix="/api/faculty", tags=["faculty"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# Helper Functions
# ============================================================================

def _fetchall(con, query: str, params: list = None) -> list:
    cur = con.execute(query, params or [])
    desc = cur.description
    return [serialize_row(desc, row) for row in cur.fetchall()]


def _fetchone(con, query: str, params: list = None) -> Optional[dict]:
    cur = con.execute(query, params or [])
    row = cur.fetchone()
    if not row:
        return None
    return serialize_row(cur.description, row)


def _verify_faculty_course(con, faculty_id: int, course_id: int):
    """Enforces that the faculty member is strictly assigned to this course."""
    row = con.execute("SELECT faculty_id, course_name FROM COURSE WHERE course_id = ?", [course_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found.")
    assigned_fac, course_name = row[0], row[1]
    if assigned_fac != faculty_id:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: You are not authorized to view or edit '{course_name}' (assigned to faculty ID {assigned_fac})."
        )
    return course_name


# ============================================================================
# STUDENT PORTAL APIS (Strictly own data from session ref_id)
# ============================================================================

@student_router.get("/me/overview")
async def get_student_overview(current_user: dict = Depends(require_role("student"))):
    student_id = current_user.get("ref_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="Student profile not linked to session.")

    with db_lock:
        con = get_connection()
        try:
            # 1. Profile information
            profile_query = """
            SELECT s.student_id, s.student_name, s.dob, s.gender, s.contact_number, s.email,
                   s.year_of_study, s.academic_performance,
                   p.program_name, p.program_level, d.dept_name, d.hod_name
            FROM STUDENT s
            JOIN PROGRAM p USING (program_id)
            JOIN DEPARTMENT d ON d.dept_id = s.dept_id
            WHERE s.student_id = ?
            """
            profile = _fetchone(con, profile_query, [student_id])
            if not profile:
                raise HTTPException(status_code=404, detail="Student record not found.")

            # 2. Examination Results with percentage
            results_query = """
            SELECT er.result_id, c.course_id, c.course_name, c.credits, c.semester,
                   a.assessment_id, a.assessment_type, a.max_marks,
                   er.marks_obtained, er.result_status,
                   ROUND(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0), 1) AS percentage
            FROM EXAMINATION_RESULT er
            JOIN COURSE c USING (course_id)
            JOIN ASSESSMENT a USING (assessment_id)
            WHERE er.student_id = ?
            ORDER BY c.semester, c.course_name, a.assessment_type
            """
            results = _fetchall(con, results_query, [student_id])

            # 3. Attendance per course with 75% target calculation
            att_query = """
            SELECT att.attendance_id, c.course_id, c.course_name,
                   att.classes_held, att.classes_attended, att.attendance_percentage
            FROM ATTENDANCE att
            JOIN COURSE c USING (course_id)
            WHERE att.student_id = ?
            ORDER BY c.course_name
            """
            attendance_raw = _fetchall(con, att_query, [student_id])
            attendance = []
            for row in attendance_raw:
                held = int(row.get("classes_held") or 0)
                attended = int(row.get("classes_attended") or 0)
                pct = float(row.get("attendance_percentage") or 0.0)

                # Target calculation: needed consecutive classes to hit 75%
                # (attended + x) / (held + x) >= 0.75  =>  x >= 3*held - 4*attended
                needed = 0
                if pct < 75.0 and held > 0:
                    needed = max(0, math.ceil(3 * held - 4 * attended))

                row["classes_needed_for_75"] = needed
                row["is_at_risk"] = pct < 75.0
                attendance.append(row)

            # 4. Enrolled Courses
            courses_query = """
            SELECT c.course_id, c.course_name, c.credits, c.semester,
                   f.faculty_name, e.academic_year
            FROM ENROLLMENT e
            JOIN COURSE c USING (course_id)
            LEFT JOIN FACULTY f USING (faculty_id)
            WHERE e.student_id = ?
            ORDER BY c.semester, c.course_name
            """
            courses = _fetchall(con, courses_query, [student_id])

            # 5. Course Averages: You vs Class Average (Strictly NO other students' names/marks)
            class_avg_query = """
            WITH course_stats AS (
                SELECT er.course_id,
                       ROUND(AVG(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0)), 1) AS class_avg_percentage,
                       COUNT(DISTINCT er.student_id) AS student_count
                FROM EXAMINATION_RESULT er
                JOIN ASSESSMENT a USING (assessment_id)
                GROUP BY er.course_id
            ),
            my_stats AS (
                SELECT er.course_id,
                       ROUND(AVG(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0)), 1) AS my_avg_percentage
                FROM EXAMINATION_RESULT er
                JOIN ASSESSMENT a USING (assessment_id)
                WHERE er.student_id = ?
                GROUP BY er.course_id
            )
            SELECT c.course_id, c.course_name,
                   m.my_avg_percentage,
                   cs.class_avg_percentage,
                   cs.student_count
            FROM my_stats m
            JOIN COURSE c USING (course_id)
            JOIN course_stats cs USING (course_id)
            ORDER BY c.course_name
            """
            benchmarks = _fetchall(con, class_avg_query, [student_id])

            # 6. Scholarships
            scholarships = _fetchall(
                con,
                "SELECT scholarship_id, scholarship_name, amount, eligibility_criteria, status "
                "FROM SCHOLARSHIP WHERE student_id = ? ORDER BY scholarship_id",
                [student_id]
            )

            # 7. Hostel
            hostel = _fetchone(
                con,
                "SELECT hostel_id, hostel_name, room_no FROM HOSTEL WHERE student_id = ?",
                [student_id]
            )

            # 8. Internships
            internships = _fetchall(
                con,
                "SELECT internship_id, company_name, duration_weeks, start_date, end_date "
                "FROM INTERNSHIP WHERE student_id = ? ORDER BY start_date DESC",
                [student_id]
            )

            # 9. Research Projects
            research = _fetchall(
                con,
                "SELECT rp.project_id, rp.project_title, rp.start_date, rp.end_date, rp.status, "
                "       f.faculty_name AS supervisor "
                "FROM RESEARCH_PROJECT rp "
                "JOIN FACULTY f USING (faculty_id) "
                "WHERE rp.student_id = ? ORDER BY rp.start_date DESC",
                [student_id]
            )

            return {
                "profile": profile,
                "results": results,
                "attendance": attendance,
                "courses": courses,
                "benchmarks": benchmarks,
                "scholarships": scholarships,
                "hostel": hostel,
                "internships": internships,
                "research": research
            }
        finally:
            con.close()


# ============================================================================
# FACULTY PORTAL APIS (Strictly own assigned courses from session ref_id)
# ============================================================================

@faculty_router.get("/me/courses")
async def get_faculty_courses(current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user.get("ref_id")
    if not faculty_id:
        raise HTTPException(status_code=400, detail="Faculty profile not linked to session.")

    with db_lock:
        con = get_connection()
        try:
            query = """
            SELECT c.course_id, c.course_name, c.credits, c.semester, d.dept_name,
                   (SELECT COUNT(DISTINCT e.student_id) FROM ENROLLMENT e WHERE e.course_id = c.course_id) AS enrolled_count,
                   (SELECT ROUND(AVG(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0)), 1)
                    FROM EXAMINATION_RESULT er
                    JOIN ASSESSMENT a USING (assessment_id)
                    WHERE er.course_id = c.course_id) AS avg_score,
                   (SELECT ROUND(100.0 * AVG(CASE WHEN er.result_status = 'Pass' THEN 1 WHEN er.result_status = 'Fail' THEN 0 END), 0)
                    FROM EXAMINATION_RESULT er
                    WHERE er.course_id = c.course_id) AS pass_rate
            FROM COURSE c
            JOIN DEPARTMENT d USING (dept_id)
            WHERE c.faculty_id = ?
            ORDER BY c.semester, c.course_name
            """
            return _fetchall(con, query, [faculty_id])
        finally:
            con.close()


@faculty_router.get("/me/courses/{course_id}/students")
async def get_course_students(course_id: int, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            _verify_faculty_course(con, faculty_id, course_id)
            query = """
            SELECT s.student_id, s.student_name, s.email, s.year_of_study, p.program_name
            FROM ENROLLMENT e
            JOIN STUDENT s USING (student_id)
            JOIN PROGRAM p USING (program_id)
            WHERE e.course_id = ?
            ORDER BY s.student_id
            """
            return _fetchall(con, query, [course_id])
        finally:
            con.close()


@faculty_router.get("/me/courses/{course_id}/assessments")
async def get_course_assessments(course_id: int, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            _verify_faculty_course(con, faculty_id, course_id)
            return _fetchall(
                con,
                "SELECT assessment_id, assessment_type, max_marks FROM ASSESSMENT WHERE course_id = ? ORDER BY assessment_id",
                [course_id]
            )
        finally:
            con.close()


@faculty_router.get("/me/courses/{course_id}/marks")
async def get_course_marks(course_id: int, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            _verify_faculty_course(con, faculty_id, course_id)
            query = """
            SELECT er.result_id, er.student_id, s.student_name,
                   er.assessment_id, a.assessment_type, a.max_marks,
                   er.marks_obtained, er.result_status,
                   ROUND(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0), 1) AS percentage
            FROM EXAMINATION_RESULT er
            JOIN STUDENT s USING (student_id)
            JOIN ASSESSMENT a USING (assessment_id)
            WHERE er.course_id = ?
            ORDER BY er.student_id, er.assessment_id
            """
            return _fetchall(con, query, [course_id])
        finally:
            con.close()


@faculty_router.post("/me/courses/{course_id}/marks")
async def save_course_marks(course_id: int, request: Request, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    payload = await request.json()
    marks_list = payload.get("marks", [])

    if not isinstance(marks_list, list) or len(marks_list) == 0:
        raise HTTPException(status_code=400, detail="Invalid marks data. Expected a list of mark objects.")

    with db_lock:
        con = get_connection()
        try:
            course_name = _verify_faculty_course(con, faculty_id, course_id)

            # Pre-fetch assessment max marks for validation
            assessments = {
                r[0]: r[1]
                for r in con.execute("SELECT assessment_id, max_marks FROM ASSESSMENT WHERE course_id = ?", [course_id]).fetchall()
            }

            saved_count = 0
            for item in marks_list:
                student_id = int(item["student_id"])
                assessment_id = int(item["assessment_id"])
                marks_obtained = float(item["marks_obtained"])

                if assessment_id not in assessments:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Assessment {assessment_id} does not belong to course {course_id}."
                    )

                max_marks = assessments[assessment_id]
                if marks_obtained < 0 or marks_obtained > max_marks:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid marks for student {student_id}: {marks_obtained} is out of bounds (0 - {max_marks})."
                    )

                # Clear pass mark rule: 40% of max_marks
                pass_threshold = 0.40 * max_marks
                result_status = "Pass" if marks_obtained >= pass_threshold else "Fail"

                # Check if existing result exists
                existing = con.execute(
                    "SELECT result_id FROM EXAMINATION_RESULT WHERE student_id = ? AND course_id = ? AND assessment_id = ?",
                    [student_id, course_id, assessment_id]
                ).fetchone()

                if existing:
                    result_id = existing[0]
                    con.execute(
                        "UPDATE EXAMINATION_RESULT SET marks_obtained = ?, result_status = ? WHERE result_id = ?",
                        [marks_obtained, result_status, result_id]
                    )
                else:
                    max_id = con.execute("SELECT COALESCE(MAX(result_id), 0) + 1 FROM EXAMINATION_RESULT").fetchone()[0]
                    con.execute(
                        "INSERT INTO EXAMINATION_RESULT (result_id, student_id, course_id, assessment_id, marks_obtained, result_status) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [max_id, student_id, course_id, assessment_id, marks_obtained, result_status]
                    )
                saved_count += 1

            # Recalculate academic performance across the entire database
            update_academic_performance_internal(con)

            log_audit(
                current_user["user_id"],
                "faculty",
                "UPDATE_MARKS",
                f"COURSE_{course_id}",
                f"Saved {saved_count} mark records for {course_name}",
                con=con
            )

            return {
                "success": True,
                "message": f"Successfully updated {saved_count} mark record(s) for {course_name}."
            }
        finally:
            con.close()


@faculty_router.get("/me/courses/{course_id}/attendance")
async def get_course_attendance(course_id: int, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            _verify_faculty_course(con, faculty_id, course_id)
            query = """
            SELECT att.attendance_id, att.student_id, s.student_name,
                   att.classes_held, att.classes_attended, att.attendance_percentage
            FROM ATTENDANCE att
            JOIN STUDENT s USING (student_id)
            WHERE att.course_id = ?
            ORDER BY s.student_id
            """
            return _fetchall(con, query, [course_id])
        finally:
            con.close()


@faculty_router.post("/me/courses/{course_id}/attendance")
async def save_course_attendance(course_id: int, request: Request, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    payload = await request.json()
    att_list = payload.get("attendance", [])

    if not isinstance(att_list, list) or len(att_list) == 0:
        raise HTTPException(status_code=400, detail="Invalid attendance data. Expected a list.")

    with db_lock:
        con = get_connection()
        try:
            course_name = _verify_faculty_course(con, faculty_id, course_id)
            saved_count = 0

            for item in att_list:
                student_id = int(item["student_id"])
                held = int(item["classes_held"])
                attended = int(item["classes_attended"])

                if held < 0 or attended < 0:
                    raise HTTPException(status_code=400, detail="Classes held and attended cannot be negative.")
                if attended > held:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Classes attended ({attended}) cannot exceed classes held ({held}) for student {student_id}."
                    )

                pct = round(100.0 * attended / held, 2) if held > 0 else 0.0

                existing = con.execute(
                    "SELECT attendance_id FROM ATTENDANCE WHERE student_id = ? AND course_id = ?",
                    [student_id, course_id]
                ).fetchone()

                if existing:
                    con.execute(
                        "UPDATE ATTENDANCE SET classes_held = ?, classes_attended = ?, attendance_percentage = ? WHERE attendance_id = ?",
                        [held, attended, pct, existing[0]]
                    )
                else:
                    max_id = con.execute("SELECT COALESCE(MAX(attendance_id), 0) + 1 FROM ATTENDANCE").fetchone()[0]
                    con.execute(
                        "INSERT INTO ATTENDANCE (attendance_id, student_id, course_id, classes_held, classes_attended, attendance_percentage) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [max_id, student_id, course_id, held, attended, pct]
                    )
                saved_count += 1

            log_audit(
                current_user["user_id"],
                "faculty",
                "UPDATE_ATTENDANCE",
                f"COURSE_{course_id}",
                f"Saved {saved_count} attendance records for {course_name}",
                con=con
            )

            return {
                "success": True,
                "message": f"Successfully updated {saved_count} attendance record(s) for {course_name}."
            }
        finally:
            con.close()


@faculty_router.get("/me/courses/{course_id}/analytics")
async def get_course_analytics(course_id: int, current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            course_name = _verify_faculty_course(con, faculty_id, course_id)

            # Overall Stats
            stats = _fetchone(con, """
                SELECT ROUND(AVG(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0)), 1) AS avg_score,
                       ROUND(100.0 * AVG(CASE WHEN er.result_status = 'Pass' THEN 1 WHEN er.result_status = 'Fail' THEN 0 END), 0) AS pass_rate,
                       COUNT(DISTINCT er.student_id) AS evaluated_students
                FROM EXAMINATION_RESULT er
                JOIN ASSESSMENT a USING (assessment_id)
                WHERE er.course_id = ?
            """, [course_id]) or {}

            # Score Distribution Bands
            bands = _fetchall(con, """
                SELECT CASE
                    WHEN p >= 90 THEN 'A (90%+)'
                    WHEN p >= 75 THEN 'B (75-89%)'
                    WHEN p >= 60 THEN 'C (60-74%)'
                    WHEN p >= 40 THEN 'D (40-59%)'
                    ELSE 'F (<40%)'
                END AS band,
                COUNT(*) AS count
                FROM (
                    SELECT 100.0 * er.marks_obtained / NULLIF(a.max_marks, 0) AS p
                    FROM EXAMINATION_RESULT er
                    JOIN ASSESSMENT a USING (assessment_id)
                    WHERE er.course_id = ?
                )
                GROUP BY band
                ORDER BY band
            """, [course_id])

            # At-Risk Watchlist for this course: attendance < 75% OR score < 40% OR any fails
            at_risk = _fetchall(con, """
                WITH sc AS (
                    SELECT er.student_id,
                           ROUND(AVG(100.0 * er.marks_obtained / NULLIF(a.max_marks, 0)), 1) AS avg_score,
                           SUM(CASE WHEN er.result_status = 'Fail' THEN 1 ELSE 0 END) AS fails
                    FROM EXAMINATION_RESULT er
                    JOIN ASSESSMENT a USING (assessment_id)
                    WHERE er.course_id = ?
                    GROUP BY er.student_id
                ),
                ax AS (
                    SELECT student_id, attendance_percentage AS attendance
                    FROM ATTENDANCE
                    WHERE course_id = ?
                )
                SELECT s.student_id, s.student_name, s.email,
                       sc.avg_score, ax.attendance, COALESCE(sc.fails, 0) AS fails,
                       ((CASE WHEN sc.avg_score < 40 THEN 1 ELSE 0 END) +
                        (CASE WHEN ax.attendance < 75 THEN 1 ELSE 0 END) +
                        (CASE WHEN sc.fails > 0 THEN 1 ELSE 0 END)) AS risk_flags
                FROM ENROLLMENT e
                JOIN STUDENT s USING (student_id)
                LEFT JOIN sc USING (student_id)
                LEFT JOIN ax USING (student_id)
                WHERE e.course_id = ?
                  AND (sc.avg_score < 40 OR ax.attendance < 75 OR sc.fails > 0)
                ORDER BY risk_flags DESC, sc.avg_score ASC
            """, [course_id, course_id, course_id])

            return {
                "course_name": course_name,
                "stats": stats,
                "bands": bands,
                "at_risk": at_risk
            }
        finally:
            con.close()


@faculty_router.get("/me/research")
async def get_faculty_research(current_user: dict = Depends(require_role("faculty"))):
    faculty_id = current_user["ref_id"]
    with db_lock:
        con = get_connection()
        try:
            query = """
            SELECT rp.project_id, rp.project_title, rp.start_date, rp.end_date, rp.status,
                   s.student_id, s.student_name
            FROM RESEARCH_PROJECT rp
            JOIN STUDENT s USING (student_id)
            WHERE rp.faculty_id = ?
            ORDER BY rp.status, rp.start_date DESC
            """
            return _fetchall(con, query, [faculty_id])
        finally:
            con.close()


# ============================================================================
# ADMIN USER MANAGEMENT & AUDIT APIS (Admin only)
# ============================================================================

@admin_router.get("/users")
async def list_users(current_user: dict = Depends(require_role("admin"))):
    with db_lock:
        con = get_connection()
        try:
            query = """
            SELECT u.user_id, u.role, u.ref_id, u.is_active, u.must_change_password,
                   u.failed_attempts, u.locked_until,
                   CASE
                       WHEN u.role = 'student' THEN (SELECT s.student_name FROM STUDENT s WHERE s.student_id = u.ref_id)
                       WHEN u.role = 'faculty' THEN (SELECT f.faculty_name FROM FACULTY f WHERE f.faculty_id = u.ref_id)
                       ELSE 'System Administrator'
                   END AS linked_name,
                   CASE
                       WHEN u.role = 'student' THEN (SELECT s.email FROM STUDENT s WHERE s.student_id = u.ref_id)
                       WHEN u.role = 'faculty' THEN (SELECT f.email FROM FACULTY f WHERE f.faculty_id = u.ref_id)
                       ELSE 'admin@abcuniv.edu'
                   END AS email
            FROM USER_ACCOUNT u
            ORDER BY u.role, u.user_id
            """
            return _fetchall(con, query)
        finally:
            con.close()


@admin_router.post("/users")
async def create_user(request: Request, current_user: dict = Depends(require_role("admin"))):
    data = await request.json()
    user_id = str(data.get("user_id", "")).strip()
    role = str(data.get("role", "")).lower()
    ref_id = data.get("ref_id")
    password = str(data.get("password", "")).strip()

    if not user_id or not role or not password:
        raise HTTPException(status_code=400, detail="User ID, role, and initial password are required.")

    if role not in ("admin", "faculty", "student"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin', 'faculty', or 'student'.")

    if role in ("faculty", "student"):
        if ref_id is None:
            raise HTTPException(status_code=400, detail=f"A valid {role}_id (ref_id) is required for {role} accounts.")
        ref_id = int(ref_id)
    else:
        ref_id = None

    hashed = hash_password(password)

    with db_lock:
        con = get_connection()
        try:
            # Check duplicate user_id
            dup = con.execute("SELECT user_id FROM USER_ACCOUNT WHERE user_id = ?", [user_id]).fetchone()
            if dup:
                raise HTTPException(status_code=400, detail=f"User ID '{user_id}' already exists.")

            con.execute(
                "INSERT INTO USER_ACCOUNT (user_id, role, ref_id, password_hash, is_active, must_change_password, failed_attempts, locked_until) "
                "VALUES (?, ?, ?, ?, TRUE, TRUE, 0, NULL)",
                [user_id, role, ref_id, hashed]
            )

            log_audit(
                current_user["user_id"],
                "admin",
                "CREATE_USER",
                f"USER_{user_id}",
                f"Created {role} account for user {user_id}"
            )

            return {"success": True, "message": f"Account '{user_id}' created successfully."}
        finally:
            con.close()


@admin_router.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, request: Request, current_user: dict = Depends(require_role("admin"))):
    data = await request.json()
    new_password = str(data.get("new_password", "")).strip()

    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    new_hash = hash_password(new_password)

    with db_lock:
        con = get_connection()
        try:
            existing = con.execute("SELECT user_id FROM USER_ACCOUNT WHERE user_id = ?", [user_id]).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

            con.execute(
                "UPDATE USER_ACCOUNT SET password_hash = ?, must_change_password = TRUE, failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
                [new_hash, user_id]
            )

            log_audit(
                current_user["user_id"],
                "admin",
                "RESET_PASSWORD",
                f"USER_{user_id}",
                f"Admin reset password for user {user_id}"
            )

            return {"success": True, "message": f"Password for '{user_id}' reset successfully. User must change password on next login."}
        finally:
            con.close()


@admin_router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, current_user: dict = Depends(require_role("admin"))):
    if user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Security constraint: You cannot deactivate your own admin account.")

    with db_lock:
        con = get_connection()
        try:
            user = con.execute("SELECT user_id, is_active FROM USER_ACCOUNT WHERE user_id = ?", [user_id]).fetchone()
            if not user:
                raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

            new_status = not bool(user[1])
            con.execute(
                "UPDATE USER_ACCOUNT SET is_active = ? WHERE user_id = ?",
                [new_status, user_id]
            )

            status_str = "activated" if new_status else "deactivated"
            log_audit(
                current_user["user_id"],
                "admin",
                "TOGGLE_ACTIVE",
                f"USER_{user_id}",
                f"User {user_id} was {status_str}"
            )

            return {
                "success": True,
                "message": f"User '{user_id}' has been {status_str}.",
                "is_active": new_status
            }
        finally:
            con.close()


@admin_router.get("/audit-logs")
async def get_audit_logs(current_user: dict = Depends(require_role("admin"))):
    with db_lock:
        con = get_connection()
        try:
            logs = _fetchall(
                con,
                "SELECT log_id, timestamp, user_id, role, action, target, details "
                "FROM AUDIT_LOG ORDER BY log_id DESC LIMIT 100"
            )
            return logs
        finally:
            con.close()

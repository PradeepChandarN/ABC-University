"""Analytics queries powering the Insights dashboard (all computed live in DuckDB)."""
from decimal import Decimal
from database import get_connection, serialize_row, db_lock

PCT = "100.0 * er.marks_obtained / a.max_marks"


def _rows(con, sql, params=None):
    cur = con.execute(sql, params or [])
    desc = cur.description
    return [serialize_row(desc, r) for r in cur.fetchall()]


def get_insights():
    with db_lock:
        con = get_connection()
        try:
            def one(q):
                v = con.execute(q).fetchone()[0]
                return float(v) if isinstance(v, Decimal) else v
            kpis = {
                "students": one("SELECT count(*) FROM STUDENT"),
                "faculty": one("SELECT count(*) FROM FACULTY"),
                "courses": one("SELECT count(*) FROM COURSE"),
                "avg_score": round(one(f"SELECT avg({PCT}) FROM EXAMINATION_RESULT er JOIN ASSESSMENT a USING(assessment_id)") or 0, 1),
                "pass_rate": round(one("SELECT 100.0*avg(CASE WHEN result_status='Pass' THEN 1 ELSE 0 END) FROM EXAMINATION_RESULT") or 0, 1),
                "avg_attendance": round(one("SELECT avg(100.0*classes_attended/classes_held) FROM ATTENDANCE") or 0, 1),
                "scholarship_active": one("SELECT coalesce(sum(amount),0) FROM SCHOLARSHIP WHERE status='Active'"),
                "hostel_residents": one("SELECT count(student_id) FROM HOSTEL"),
            }
            departments = _rows(con, f"""
                SELECT d.dept_name AS name, d.hod_name AS hod,
                  (SELECT count(*) FROM STUDENT s WHERE s.dept_id=d.dept_id) AS students,
                  (SELECT count(*) FROM FACULTY f WHERE f.dept_id=d.dept_id) AS faculty,
                  (SELECT count(*) FROM COURSE c WHERE c.dept_id=d.dept_id) AS courses,
                  (SELECT round(avg({PCT}),1) FROM EXAMINATION_RESULT er
                     JOIN ASSESSMENT a USING(assessment_id) JOIN STUDENT s ON s.student_id=er.student_id
                     WHERE s.dept_id=d.dept_id) AS avg_score
                FROM DEPARTMENT d ORDER BY d.dept_id""")
            courses = _rows(con, f"""
                SELECT c.course_name AS name, f.faculty_name AS faculty,
                  count(DISTINCT e.student_id) AS enrolled,
                  round(avg({PCT}),1) AS avg_score,
                  round(100.0*avg(CASE WHEN er.result_status='Pass' THEN 1 ELSE 0 END),0) AS pass_rate
                FROM COURSE c LEFT JOIN FACULTY f USING(faculty_id)
                LEFT JOIN ENROLLMENT e ON e.course_id=c.course_id
                LEFT JOIN EXAMINATION_RESULT er ON er.course_id=c.course_id
                LEFT JOIN ASSESSMENT a ON a.assessment_id=er.assessment_id
                GROUP BY c.course_id, c.course_name, f.faculty_name ORDER BY avg_score DESC NULLS LAST""")
            leaderboard = _rows(con, f"""
                SELECT s.student_id AS id, s.student_name AS name, d.dept_name AS dept,
                  s.year_of_study AS year, round(avg({PCT}),1) AS score
                FROM STUDENT s JOIN DEPARTMENT d USING(dept_id)
                JOIN EXAMINATION_RESULT er ON er.student_id=s.student_id
                JOIN ASSESSMENT a USING(assessment_id)
                GROUP BY ALL ORDER BY score DESC""")
            attendance = _rows(con, """
                SELECT s.student_id AS id, s.student_name AS name, c.course_name AS course,
                  round(100.0*t.classes_attended/t.classes_held,1) AS pct
                FROM ATTENDANCE t JOIN STUDENT s USING(student_id) JOIN COURSE c USING(course_id)
                ORDER BY pct""")
            grade_bands = _rows(con, f"""
                SELECT CASE WHEN p>=90 THEN 'A  90+' WHEN p>=75 THEN 'B  75-89' WHEN p>=60 THEN 'C  60-74'
                            WHEN p>=40 THEN 'D  40-59' ELSE 'F  <40' END AS band, count(*) AS n
                FROM (SELECT {PCT} AS p FROM EXAMINATION_RESULT er JOIN ASSESSMENT a USING(assessment_id))
                GROUP BY band ORDER BY band""")
            by_type = _rows(con, f"""
                SELECT a.assessment_type AS type, round(avg({PCT}),1) AS avg_score, count(*) AS n
                FROM EXAMINATION_RESULT er JOIN ASSESSMENT a USING(assessment_id) GROUP BY 1 ORDER BY 2 DESC""")
            scholarships = _rows(con, "SELECT status, count(*) AS n, coalesce(sum(amount),0) AS amount FROM SCHOLARSHIP GROUP BY status")
            mix = {
                "gender": _rows(con, "SELECT coalesce(gender,'Unknown') AS label, count(*) AS n FROM STUDENT GROUP BY 1 ORDER BY 2 DESC"),
                "level": _rows(con, "SELECT p.program_level AS label, count(*) AS n FROM STUDENT s JOIN PROGRAM p USING(program_id) GROUP BY 1 ORDER BY 2 DESC"),
                "year": _rows(con, "SELECT 'Year '||year_of_study AS label, count(*) AS n FROM STUDENT GROUP BY year_of_study ORDER BY year_of_study"),
                "faculty_type": _rows(con, "SELECT coalesce(faculty_type,'Unknown') AS label, count(*) AS n FROM FACULTY GROUP BY 1 ORDER BY 2 DESC"),
            }
            at_risk = _rows(con, f"""
                WITH sc AS (SELECT er.student_id, avg({PCT}) AS score, sum(CASE WHEN er.result_status='Fail' THEN 1 ELSE 0 END) AS fails
                            FROM EXAMINATION_RESULT er JOIN ASSESSMENT a USING(assessment_id) GROUP BY 1),
                     ax AS (SELECT student_id, avg(100.0*classes_attended/classes_held) AS att FROM ATTENDANCE GROUP BY 1)
                SELECT s.student_id AS id, s.student_name AS name, round(sc.score,1) AS score,
                       round(ax.att,1) AS attendance, coalesce(sc.fails,0) AS fails,
                       (CASE WHEN sc.score<50 THEN 1 ELSE 0 END)+(CASE WHEN ax.att<75 THEN 1 ELSE 0 END)+(CASE WHEN sc.fails>0 THEN 1 ELSE 0 END) AS flags
                FROM STUDENT s LEFT JOIN sc USING(student_id) LEFT JOIN ax USING(student_id)
                WHERE sc.score<50 OR ax.att<75 OR sc.fails>0 ORDER BY flags DESC, score""")
            internships = _rows(con, "SELECT s.student_name AS name, i.company_name AS company, i.duration_weeks AS weeks, i.start_date AS start FROM INTERNSHIP i JOIN STUDENT s USING(student_id) ORDER BY i.start_date")
            research = _rows(con, "SELECT r.project_title AS title, s.student_name AS student, f.faculty_name AS guide, r.status FROM RESEARCH_PROJECT r JOIN STUDENT s USING(student_id) JOIN FACULTY f USING(faculty_id)")
            workload = _rows(con, "SELECT f.faculty_name AS name, f.designation, count(DISTINCT c.course_id) AS courses, coalesce(sum(c.credits),0) AS credits FROM FACULTY f LEFT JOIN COURSE c USING(faculty_id) GROUP BY ALL ORDER BY credits DESC")
            return dict(kpis=kpis, departments=departments, courses=courses, leaderboard=leaderboard,
                        attendance=attendance, grade_bands=grade_bands, by_type=by_type,
                        scholarships=scholarships, mix=mix, at_risk=at_risk,
                        internships=internships, research=research, workload=workload)
        finally:
            con.close()


def get_student_profile(student_id: int):
    with db_lock:
        con = get_connection()
        try:
            p = _rows(con, """SELECT s.*, d.dept_name, pr.program_name, pr.program_level
                FROM STUDENT s JOIN DEPARTMENT d USING(dept_id) JOIN PROGRAM pr USING(program_id)
                WHERE s.student_id=?""", [student_id])
            if not p:
                return None
            q = lambda sql: _rows(con, sql, [student_id])
            return dict(
                profile=p[0],
                results=q(f"""SELECT c.course_name AS course, a.assessment_type AS type, er.marks_obtained AS marks,
                    a.max_marks AS max, round({PCT},1) AS pct, er.result_status AS status
                    FROM EXAMINATION_RESULT er JOIN ASSESSMENT a USING(assessment_id) JOIN COURSE c ON c.course_id=er.course_id
                    WHERE er.student_id=? ORDER BY c.course_name, a.assessment_id"""),
                attendance=q("""SELECT c.course_name AS course, t.classes_attended AS attended, t.classes_held AS held,
                    round(100.0*t.classes_attended/t.classes_held,1) AS pct
                    FROM ATTENDANCE t JOIN COURSE c USING(course_id) WHERE t.student_id=?"""),
                scholarships=q("SELECT scholarship_name AS name, amount, status, eligibility_criteria AS criteria FROM SCHOLARSHIP WHERE student_id=?"),
                hostel=q("SELECT hostel_name AS name, room_no AS room FROM HOSTEL WHERE student_id=?"),
                internships=q("SELECT company_name AS company, duration_weeks AS weeks, start_date AS start, end_date AS end FROM INTERNSHIP WHERE student_id=?"),
                research=q("SELECT r.project_title AS title, r.status, f.faculty_name AS guide FROM RESEARCH_PROJECT r JOIN FACULTY f USING(faculty_id) WHERE r.student_id=?"),
                courses=q("SELECT c.course_name AS name, e.semester, e.academic_year AS year FROM ENROLLMENT e JOIN COURSE c USING(course_id) WHERE e.student_id=?"),
            )
        finally:
            con.close()

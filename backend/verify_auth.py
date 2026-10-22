import sys
import urllib.request
import urllib.parse
import json
import http.cookiejar

# Ensure immediate unbuffered output
sys.stdout.reconfigure(line_buffering=True)

BASE = 'http://127.0.0.1:8000'

def make_session():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    return opener

def request(opener, path, data=None, method=None):
    if method is None:
        method = 'POST' if data is not None else 'GET'
    url = BASE + path
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        res = opener.open(req)
        return res.status, json.loads(res.read().decode('utf-8')), res.geturl()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8')
        try:
            return e.code, json.loads(body_text), e.geturl()
        except Exception:
            return e.code, body_text, e.geturl()

def run_tests():
    print("==================================================")
    print("1. ANONYMOUS ACCESS VERIFICATION")
    print("==================================================")
    anon = make_session()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    no_red_opener = urllib.request.build_opener(NoRedirect)

    # Web pages: must redirect to /login
    for page in ['/admin', '/student', '/faculty', '/admin/manage', '/admin/users']:
        req = urllib.request.Request(BASE + page)
        try:
            res = no_red_opener.open(req)
            print(f"FAILED: {page} returned status {res.status}")
        except urllib.error.HTTPError as e:
            loc = e.headers.get('Location', '')
            print(f"PASS: {page:<15} -> HTTP {e.code} Redirect -> {loc}")
            assert e.code in (302, 307) and '/login' in loc, f"Failed redirect on {page}"

    # API endpoints: must return HTTP 401
    for ep in ['/api/insights', '/api/student/me/overview', '/api/faculty/me/courses', '/api/admin/users', '/api/STUDENT']:
        status_code, data, _ = request(anon, ep)
        print(f"PASS: {ep:<25} -> HTTP {status_code}")
        assert status_code == 401, f"Expected 401 on {ep}, got {status_code}"

    print("\n==================================================")
    print("2. LOGIN & BRUTE FORCE LOCKOUT VERIFICATION")
    print("==================================================")
    # Test wrong password
    st, d, _ = request(anon, '/api/auth/login', {'user_id': '1010', 'password': 'WrongPassword123'})
    print(f"Wrong password: HTTP {st} -> {d.get('detail')}")
    assert st == 400 and d.get('detail') == 'Invalid login ID or password.'

    # Trigger 5 failed attempts
    for i in range(4):
        request(anon, '/api/auth/login', {'user_id': '1010', 'password': 'WrongPassword123'})

    # 6th attempt should be locked
    st, d, _ = request(anon, '/api/auth/login', {'user_id': '1010', 'password': 'Student@123'})
    print(f"Locked attempt: HTTP {st} -> {d.get('detail')}")
    assert st == 400 and 'temporarily locked' in str(d.get('detail')), f"Lockout failed: {d}"

    print("\n==================================================")
    print("3. ADMIN SESSION & UNLOCK CAPABILITY")
    print("==================================================")
    admin_sess = make_session()
    st, d, _ = request(admin_sess, '/api/auth/login', {'user_id': 'admin', 'password': 'Admin@123'})
    assert st == 200 and d['user']['role'] == 'admin'
    print("Admin logged in successfully.")

    # Admin resets password for 1010, unlocking account
    st, d, _ = request(admin_sess, '/api/admin/users/1010/reset-password', {'new_password': 'Student@123'})
    print(f"Admin reset & unlocked 1010: HTTP {st} -> {d.get('message')}")
    assert st == 200

    # User 1010 can now login again
    st, d, _ = request(anon, '/api/auth/login', {'user_id': '1010', 'password': 'Student@123'})
    print(f"Unlocked 1010 login: HTTP {st} -> role: {d.get('user', {}).get('role')}")
    assert st == 200

    print("\n==================================================")
    print("4. STUDENT SESSION & PERMISSION CHECKS")
    print("==================================================")
    student_sess = make_session()
    st, d, _ = request(student_sess, '/api/auth/login', {'user_id': '1001', 'password': 'Student@123'})
    assert st == 200 and d['user']['role'] == 'student'
    print(f"Student 1001 logged in: {d['user']['name']} (Role: {d['user']['role']})")

    # Student accesses own overview
    st, stu_data, _ = request(student_sess, '/api/student/me/overview')
    assert st == 200
    p = stu_data['profile']
    print(f"PASS: Own profile retrieved: {p['student_name']} (ID: {p['student_id']}), GPA: {p['academic_performance']}")
    print(f"PASS: Results count: {len(stu_data['results'])}, Attendance count: {len(stu_data['attendance'])}")
    assert p['student_id'] == 1001

    # Student accesses /api/faculty/me/courses -> 403
    st, d, _ = request(student_sess, '/api/faculty/me/courses')
    print(f"PASS: Student -> /api/faculty/me/courses returned HTTP {st}")
    assert st == 403

    # Student accesses /api/STUDENT (admin CRUD) -> 403
    st, d, _ = request(student_sess, '/api/STUDENT')
    print(f"PASS: Student -> /api/STUDENT returned HTTP {st}")
    assert st == 403

    # Student accesses /api/insights (admin insights) -> 403
    st, d, _ = request(student_sess, '/api/insights')
    print(f"PASS: Student -> /api/insights returned HTTP {st}")
    assert st == 403

    print("\n==================================================")
    print("5. FACULTY SESSION & COURSE ISOLATION CHECKS")
    print("==================================================")
    faculty_sess = make_session()
    st, d, _ = request(faculty_sess, '/api/auth/login', {'user_id': '501', 'password': 'Faculty@123'})
    assert st == 200 and d['user']['role'] == 'faculty'
    print(f"Faculty 501 logged in: {d['user']['name']}")

    # Faculty accesses own courses
    st, courses, _ = request(faculty_sess, '/api/faculty/me/courses')
    assert st == 200
    course_ids = [c['course_id'] for c in courses]
    print(f"PASS: Faculty 501 assigned courses: {course_ids}")
    assert 201 in course_ids

    # Faculty attempts to access Course 205 (taught by 503) -> 403 Forbidden!
    st, d, _ = request(faculty_sess, '/api/faculty/me/courses/205/students')
    print(f"PASS: Faculty 501 -> Course 205 (other faculty) students returned HTTP {st}")
    assert st == 403

    st, d, _ = request(faculty_sess, '/api/faculty/me/courses/205/marks')
    print(f"PASS: Faculty 501 -> Course 205 marks returned HTTP {st}")
    assert st == 403

    # Faculty attempts admin route -> 403
    st, d, _ = request(faculty_sess, '/api/admin/users')
    print(f"PASS: Faculty 501 -> /api/admin/users returned HTTP {st}")
    assert st == 403

    # Faculty saves mark for student 1001 in Course 201
    st, d, _ = request(faculty_sess, '/api/faculty/me/courses/201/marks', {
        'marks': [{'student_id': 1001, 'assessment_id': 301, 'marks_obtained': 18.5}]
    }, method='POST')
    print(f"PASS: Faculty 501 saved marks for Course 201: HTTP {st} -> {d.get('message')}")
    assert st == 200

    print("\n==================================================")
    print("6. ADMIN CAPABILITIES & AUDIT LOGGING")
    print("==================================================")
    # Admin accesses insights
    st, ins, _ = request(admin_sess, '/api/insights')
    assert st == 200
    print(f"PASS: Admin insights accessible. Live KPI avg_score: {ins['kpis']['avg_score']}%")

    # Admin accesses users list
    st, users, _ = request(admin_sess, '/api/admin/users')
    assert st == 200
    print(f"PASS: Admin user accounts listed: {len(users)} accounts.")

    # Admin accesses audit logs
    st, logs, _ = request(admin_sess, '/api/admin/audit-logs')
    assert st == 200 and len(logs) > 0
    print(f"PASS: Audit log records verified: {len(logs)} entries. Latest action: {logs[0]['action']} on {logs[0]['target']}")

    print("\n==================================================")
    print("7. PASSWORD CHANGE & SECURITY LIFECYCLE")
    print("==================================================")
    # Student 1001 changes password
    st, d, _ = request(student_sess, '/api/auth/change-password', {
        'current_password': 'Student@123',
        'new_password': 'NewSecurePass@456'
    }, method='POST')
    print(f"Password change result: HTTP {st} -> {d.get('message')}")
    assert st == 200

    # Old password fails
    st, d, _ = request(anon, '/api/auth/login', {'user_id': '1001', 'password': 'Student@123'})
    print(f"Old password attempt: HTTP {st} -> {d.get('detail')}")
    assert st == 400

    # New password succeeds
    st, d, _ = request(anon, '/api/auth/login', {'user_id': '1001', 'password': 'NewSecurePass@456'})
    print(f"New password attempt: HTTP {st} -> {d.get('message')}")
    assert st == 200

    # Reset password back to default via Admin endpoint for consistency
    st, d, _ = request(admin_sess, '/api/admin/users/1001/reset-password', {'new_password': 'Student@123'})
    assert st == 200
    print("Restored student 1001 password to demo default via Admin reset.")

    print("\n==================================================")
    print("ALL 7 VERIFICATION SUITES COMPLETED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()

# ABC University Academic Management System

A comprehensive, production-grade Academic Management System built for **ABC University**, powered by a persistent **DuckDB** database, **FastAPI (Python)** backend, and a modern, responsive **Vanilla HTML/CSS/JavaScript** frontend interface.

The entire database schema, table structures, constraints, relationships, sample records, and the original `academic_performance` update logic are derived directly from `ABC UNIVERSITY(1).docx`.

---

## 🏛️ System Architecture

- **Database**: DuckDB (Persistent file at `backend/university.duckdb`)
  - Exactly 13 tables converted from Oracle SQL to DuckDB SQL.
  - All original columns, data types, primary keys, foreign keys, unique constraints, and check constraints preserved.
  - All 115 original sample records preserved.
  - Original Oracle PL/SQL `academic_performance` update adapted to DuckDB syntax.
  - Idempotent seeding prevents record duplication on restarts.
- **Backend**: Python 3.10+ & FastAPI
  - Full CRUD REST API for all 13 tables (`GET`, `POST`, `PUT`, `DELETE`).
  - Thread-safe parameterized SQL execution with `threading.Lock`.
  - Comprehensive constraint error handling with clean HTTP 400 responses.
  - Dynamic foreign-key lookup endpoint (`/api/lookups`) for dropdown population.
  - Performance recalculation endpoint (`/api/recalculate-performance`).
- **Security & Portals**:
  - Role-based Access Control (RBAC): Student, Faculty, and Admin portals.
  - PBKDF2-HMAC-SHA256 salted password hashing (260,000 iterations).
  - Signed, HttpOnly, SameSite=Lax session cookies (8-hour lifetime) via `itsdangerous`.
  - Brute-force protection: Locks accounts for 5 minutes after 5 failed login attempts.
  - Server-side role enforcement on all API routes and web views.
  - Audit logging of all administrative actions and faculty mark/attendance updates.
- **Frontend**: HTML5, Vanilla CSS & Vanilla JavaScript
  - Cohesive Academic design system (Paper `#f3eee4`, Ink `#14213d`, Vermilion `#c2410c`).
  - **Student Portal (`/student`)**: Read-only personal academic 360, attendance radar with 75% target calculator, performance benchmark (You vs Class Average).
  - **Faculty Portal (`/faculty`)**: Restricted to assigned courses, mark entry with 40% pass rule, attendance log, class analytics & at-risk watchlist.
  - **Admin Portal (`/admin`)**: Institutional analytics dashboard, record management (`/admin/manage`), user directory & audit logs (`/admin/users`).

---

## 🗃️ 13 Database Tables

| # | Table Name | Primary Key | Description | Records |
|---|---|---|---|---|
| 1 | `DEPARTMENT` | `dept_id` | Academic departments & HOD details | 3 |
| 2 | `PROGRAM` | `program_id` | Degree programs (UG, PG, PhD) linked to departments | 4 |
| 3 | `STUDENT` | `student_id` | Enrolled students, personal info & academic performance | 10 |
| 4 | `FACULTY` | `faculty_id` | Faculty members, designations & department affiliations | 6 |
| 5 | `COURSE` | `course_id` | Courses, credits, semesters & assigned faculty | 8 |
| 6 | `ENROLLMENT` | `enrollment_id` | Student course enrollments by semester & academic year | 15 |
| 7 | `ASSESSMENT` | `assessment_id` | Course assessments (Assignments, Quizzes, Exams) | 16 |
| 8 | `EXAMINATION_RESULT` | `result_id` | Student marks & pass/fail statuses | 20 |
| 9 | `ATTENDANCE` | `attendance_id` | Classes held, attended & attendance percentages | 15 |
| 10 | `SCHOLARSHIP` | `scholarship_id` | Student scholarships, grant amounts & statuses | 5 |
| 11 | `HOSTEL` | `hostel_id` | Hostel rooms assigned to students | 5 |
| 12 | `INTERNSHIP` | `internship_id` | Industry internships & student company placements | 4 |
| 13 | `RESEARCH_PROJECT` | `project_id` | Research projects supervised by faculty | 4 |
| | **Total** | | | **115** |

### Academic Performance Update Operation
In accordance with the specification document, student academic performance is computed from examination results:
```sql
UPDATE STUDENT
SET academic_performance = COALESCE(
    (SELECT ROUND(AVG(er.marks_obtained), 2) FROM EXAMINATION_RESULT er WHERE er.student_id = STUDENT.student_id), 0
);
```
This query is automatically executed upon database initialization and whenever examination results are added, edited, or deleted. It can also be re-triggered anytime via the **"Recalculate Performance"** button in the top navigation bar.

---

## 📂 Project Structure

```text
university/
├── ABC UNIVERSITY(1).docx      # Source document
├── run.bat                     # Windows one-click startup launcher
├── README.md                   # System documentation and execution guide
├── sql/
│   ├── schema.sql              # DuckDB DDL for the 13 tables
│   └── seed.sql                # 115 original INSERT statements + UPDATE query
├── backend/
│   ├── database.py             # DuckDB connection manager, schema metadata & CRUD logic
│   ├── init_db.py              # Standalone DB initialization & verification script
│   ├── main.py                 # FastAPI application, REST endpoints & static file server
│   ├── requirements.txt        # Python dependencies
│   ├── test_app.py             # Live server integration & constraint verification test suite
│   └── university.duckdb       # Persistent DuckDB database file
└── frontend/
    ├── index.html              # University management portal single-page interface
    ├── css/
    │   └── style.css           # Premium responsive styling & glassmorphism theme
    └── js/
        └── app.js              # State management, fetch calls, dynamic modal & table logic
```

---

## 🚀 Windows Setup and Execution Instructions

### Option 1: Quick Launch (Recommended)
Double-click the `run.bat` file in the project root directory, or execute it from PowerShell / Command Prompt:
```cmd
.\run.bat
```
This script will:
1. Verify Python availability.
2. Initialize and verify the DuckDB database.
3. Automatically launch your default web browser to `http://127.0.0.1:8000`.
4. Start the FastAPI backend server with live reload.

---

### Option 2: Manual Terminal Execution

#### 1. Navigate to the project directory:
```powershell
cd d:\VIT\university
```

#### 2. Install dependencies (if not already installed):
```powershell
pip install -r backend/requirements.txt
```

#### 3. Initialize the database:
```powershell
python backend/init_db.py
```
*Note: If the database is already initialized, sample records will not be duplicated.*

#### 4. Start the FastAPI server:
```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

#### 5. Open the application:
Open your browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## 🧪 Testing & Verification

A dedicated verification test suite is included in `backend/test_app.py`. With the server running, execute:
```powershell
python backend/test_app.py
```
This script validates:
- [x] Schema & Table metadata for all 13 tables.
- [x] Record counts across all 13 tables matching the 115 rows in `ABC UNIVERSITY(1).docx`.
- [x] Full CRUD operations (Create, Read, Update, Delete) on DuckDB.
- [x] Catching and reporting constraint violations (Duplicate Primary Key, Check Constraints, Foreign Key Violations).
- [x] Recalculation of `academic_performance` from `EXAMINATION_RESULT`.
- [x] Serving of frontend assets (`index.html`, `style.css`, `app.js`).

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tables-meta` | Returns schema, column types, and constraints for all 13 tables |
| `GET` | `/api/lookups` | Returns foreign-key lookup lists for dropdown selection |
| `POST` | `/api/recalculate-performance` | Recalculates student academic performance via SQL |
| `GET` | `/api/{table}` | Lists all records in the specified table |
| `GET` | `/api/{table}/{id}` | Retrieves a single record by primary key |
---

## 🌐 Making the System Available to Others on Their Laptops

### Method 1: Instant Access Over the Same Wi-Fi / LAN (Zero Install for Others)
Because `run.bat` binds to `0.0.0.0:8000`, anyone connected to the same Wi-Fi network can use the system directly through their browser:
1. Start the application on your host laptop by running `run.bat`.
2. Notice the IP displayed in the console:
   ```text
   Access Information:
     - On this laptop:     http://localhost:8000
     - For other laptops:  http://<YOUR_IP>:8000  (e.g., http://172.20.25.2:8000)
   ```
3. Other users simply open Chrome, Edge, or Firefox on their laptops and navigate to:
   ```text
   http://<YOUR_IP>:8000
   ```
   *(Ensure Windows Firewall allows inbound connections on port 8000 if prompted).*

---

### Method 2: Share the Project for Standalone Local Execution
To let others run the system completely independently on their own laptops:
1. Compress the `university` folder into a `.zip` archive (or push it to a Git repository).
2. Send the `.zip` file to them.
3. They extract it on their laptop and double-click `run.bat`.
4. The enhanced `run.bat` will automatically:
   - Check their Python installation.
   - Automatically install all required packages (`duckdb`, `fastapi`, `uvicorn`).
   - Initialize and seed the DuckDB database.
   - Open their default browser to `http://localhost:8000`.

---

### Method 3: Share Over the Internet (Anywhere in the World)
If the other laptops are on different Wi-Fi networks or remote, you can create a free temporary secure HTTPS link:
```powershell
# Using Cloudflare Tunnel (no signup needed):
npx -y cloudflared tunnel --url http://localhost:8000
```
or
```powershell
# Using Localtunnel:
npx -y localtunnel --port 8000
```
Send the generated `https://...` link to anyone; they can immediately use the portal in their browser without installing anything.

---

## ☁️ Render Deployment & Environment Variables

When deploying to **Render**, set the following environment variables in your Render Dashboard (`Environment` tab):

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Recommended | Random secret string used to sign session cookies. If omitted, a local dev key is used. |
| `ADMIN_PASSWORD` | Optional | Custom administrator password. Defaults to `Admin@123` if unset. |
| `PYTHON_VERSION` | Yes | Set to `3.10.12` (configured in `render.yaml`). |

> **⚠️ Note on Render Free Tier Persistence**:
> Render's Free Web Service tier has an ephemeral disk that resets upon service restarts or redeployments. On every startup, DuckDB automatically verifies the database and re-seeds all default accounts from `CREDENTIALS.md`. Any passwords changed during a session on Render's free tier will revert back to the default credentials upon a server restart.

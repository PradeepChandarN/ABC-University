import os
import sys
from contextlib import asynccontextmanager

# Ensure backend directory is in Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import duckdb

from database import (
    TABLES_META,
    init_database,
    get_all_records,
    get_record_by_id,
    insert_record,
    update_record,
    delete_record,
    get_foreign_key_lookups,
    update_academic_performance
)
from insights import get_insights, get_student_profile
from auth import (
    auth_router,
    get_current_user,
    require_login,
    require_role,
    log_audit
)
from portals import student_router, faculty_router, admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DuckDB and seed sample records and accounts if necessary on startup
    init_database()
    yield

app = FastAPI(
    title="ABC University Academic Management System API",
    description="Role-Based Academic Management System with DuckDB and FastAPI",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local development and web requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(faculty_router)
app.include_router(admin_router)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


# ============================================================================
# Admin-Only Generic CRUD & Insights API Endpoints
# ============================================================================

@app.get("/api/tables-meta")
def get_tables_metadata(current_user: dict = Depends(require_role("admin"))):
    """Returns metadata for all 13 tables including columns, types, labels, and constraints (Admin only)."""
    return {"tables": TABLES_META}

@app.get("/api/lookups")
def get_lookups(current_user: dict = Depends(require_role("admin"))):
    """Returns foreign key lookup lists for UI dropdowns (Admin only)."""
    try:
        return get_foreign_key_lookups()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch lookups: {str(e)}")

@app.post("/api/recalculate-performance")
def recalculate_performance(current_user: dict = Depends(require_role("admin"))):
    """Recalculates students' academic performance based on examination results (Admin only)."""
    try:
        update_academic_performance()
        log_audit(current_user["user_id"], "admin", "RECALCULATE", "STUDENT", "Recalculated academic performance")
        return {"success": True, "message": "Academic performance recalculated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/insights")
def insights(current_user: dict = Depends(require_role("admin"))):
    """Returns aggregated academic analytics (Admin only)."""
    return get_insights()

@app.get("/api/insights/student/{student_id}")
def student_profile(student_id: int, current_user: dict = Depends(require_role("admin"))):
    """Returns student 360 profile for admin inspection (Admin only)."""
    data = get_student_profile(student_id)
    if not data:
        raise HTTPException(status_code=404, detail="Student not found.")
    return data

@app.get("/api/{table_name}")
def list_records(table_name: str, current_user: dict = Depends(require_role("admin"))):
    """Retrieves all records for a table (Admin only)."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        records = get_all_records(table_upper)
        return {
            "table": table_upper,
            "count": len(records),
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/{table_name}/{record_id}")
def get_record(table_name: str, record_id: int, current_user: dict = Depends(require_role("admin"))):
    """Retrieves a single record by primary key (Admin only)."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        record = get_record_by_id(table_upper, record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found in {table_upper}.")
        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/{table_name}", status_code=status.HTTP_201_CREATED)
async def create_record(table_name: str, request: Request, current_user: dict = Depends(require_role("admin"))):
    """Inserts a new record into the specified table (Admin only)."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        data = await request.json()
        new_record = insert_record(table_upper, data)
        pk_val = new_record.get(TABLES_META[table_upper]["pk"])
        log_audit(current_user["user_id"], "admin", "CREATE", f"{table_upper}_{pk_val}", f"Created record in {table_upper}")
        return {
            "success": True,
            "message": f"Record created successfully in {table_upper}.",
            "record": new_record
        }
    except duckdb.ConstraintException as ce:
        err_msg = str(ce)
        if "PRIMARY KEY" in err_msg or "unique" in err_msg.lower():
            detail = f"Constraint Error: Duplicate primary key or unique field value. {err_msg}"
        elif "foreign key" in err_msg.lower():
            detail = f"Constraint Error: Referenced foreign key does not exist. {err_msg}"
        elif "check" in err_msg.lower():
            detail = f"Constraint Error: Field value violates check constraint. {err_msg}"
        else:
            detail = f"Database constraint violation: {err_msg}"
        raise HTTPException(status_code=400, detail=detail)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/{table_name}/{record_id}")
async def edit_record(table_name: str, record_id: int, request: Request, current_user: dict = Depends(require_role("admin"))):
    """Updates an existing record by primary key (Admin only)."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        data = await request.json()
        updated_record = update_record(table_upper, record_id, data)
        if not updated_record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found in {table_upper}.")
        log_audit(current_user["user_id"], "admin", "UPDATE", f"{table_upper}_{record_id}", f"Updated record {record_id} in {table_upper}")
        return {
            "success": True,
            "message": f"Record {record_id} updated successfully in {table_upper}.",
            "record": updated_record
        }
    except duckdb.ConstraintException as ce:
        err_msg = str(ce)
        if "foreign key" in err_msg.lower():
            detail = f"Constraint Error: Referenced foreign key does not exist. {err_msg}"
        elif "check" in err_msg.lower():
            detail = f"Constraint Error: Field value violates check constraint. {err_msg}"
        elif "unique" in err_msg.lower():
            detail = f"Constraint Error: Duplicate unique field value. {err_msg}"
        else:
            detail = f"Database constraint violation: {err_msg}"
        raise HTTPException(status_code=400, detail=detail)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/{table_name}/{record_id}")
def remove_record(table_name: str, record_id: int, current_user: dict = Depends(require_role("admin"))):
    """Deletes a record by primary key (Admin only)."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        existing = get_record_by_id(table_upper, record_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found in {table_upper}.")
        delete_record(table_upper, record_id)
        log_audit(current_user["user_id"], "admin", "DELETE", f"{table_upper}_{record_id}", f"Deleted record {record_id} from {table_upper}")
        return {
            "success": True,
            "message": f"Record {record_id} deleted successfully from {table_upper}."
        }
    except duckdb.ConstraintException as ce:
        err_msg = str(ce)
        if "foreign key" in err_msg.lower():
            detail = f"Cannot delete: Record {record_id} in {table_upper} is referenced by other records in the database."
        else:
            detail = f"Constraint Error: {err_msg}"
        raise HTTPException(status_code=400, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Static Files & Web Page Routing with Role-Based Redirection
# ============================================================================

if os.path.exists(FRONTEND_DIR):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/login")
    async def serve_login(request: Request):
        user = await get_current_user(request)
        if user:
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

    @app.get("/")
    async def serve_root(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        return RedirectResponse(f"/{user['role']}", status_code=307)

    @app.get("/student")
    async def serve_student_portal(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        if user["role"] != "student":
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "student.html"))

    @app.get("/faculty")
    async def serve_faculty_portal(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        if user["role"] != "faculty":
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "faculty.html"))

    @app.get("/admin")
    async def serve_admin_portal(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        if user["role"] != "admin":
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "insights.html"))

    @app.get("/admin/manage")
    async def serve_admin_manage(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        if user["role"] != "admin":
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/admin/users")
    async def serve_admin_users(request: Request):
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=307)
        if user["role"] != "admin":
            return RedirectResponse(f"/{user['role']}", status_code=307)
        return FileResponse(os.path.join(FRONTEND_DIR, "users.html"))

    @app.get("/manage")
    async def legacy_manage_redirect():
        return RedirectResponse("/admin/manage", status_code=307)

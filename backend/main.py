import os
import sys
from contextlib import asynccontextmanager

# Ensure backend directory is in Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DuckDB and seed if necessary on startup
    init_database()
    yield

app = FastAPI(
    title="ABC University Academic Management System API",
    description="REST API for ABC University Academic Management System with DuckDB",
    version="1.0.0",
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

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/api/tables-meta")
def get_tables_metadata():
    """Returns metadata for all 13 tables including columns, types, labels, and constraints."""
    return {"tables": TABLES_META}

@app.get("/api/lookups")
def get_lookups():
    """Returns foreign key lookup lists for UI dropdowns."""
    try:
        return get_foreign_key_lookups()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch lookups: {str(e)}")

@app.post("/api/recalculate-performance")
def recalculate_performance():
    """Recalculates students' academic performance based on examination results."""
    try:
        update_academic_performance()
        return {"success": True, "message": "Academic performance recalculated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/{table_name}")
def list_records(table_name: str):
    """Retrieves all records for a table."""
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
def get_record(table_name: str, record_id: int):
    """Retrieves a single record by primary key."""
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
async def create_record(table_name: str, request: Request):
    """Inserts a new record into the specified table."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        data = await request.json()
        new_record = insert_record(table_upper, data)
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
async def edit_record(table_name: str, record_id: int, request: Request):
    """Updates an existing record by primary key."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        data = await request.json()
        updated_record = update_record(table_upper, record_id, data)
        if not updated_record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found in {table_upper}.")
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
def remove_record(table_name: str, record_id: int):
    """Deletes a record by primary key."""
    table_upper = table_name.upper()
    if table_upper not in TABLES_META:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")
    try:
        # Check if record exists
        existing = get_record_by_id(table_upper, record_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found in {table_upper}.")
        delete_record(table_upper, record_id)
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

# Serve frontend static assets if directory exists
if os.path.exists(FRONTEND_DIR):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse({"message": "ABC University API is running. Frontend index.html not yet found."})

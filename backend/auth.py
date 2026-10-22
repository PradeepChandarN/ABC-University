import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from database import get_connection, db_lock, serialize_row

# Session configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "abc-university-dev-secret-key-change-in-prod-384920")
SESSION_COOKIE_NAME = "abc_session"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # 8 hours
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION_MINUTES = 5

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="abc-university-session-salt")

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================================
# Password Hashing & Verification (PBKDF2-HMAC-SHA256, 260,000 iterations)
# ============================================================================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    kdf = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        260000
    )
    return f"pbkdf2:sha256:260000${salt}${kdf.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        algo_iter, salt, expected_hash = parts
        _, _, iter_str = algo_iter.split(":")
        iterations = int(iter_str)
        kdf = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        )
        return hmac.compare_digest(kdf.hex(), expected_hash)
    except Exception:
        return False


# ============================================================================
# Session Cookie Helpers
# ============================================================================

def create_session_token(data: dict) -> str:
    return serializer.dumps(data)


def decode_session_token(token: str) -> Optional[dict]:
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def is_secure_request(request: Request) -> bool:
    """Detect if connection is HTTPS (direct, via reverse proxy, or Render)."""
    if request.url.scheme == "https":
        return True
    if request.headers.get("x-forwarded-proto") == "https":
        return True
    if os.environ.get("RENDER"):
        return True
    return False


def set_session_cookie(response: Response, request: Request, data: dict):
    token = create_session_token(data)
    secure = is_secure_request(request)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/"
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax"
    )


# ============================================================================
# Audit Logging Helper
# ============================================================================

def log_audit(user_id: str, role: str, action: str, target: str, details: str = "", con=None):
    """Inserts a record into the AUDIT_LOG table."""
    try:
        with db_lock:
            should_close = False
            if con is None:
                con = get_connection()
                should_close = True
            try:
                max_id = con.execute("SELECT COALESCE(MAX(log_id), 0) + 1 FROM AUDIT_LOG").fetchone()[0]
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                con.execute(
                    "INSERT INTO AUDIT_LOG (log_id, timestamp, user_id, role, action, target, details) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [max_id, now_str, user_id, role, action, target, details]
                )
            finally:
                if should_close:
                    con.close()
    except Exception as e:
        print(f"[AUDIT LOG ERROR] {e}")


# ============================================================================
# Account Seeding Logic
# ============================================================================

def seed_user_accounts(con=None):
    """
    Seeds initial user accounts if USER_ACCOUNT is empty.
    Creates:
      - Admin ('admin') with password from ADMIN_PASSWORD or 'Admin@123'
      - One account per FACULTY (user_id = faculty_id, default 'Faculty@123')
      - One account per STUDENT (user_id = student_id, default 'Student@123')
    """
    should_close = False
    if con is None:
        con = get_connection()
        should_close = True

    try:
        # Check if table exists and count
        table_exists = False
        try:
            cnt = con.execute("SELECT count(*) FROM USER_ACCOUNT").fetchone()[0]
            table_exists = True
        except Exception:
            cnt = 0

        if not table_exists:
            return

        if cnt > 0:
            return  # Already seeded

        print("Seeding USER_ACCOUNT table with initial role-based credentials...")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "Admin@123")
        admin_hash = hash_password(admin_pass)

        # 1. Admin account
        con.execute(
            "INSERT INTO USER_ACCOUNT (user_id, role, ref_id, password_hash, is_active, must_change_password, failed_attempts, locked_until) "
            "VALUES (?, 'admin', NULL, ?, TRUE, TRUE, 0, NULL)",
            ["admin", admin_hash]
        )

        # 2. Faculty accounts
        faculty_rows = con.execute("SELECT faculty_id FROM FACULTY").fetchall()
        default_fac_hash = hash_password("Faculty@123")
        for (fac_id,) in faculty_rows:
            con.execute(
                "INSERT INTO USER_ACCOUNT (user_id, role, ref_id, password_hash, is_active, must_change_password, failed_attempts, locked_until) "
                "VALUES (?, 'faculty', ?, ?, TRUE, TRUE, 0, NULL)",
                [str(fac_id), int(fac_id), default_fac_hash]
            )

        # 3. Student accounts
        student_rows = con.execute("SELECT student_id FROM STUDENT").fetchall()
        default_stu_hash = hash_password("Student@123")
        for (stu_id,) in student_rows:
            con.execute(
                "INSERT INTO USER_ACCOUNT (user_id, role, ref_id, password_hash, is_active, must_change_password, failed_attempts, locked_until) "
                "VALUES (?, 'student', ?, ?, TRUE, TRUE, 0, NULL)",
                [str(stu_id), int(stu_id), default_stu_hash]
            )

        print(f"Successfully seeded USER_ACCOUNT: 1 admin, {len(faculty_rows)} faculty, {len(student_rows)} students.")
    finally:
        if should_close:
            con.close()


# ============================================================================
# User Fetching and Authentication Logic
# ============================================================================

def get_user_by_id(user_id: str) -> Optional[dict]:
    with db_lock:
        con = get_connection()
        try:
            cur = con.execute(
                "SELECT user_id, role, ref_id, password_hash, is_active, must_change_password, failed_attempts, locked_until "
                "FROM USER_ACCOUNT WHERE user_id = ?",
                [user_id]
            )
            row = cur.fetchone()
            if not row:
                return None
            desc = cur.description
            user_data = serialize_row(desc, row)

            # Attach human-readable display name and email if linked
            name = "System Administrator"
            email = None
            if user_data["role"] == "student" and user_data["ref_id"] is not None:
                s_row = con.execute("SELECT student_name, email FROM STUDENT WHERE student_id = ?", [user_data["ref_id"]]).fetchone()
                if s_row:
                    name, email = s_row[0], s_row[1]
            elif user_data["role"] == "faculty" and user_data["ref_id"] is not None:
                f_row = con.execute("SELECT faculty_name, email FROM FACULTY WHERE faculty_id = ?", [user_data["ref_id"]]).fetchone()
                if f_row:
                    name, email = f_row[0], f_row[1]

            user_data["name"] = name
            user_data["email"] = email
            return user_data
        finally:
            con.close()


# ============================================================================
# Authorization Dependencies
# ============================================================================

async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and validate current authenticated user from session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session_data = decode_session_token(token)
    if not session_data or "user_id" not in session_data:
        return None

    user = get_user_by_id(session_data["user_id"])
    if not user or not user["is_active"]:
        return None
    return user


async def require_login(request: Request) -> dict:
    user = await get_current_user(request)
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Please sign in."
            )
        # Web page route: redirect to login
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user


def require_role(allowed_roles: Union[str, List[str]]):
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    async def role_checker(request: Request, user: dict = Depends(require_login)) -> dict:
        if user["role"] not in allowed_roles:
            if request.url.path.startswith("/api/"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Access restricted to {', '.join(allowed_roles)}."
                )
            # Redirect to their own portal if trying to access unauthorized web page
            target_portal = f"/{user['role']}"
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": target_portal}
            )
        return user

    return role_checker


# ============================================================================
# Auth Endpoints
# ============================================================================

@auth_router.post("/login")
async def login(request: Request, response: Response):
    data = await request.json()
    user_id = str(data.get("user_id", "")).strip()
    password = str(data.get("password", ""))

    if not user_id or not password:
        raise HTTPException(status_code=400, detail="Login ID and password are required.")

    user = get_user_by_id(user_id)
    generic_error = "Invalid login ID or password."

    if not user:
        # Dummy verification to prevent timing attack
        verify_password("dummy", hash_password("dummy"))
        raise HTTPException(status_code=400, detail=generic_error)

    # Check brute-force lockout
    now = datetime.now(timezone.utc)
    if user.get("locked_until"):
        try:
            locked_until_dt = datetime.fromisoformat(str(user["locked_until"]))
            if locked_until_dt.tzinfo is None:
                locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
            if now < locked_until_dt:
                minutes_left = max(1, int((locked_until_dt - now).total_seconds() / 60))
                raise HTTPException(
                    status_code=400,
                    detail=f"Account is temporarily locked due to multiple failed login attempts. Please try again in {minutes_left} minute(s)."
                )
        except HTTPException:
            raise
        except Exception:
            pass

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact an administrator.")

    # Verify password
    if not verify_password(password, user["password_hash"]):
        # Increment failed attempts
        with db_lock:
            con = get_connection()
            try:
                new_attempts = user.get("failed_attempts", 0) + 1
                new_lock = None
                if new_attempts >= LOCKOUT_THRESHOLD:
                    new_lock = (now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
                    new_attempts = 0
                con.execute(
                    "UPDATE USER_ACCOUNT SET failed_attempts = ?, locked_until = ? WHERE user_id = ?",
                    [new_attempts, new_lock, user_id]
                )
            finally:
                con.close()
        raise HTTPException(status_code=400, detail=generic_error)

    # Login successful: reset failed attempts
    with db_lock:
        con = get_connection()
        try:
            con.execute(
                "UPDATE USER_ACCOUNT SET failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
                [user_id]
            )
        finally:
            con.close()

    # Create session cookie
    session_payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "ref_id": user["ref_id"]
    }
    set_session_cookie(response, request, session_payload)

    log_audit(user["user_id"], user["role"], "LOGIN", "SESSION", "User signed in successfully")

    portal_map = {
        "admin": "/admin",
        "faculty": "/faculty",
        "student": "/student"
    }

    return {
        "success": True,
        "message": "Login successful.",
        "redirect": portal_map.get(user["role"], "/login"),
        "user": {
            "user_id": user["user_id"],
            "role": user["role"],
            "name": user["name"],
            "ref_id": user["ref_id"],
            "must_change_password": bool(user["must_change_password"])
        }
    }


@auth_router.post("/logout")
async def logout(response: Response, current_user: Optional[dict] = Depends(get_current_user)):
    if current_user:
        log_audit(current_user["user_id"], current_user["role"], "LOGOUT", "SESSION", "User logged out")
    clear_session_cookie(response)
    return {"success": True, "redirect": "/login"}


@auth_router.get("/me")
async def get_me(current_user: dict = Depends(require_login)):
    return {
        "user_id": current_user["user_id"],
        "role": current_user["role"],
        "name": current_user["name"],
        "email": current_user.get("email"),
        "ref_id": current_user["ref_id"],
        "must_change_password": bool(current_user["must_change_password"])
    }


@auth_router.post("/change-password")
async def change_password(request: Request, current_user: dict = Depends(require_login)):
    data = await request.json()
    current_pass = str(data.get("current_password", ""))
    new_pass = str(data.get("new_password", ""))

    if not current_pass or not new_pass:
        raise HTTPException(status_code=400, detail="Both current and new passwords are required.")

    if len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")

    if not verify_password(current_pass, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    new_hash = hash_password(new_pass)
    with db_lock:
        con = get_connection()
        try:
            con.execute(
                "UPDATE USER_ACCOUNT SET password_hash = ?, must_change_password = FALSE WHERE user_id = ?",
                [new_hash, current_user["user_id"]]
            )
        finally:
            con.close()

    log_audit(current_user["user_id"], current_user["role"], "PASSWORD_CHANGE", "USER_ACCOUNT", "Password changed successfully")

    return {
        "success": True,
        "message": "Password updated successfully."
    }

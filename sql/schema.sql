-- ============================================================================
-- ABC UNIVERSITY - DUCKDB COMPATIBLE SCHEMA
-- 13 Tables preserving all original columns, types, PKs, FKs, and constraints
-- ============================================================================

CREATE TABLE IF NOT EXISTS DEPARTMENT (
    dept_id         INTEGER PRIMARY KEY,
    dept_name       VARCHAR(100) NOT NULL UNIQUE,
    hod_name        VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS PROGRAM (
    program_id      INTEGER PRIMARY KEY,
    program_name    VARCHAR(100) NOT NULL,
    program_level   VARCHAR(20) CHECK (program_level IN ('UG','PG','PhD')),
    dept_id         INTEGER NOT NULL,
    duration_years  INTEGER NOT NULL,
    CONSTRAINT fk_program_dept FOREIGN KEY (dept_id) REFERENCES DEPARTMENT(dept_id)
);

CREATE TABLE IF NOT EXISTS STUDENT (
    student_id            INTEGER PRIMARY KEY,
    student_name          VARCHAR(100) NOT NULL,
    dob                   DATE,
    gender                VARCHAR(10) CHECK (gender IN ('Male','Female','Other')),
    contact_number        VARCHAR(15),
    email                 VARCHAR(100) UNIQUE,
    year_of_study         INTEGER CHECK (year_of_study BETWEEN 1 AND 5),
    program_id            INTEGER NOT NULL,
    dept_id               INTEGER NOT NULL,
    academic_performance  DECIMAL(5,2) DEFAULT 0,
    CONSTRAINT fk_student_program FOREIGN KEY (program_id) REFERENCES PROGRAM(program_id),
    CONSTRAINT fk_student_dept FOREIGN KEY (dept_id) REFERENCES DEPARTMENT(dept_id)
);

CREATE TABLE IF NOT EXISTS FACULTY (
    faculty_id      INTEGER PRIMARY KEY,
    faculty_name    VARCHAR(100) NOT NULL,
    dept_id         INTEGER NOT NULL,
    faculty_type    VARCHAR(20) CHECK (faculty_type IN ('Permanent','Adjunct','Visiting')),
    designation     VARCHAR(50),
    contact_number  VARCHAR(15),
    email           VARCHAR(100) UNIQUE,
    CONSTRAINT fk_faculty_dept FOREIGN KEY (dept_id) REFERENCES DEPARTMENT(dept_id)
);

CREATE TABLE IF NOT EXISTS COURSE (
    course_id       INTEGER PRIMARY KEY,
    course_name     VARCHAR(100) NOT NULL,
    credits         INTEGER NOT NULL,
    semester        INTEGER NOT NULL,
    dept_id         INTEGER NOT NULL,
    faculty_id      INTEGER,
    CONSTRAINT fk_course_dept FOREIGN KEY (dept_id) REFERENCES DEPARTMENT(dept_id),
    CONSTRAINT fk_course_faculty FOREIGN KEY (faculty_id) REFERENCES FACULTY(faculty_id)
);

CREATE TABLE IF NOT EXISTS ENROLLMENT (
    enrollment_id   INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL,
    course_id       INTEGER NOT NULL,
    semester        INTEGER NOT NULL,
    academic_year   VARCHAR(9) NOT NULL,
    CONSTRAINT fk_enroll_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id),
    CONSTRAINT fk_enroll_course FOREIGN KEY (course_id) REFERENCES COURSE(course_id),
    CONSTRAINT uq_enrollment UNIQUE (student_id, course_id, academic_year)
);

CREATE TABLE IF NOT EXISTS ASSESSMENT (
    assessment_id   INTEGER PRIMARY KEY,
    course_id       INTEGER NOT NULL,
    assessment_type VARCHAR(30) CHECK (assessment_type IN ('Assignment','Quiz','Lab','Mid-Semester','End-Semester')),
    max_marks       INTEGER NOT NULL,
    CONSTRAINT fk_assess_course FOREIGN KEY (course_id) REFERENCES COURSE(course_id)
);

CREATE TABLE IF NOT EXISTS EXAMINATION_RESULT (
    result_id        INTEGER PRIMARY KEY,
    student_id       INTEGER NOT NULL,
    course_id        INTEGER NOT NULL,
    assessment_id    INTEGER NOT NULL,
    marks_obtained   DECIMAL(5,2) NOT NULL,
    result_status    VARCHAR(10) CHECK (result_status IN ('Pass','Fail')),
    CONSTRAINT fk_result_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id),
    CONSTRAINT fk_result_course FOREIGN KEY (course_id) REFERENCES COURSE(course_id),
    CONSTRAINT fk_result_assessment FOREIGN KEY (assessment_id) REFERENCES ASSESSMENT(assessment_id)
);

CREATE TABLE IF NOT EXISTS ATTENDANCE (
    attendance_id           INTEGER PRIMARY KEY,
    student_id              INTEGER NOT NULL,
    course_id               INTEGER NOT NULL,
    classes_held            INTEGER NOT NULL,
    classes_attended        INTEGER NOT NULL,
    attendance_percentage   DECIMAL(5,2),
    CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id),
    CONSTRAINT fk_att_course FOREIGN KEY (course_id) REFERENCES COURSE(course_id)
);

CREATE TABLE IF NOT EXISTS SCHOLARSHIP (
    scholarship_id        INTEGER PRIMARY KEY,
    student_id            INTEGER NOT NULL,
    scholarship_name      VARCHAR(100) NOT NULL,
    amount                DECIMAL(10,2),
    eligibility_criteria  VARCHAR(200),
    status                VARCHAR(20) CHECK (status IN ('Active','Inactive','Pending')),
    CONSTRAINT fk_schol_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id)
);

CREATE TABLE IF NOT EXISTS HOSTEL (
    hostel_id       INTEGER PRIMARY KEY,
    hostel_name     VARCHAR(50) NOT NULL,
    room_no         VARCHAR(10) NOT NULL,
    student_id      INTEGER UNIQUE,
    CONSTRAINT fk_hostel_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id)
);

CREATE TABLE IF NOT EXISTS INTERNSHIP (
    internship_id   INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL,
    company_name    VARCHAR(100) NOT NULL,
    duration_weeks  INTEGER,
    start_date      DATE,
    end_date        DATE,
    CONSTRAINT fk_intern_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id)
);

CREATE TABLE IF NOT EXISTS RESEARCH_PROJECT (
    project_id      INTEGER PRIMARY KEY,
    student_id      INTEGER NOT NULL,
    faculty_id      INTEGER NOT NULL,
    project_title   VARCHAR(200) NOT NULL,
    start_date      DATE,
    end_date        DATE,
    status          VARCHAR(20) CHECK (status IN ('Ongoing','Completed')),
    CONSTRAINT fk_research_student FOREIGN KEY (student_id) REFERENCES STUDENT(student_id),
    CONSTRAINT fk_research_faculty FOREIGN KEY (faculty_id) REFERENCES FACULTY(faculty_id)
);

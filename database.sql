-- ============================================================================
-- EduTrack - Student Performance Analysis System
-- Database Schema and Default Seed Data
-- ============================================================================

-- For local MySQL setups, uncomment the following two lines if needed:
-- CREATE DATABASE IF NOT EXISTS student_performance_db;
-- USE student_performance_db;

-- 1. Students Table
CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    section VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Subjects Table
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL UNIQUE,
    max_marks INT NOT NULL DEFAULT 100,
    pass_marks INT NOT NULL DEFAULT 40
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Marks Table
CREATE TABLE IF NOT EXISTS marks (
    mark_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    subject_id INT NOT NULL,
    assessment VARCHAR(30) NOT NULL,
    marks_obtained DECIMAL(5,2) NOT NULL,
    max_marks INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_subject_assessment UNIQUE (student_id, subject_id, assessment),
    CONSTRAINT fk_marks_student FOREIGN KEY (student_id)
        REFERENCES students(student_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_marks_subject FOREIGN KEY (subject_id)
        REFERENCES subjects(subject_id)
        ON DELETE RESTRICT,
    CHECK (marks_obtained >= 0),
    CHECK (marks_obtained <= max_marks),
    CHECK (max_marks > 0),
    CHECK (assessment IN ('Internal 1', 'Internal 2', 'Semester Exam'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Initial Subject Configuration
INSERT IGNORE INTO subjects (subject_name, max_marks, pass_marks) VALUES
    ('Java', 100, 40),
    ('Python', 100, 40),
    ('DBMS', 100, 40),
    ('Mathematics', 100, 40);

-- ============================================================================
-- Optional Demonstration Seed Data (uncomment if desired)
-- ============================================================================
-- INSERT IGNORE INTO students (roll_no, name, section) VALUES
--     ('22CS001', 'Aarav Sharma', 'CSE-A'),
--     ('22CS002', 'Diya Patel', 'CSE-A'),
--     ('22CS003', 'Karthik Raja', 'CSE-B'),
--     ('22CS004', 'Meera Nair', 'CSE-B'),
--     ('22CS005', 'Rohan Verma', 'CSE-A');

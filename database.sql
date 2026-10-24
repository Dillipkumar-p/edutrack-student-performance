
CREATE DATABASE IF NOT EXISTS student_performance_db;

USE student_performance_db;

CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    section VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL UNIQUE,
    max_marks INT NOT NULL DEFAULT 100,
    pass_marks INT NOT NULL DEFAULT 40
);

CREATE TABLE IF NOT EXISTS marks (
    mark_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    subject_id INT NOT NULL,
    assessment VARCHAR(30) NOT NULL,
    marks_obtained DECIMAL(5,2) NOT NULL,
    max_marks INT NOT NULL,
    UNIQUE (student_id, subject_id, assessment),
    FOREIGN KEY (student_id)
        REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (subject_id)
        REFERENCES subjects(subject_id)
        ON DELETE RESTRICT,
    CHECK (marks_obtained >= 0),
    CHECK (marks_obtained <= max_marks),
    CHECK (max_marks > 0),
    CHECK (
        assessment IN (
            'Internal 1',
            'Internal 2',
            'Semester Exam'
        )
    )
);

INSERT IGNORE INTO subjects
    (subject_name, max_marks, pass_marks)
VALUES
    ('Java', 100, 40),
    ('Python', 100, 40),
    ('DBMS', 100, 40),
    ('Mathematics', 100, 40);

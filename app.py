"""
EduTrack - Student Performance Analysis System
Flask Web Application with MySQL Backend.
Designed for local development and direct deployment to Render.
"""

import os
import io
import base64
import logging
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    g
)

# Use non-interactive Agg backend for headless server environments
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Database helper module
from db import (
    get_db,
    close_db,
    query_db,
    execute_db,
    init_db,
    seed_sample_data,
    get_db_connection,
    DRIVER
)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Fallback secret key to ensure app never crashes if FLASK_SECRET_KEY is missing on Render
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "edutrack-secret-key-production-safe-3f98a21b4e"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edutrack")

# Register database connection teardown
app.teardown_appcontext(close_db)


# Safe automatic database initialization on first startup
_db_initialized = False

@app.before_request
def auto_init_database():
    """Ensure database tables exist before handling requests."""
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.warning("Could not auto-initialize database on startup: %s", e)


def get_max_marks(assessment):
    """Return the maximum allowable marks for a given assessment type."""
    if assessment in ("Internal 1", "Internal 2"):
        return 50
    return 100


def get_pass_marks(assessment, max_marks=None):
    """Return the passing marks based on assessment or max_marks."""
    if assessment in ("Internal 1", "Internal 2") or max_marks == 50:
        return 20
    return 40


def load_students():
    """Fetch all students ordered by ID."""
    return query_db("""
        SELECT student_id AS id, roll_no, name, section
        FROM students
        ORDER BY student_id ASC
    """)


def load_subjects():
    """Fetch all subjects mapped by subject name."""
    rows = query_db("""
        SELECT subject_name, max_marks, pass_marks
        FROM subjects
        ORDER BY subject_id ASC
    """)
    return {
        row["subject_name"]: {
            "max_marks": row["max_marks"],
            "pass_marks": row["pass_marks"]
        }
        for row in rows
    }


# ============================================================================
# 1. DASHBOARD
# ============================================================================

@app.route("/")
def dashboard():
    """Main dashboard displaying high-level performance metrics."""
    student_count_row = query_db("SELECT COUNT(*) AS total FROM students", one=True)
    total_students = student_count_row["total"] if student_count_row else 0

    stats = query_db("""
        SELECT
            COUNT(*) AS total_marks,
            SUM(
                CASE
                    WHEN m.marks_obtained >= (CASE WHEN m.max_marks = 50 THEN 20 ELSE 40 END)
                    THEN 1
                    ELSE 0
                END
            ) AS passed_marks,
            COALESCE(SUM(m.marks_obtained), 0) AS total_obtained,
            COALESCE(SUM(m.max_marks), 0) AS total_possible
        FROM marks AS m
    """, one=True)

    total_marks = stats["total_marks"] if stats else 0
    passed_marks = stats["passed_marks"] or 0 if stats else 0
    total_obtained = float(stats["total_obtained"]) if stats else 0.0
    total_possible = float(stats["total_possible"]) if stats else 0.0

    if total_marks > 0 and total_possible > 0:
        pass_percentage = round((passed_marks / total_marks) * 100, 1)
        class_average = round((total_obtained / total_possible) * 100, 1)
    else:
        pass_percentage = 0.0
        class_average = 0.0

    top_row = query_db("""
        SELECT s.name,
               SUM(m.marks_obtained) AS obtained,
               SUM(m.max_marks) AS possible
        FROM students AS s
        JOIN marks AS m ON s.student_id = m.student_id
        GROUP BY s.student_id, s.name
        HAVING SUM(m.max_marks) > 0
        ORDER BY (SUM(m.marks_obtained) / SUM(m.max_marks)) DESC, s.name ASC
        LIMIT 1
    """, one=True)

    top_performer = top_row["name"] if top_row else "N/A"

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        total_students=total_students,
        pass_percentage=pass_percentage,
        class_average=class_average,
        top_performer=top_performer
    )


# ============================================================================
# 2. STUDENTS MANAGEMENT
# ============================================================================

@app.route("/students")
def students_page():
    """List students with search filter support."""
    search = request.args.get("search", "").strip()

    if search:
        search_pattern = f"%{search}%"
        students = query_db("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            WHERE roll_no LIKE %s
               OR name LIKE %s
               OR section LIKE %s
            ORDER BY student_id ASC
        """, (search_pattern, search_pattern, search_pattern))
    else:
        students = query_db("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            ORDER BY student_id ASC
        """)

    student_count_row = query_db("SELECT COUNT(*) AS total FROM students", one=True)
    total_students = student_count_row["total"] if student_count_row else 0

    return render_template(
        "students.html",
        active_page="students",
        students=students,
        search=search,
        total_students=total_students
    )


@app.route("/students/add", methods=["POST"])
def add_student():
    """Add a new student record."""
    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()
    section = request.form.get("section", "").strip().upper()

    if not roll_no or not name or not section:
        flash("Please fill in all fields (Roll Number, Name, Section).", "error")
        return redirect(url_for("students_page"))

    # Check for existing roll number
    existing = query_db(
        "SELECT student_id FROM students WHERE roll_no = %s",
        (roll_no,),
        one=True
    )
    if existing:
        flash(f"Roll number '{roll_no}' already exists. Please use a unique roll number.", "error")
        return redirect(url_for("students_page"))

    try:
        execute_db("""
            INSERT INTO students (roll_no, name, section)
            VALUES (%s, %s, %s)
        """, (roll_no, name, section))
        flash(f"Student '{name}' added successfully!", "success")
    except Exception as e:
        logger.exception("Error adding student: %s", e)
        flash("Could not save the student due to a database error.", "error")

    return redirect(url_for("students_page"))


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    """Edit student details."""
    student = query_db(
        "SELECT student_id AS id, roll_no, name, section FROM students WHERE student_id = %s",
        (student_id,),
        one=True
    )

    if student is None:
        flash("Student record not found.", "error")
        return redirect(url_for("students_page"))

    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        section = request.form.get("section", "").strip().upper()

        if not roll_no or not name or not section:
            flash("Please fill in all fields.", "error")
            return render_template("edit_student.html", active_page="students", student=student)

        # Check for roll number collision with another student
        existing = query_db(
            "SELECT student_id FROM students WHERE roll_no = %s AND student_id != %s",
            (roll_no, student_id),
            one=True
        )
        if existing:
            flash(f"Roll number '{roll_no}' is already used by another student.", "error")
            return render_template("edit_student.html", active_page="students", student=student)

        try:
            execute_db("""
                UPDATE students
                SET roll_no = %s, name = %s, section = %s
                WHERE student_id = %s
            """, (roll_no, name, section, student_id))
            flash("Student details updated successfully!", "success")
            return redirect(url_for("students_page"))
        except Exception as e:
            logger.exception("Error updating student: %s", e)
            flash("Could not update student record due to a database error.", "error")

    return render_template("edit_student.html", active_page="students", student=student)


@app.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    """Delete a student and cascade delete associated marks."""
    try:
        rowcount, _ = execute_db(
            "DELETE FROM students WHERE student_id = %s",
            (student_id,)
        )
        if rowcount > 0:
            flash("Student deleted successfully!", "success")
        else:
            flash("Student not found.", "error")
    except Exception as e:
        logger.exception("Error deleting student: %s", e)
        flash("Could not delete student record.", "error")

    return redirect(url_for("students_page"))


# ============================================================================
# 3. MARKS MANAGEMENT
# ============================================================================

@app.route("/marks")
def marks_page():
    """List entered marks and provide entry form."""
    search = request.args.get("search", "").strip()

    if search:
        search_pattern = f"%{search}%"
        display_marks = query_db("""
            SELECT m.mark_id AS id,
                   m.student_id,
                   s.roll_no,
                   s.name AS student_name,
                   sub.subject_name AS subject,
                   m.assessment,
                   m.marks_obtained,
                   m.max_marks,
                   sub.pass_marks
            FROM marks AS m
            JOIN students AS s ON m.student_id = s.student_id
            JOIN subjects AS sub ON m.subject_id = sub.subject_id
            WHERE s.roll_no LIKE %s
               OR s.name LIKE %s
               OR sub.subject_name LIKE %s
               OR m.assessment LIKE %s
            ORDER BY m.mark_id DESC
        """, (search_pattern, search_pattern, search_pattern, search_pattern))
    else:
        display_marks = query_db("""
            SELECT m.mark_id AS id,
                   m.student_id,
                   s.roll_no,
                   s.name AS student_name,
                   sub.subject_name AS subject,
                   m.assessment,
                   m.marks_obtained,
                   m.max_marks,
                   sub.pass_marks
            FROM marks AS m
            JOIN students AS s ON m.student_id = s.student_id
            JOIN subjects AS sub ON m.subject_id = sub.subject_id
            ORDER BY m.mark_id DESC
        """)

    return render_template(
        "marks.html",
        active_page="marks",
        all_students=load_students(),
        subjects=load_subjects(),
        marks=display_marks,
        search=search
    )


@app.route("/marks/add", methods=["POST"])
def add_mark():
    """Save assessment marks for a student."""
    try:
        student_id = int(request.form.get("student_id", ""))
        subject_name = request.form.get("subject", "").strip()
        assessment = request.form.get("assessment", "").strip()
        marks_obtained = float(request.form.get("marks_obtained", ""))
    except (ValueError, TypeError):
        flash("Please enter valid student and numeric mark values.", "error")
        return redirect(url_for("marks_page"))

    if assessment not in ("Internal 1", "Internal 2", "Semester Exam"):
        flash("Please select a valid assessment examination.", "error")
        return redirect(url_for("marks_page"))

    maximum = get_max_marks(assessment)
    if not (0 <= marks_obtained <= maximum):
        flash(f"Marks must be between 0 and {maximum} for {assessment}.", "error")
        return redirect(url_for("marks_page"))

    # Validate student
    student = query_db(
        "SELECT student_id, name FROM students WHERE student_id = %s",
        (student_id,),
        one=True
    )
    if not student:
        flash("Please select a valid student from the list.", "error")
        return redirect(url_for("marks_page"))

    # Validate subject
    subject_row = query_db(
        "SELECT subject_id FROM subjects WHERE subject_name = %s",
        (subject_name,),
        one=True
    )
    if not subject_row:
        flash("Please select a valid subject.", "error")
        return redirect(url_for("marks_page"))

    subject_id = subject_row["subject_id"]

    # Check for duplicate mark entry
    existing_mark = query_db("""
        SELECT mark_id FROM marks
        WHERE student_id = %s AND subject_id = %s AND assessment = %s
    """, (student_id, subject_id, assessment), one=True)

    if existing_mark:
        flash(
            f"Marks for {student['name']} in {subject_name} ({assessment}) already exist. "
            f"Please edit the existing record below.",
            "error"
        )
        return redirect(url_for("marks_page"))

    try:
        execute_db("""
            INSERT INTO marks (student_id, subject_id, assessment, marks_obtained, max_marks)
            VALUES (%s, %s, %s, %s, %s)
        """, (student_id, subject_id, assessment, marks_obtained, maximum))
        flash("Marks saved successfully!", "success")
    except Exception as e:
        logger.exception("Error saving marks: %s", e)
        flash("Could not save marks due to a database error.", "error")

    return redirect(url_for("marks_page"))


@app.route("/marks/edit/<int:mark_id>", methods=["GET", "POST"])
def edit_mark(mark_id):
    """Edit an existing marks record."""
    mark = query_db("""
        SELECT m.mark_id AS id,
               m.student_id,
               sub.subject_name AS subject,
               m.assessment,
               m.marks_obtained,
               m.max_marks,
               sub.pass_marks
        FROM marks AS m
        JOIN subjects AS sub ON m.subject_id = sub.subject_id
        WHERE m.mark_id = %s
    """, (mark_id,), one=True)

    if mark is None:
        flash("Marks record not found.", "error")
        return redirect(url_for("marks_page"))

    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
            subject_name = request.form.get("subject", "").strip()
            assessment = request.form.get("assessment", "").strip()
            marks_obtained = float(request.form.get("marks_obtained", ""))
        except (ValueError, TypeError):
            flash("Please enter valid marks details.", "error")
            return redirect(url_for("edit_mark", mark_id=mark_id))

        if assessment not in ("Internal 1", "Internal 2", "Semester Exam"):
            flash("Please select a valid assessment.", "error")
            return redirect(url_for("edit_mark", mark_id=mark_id))

        maximum = get_max_marks(assessment)
        if not (0 <= marks_obtained <= maximum):
            flash(f"Marks must be between 0 and {maximum}.", "error")
            return redirect(url_for("edit_mark", mark_id=mark_id))

        student = query_db("SELECT student_id FROM students WHERE student_id = %s", (student_id,), one=True)
        subject_row = query_db("SELECT subject_id FROM subjects WHERE subject_name = %s", (subject_name,), one=True)

        if not student or not subject_row:
            flash("Invalid student or subject specified.", "error")
            return redirect(url_for("edit_mark", mark_id=mark_id))

        subject_id = subject_row["subject_id"]

        # Prevent duplicate clash with another record
        existing = query_db("""
            SELECT mark_id FROM marks
            WHERE student_id = %s AND subject_id = %s AND assessment = %s AND mark_id != %s
        """, (student_id, subject_id, assessment, mark_id), one=True)

        if existing:
            flash("Another record already has marks for this student, subject, and assessment.", "error")
            return redirect(url_for("edit_mark", mark_id=mark_id))

        try:
            execute_db("""
                UPDATE marks
                SET student_id = %s,
                    subject_id = %s,
                    assessment = %s,
                    marks_obtained = %s,
                    max_marks = %s
                WHERE mark_id = %s
            """, (student_id, subject_id, assessment, marks_obtained, maximum, mark_id))
            flash("Marks record updated successfully!", "success")
            return redirect(url_for("marks_page"))
        except Exception as e:
            logger.exception("Error updating mark: %s", e)
            flash("Database error while updating marks.", "error")

    return render_template(
        "edit_mark.html",
        active_page="marks",
        mark=mark,
        all_students=load_students(),
        subjects=load_subjects()
    )


@app.route("/marks/delete/<int:mark_id>", methods=["POST"])
def delete_mark(mark_id):
    """Delete a marks entry."""
    try:
        rowcount, _ = execute_db("DELETE FROM marks WHERE mark_id = %s", (mark_id,))
        if rowcount > 0:
            flash("Marks record deleted successfully!", "success")
        else:
            flash("Marks record not found.", "error")
    except Exception as e:
        logger.exception("Error deleting mark: %s", e)
        flash("Could not delete the marks record.", "error")

    return redirect(url_for("marks_page"))


# ============================================================================
# 4. RESULTS VIEW
# ============================================================================

@app.route("/results")
def results():
    """Detailed subject-wise results for a selected student and assessment."""
    selected_id = request.args.get("student_id", type=int)
    assessment = request.args.get("assessment", "Internal 1")
    assessments = ["Internal 1", "Internal 2", "Semester Exam"]

    if assessment not in assessments:
        assessment = "Internal 1"

    all_students = load_students()
    selected_student = next(
        (s for s in all_students if s["id"] == selected_id),
        None
    ) if selected_id else None

    subject_results = []
    total_obtained = 0.0
    total_maximum = 0
    any_failed = False

    if selected_student:
        student_marks = query_db("""
            SELECT sub.subject_name AS subject,
                   m.marks_obtained AS obtained,
                   m.max_marks AS maximum
            FROM marks AS m
            JOIN subjects AS sub ON m.subject_id = sub.subject_id
            WHERE m.student_id = %s
              AND m.assessment = %s
            ORDER BY sub.subject_id ASC, m.mark_id ASC
        """, (selected_id, assessment))

        for mark in student_marks:
            obtained = float(mark["obtained"])
            maximum = int(mark["maximum"])
            percentage = round((obtained / maximum) * 100, 2) if maximum > 0 else 0.0

            pass_threshold = get_pass_marks(assessment, maximum)
            passed = obtained >= pass_threshold

            if not passed:
                grade = "F"
                any_failed = True
            elif percentage >= 90:
                grade = "A+"
            elif percentage >= 80:
                grade = "A"
            elif percentage >= 70:
                grade = "B"
            elif percentage >= 60:
                grade = "C"
            elif percentage >= 50:
                grade = "D"
            else:
                grade = "E"

            subject_results.append({
                "subject": mark["subject"],
                "obtained": obtained,
                "maximum": maximum,
                "percentage": percentage,
                "grade": grade,
                "status": "Pass" if passed else "Fail"
            })

            total_obtained += obtained
            total_maximum += maximum

    if subject_results and total_maximum > 0:
        overall_percentage = round((total_obtained / total_maximum) * 100, 2)
        overall_average = round(total_obtained / len(subject_results), 2)
        overall_status = "Fail" if any_failed else "Pass"
    else:
        overall_percentage = 0.0
        overall_average = 0.0
        overall_status = "No marks"

    return render_template(
        "results.html",
        active_page="results",
        all_students=all_students,
        selected_student=selected_student,
        assessment=assessment,
        assessments=assessments,
        subject_results=subject_results,
        total_obtained=total_obtained,
        total_maximum=total_maximum,
        overall_percentage=overall_percentage,
        overall_average=overall_average,
        overall_status=overall_status
    )


# ============================================================================
# 5. PERFORMANCE ANALYTICS
# ============================================================================

@app.route("/analytics")
def analytics():
    """Visual and aggregate analytics across students for a given assessment."""
    assessment = request.args.get("assessment", "Internal 1")
    assessments = ["Internal 1", "Internal 2", "Semester Exam"]
    expected_subjects = ["Java", "Python", "DBMS", "Mathematics"]

    if assessment not in assessments:
        assessment = "Internal 1"

    pass_threshold = get_pass_marks(assessment)
    max_per_subject = get_max_marks(assessment)

    database_students = load_students()
    assessment_marks = query_db("""
        SELECT m.mark_id AS id,
               m.student_id,
               sub.subject_name AS subject,
               m.assessment,
               m.marks_obtained,
               m.max_marks
        FROM marks AS m
        JOIN subjects AS sub ON m.subject_id = sub.subject_id
        WHERE m.assessment = %s
        ORDER BY m.mark_id ASC
    """, (assessment,))

    subject_data = {
        sub: {"total": 0.0, "count": 0}
        for sub in expected_subjects
    }

    student_data = {
        s["id"]: {
            "id": s["id"],
            "roll_no": s["roll_no"],
            "name": s["name"],
            "section": s["section"],
            "total": 0.0,
            "maximum": 0,
            "subjects": [],
            "recorded_subjects": set(),
            "needs_assistance": False
        }
        for s in database_students
    }

    for mark in assessment_marks:
        sub = mark["subject"]
        s_id = mark["student_id"]

        if sub not in subject_data or s_id not in student_data:
            continue

        obtained = float(mark["marks_obtained"])
        maximum = max_per_subject

        subject_data[sub]["total"] += obtained
        subject_data[sub]["count"] += 1

        student = student_data[s_id]
        student["total"] += obtained
        student["maximum"] += maximum
        student["recorded_subjects"].add(sub)

        passed = obtained >= pass_threshold
        student["subjects"].append({
            "subject": sub,
            "obtained": obtained,
            "maximum": maximum,
            "percentage": round((obtained / maximum) * 100, 2) if maximum else 0.0,
            "status": "Pass" if passed else "Fail"
        })

        if not passed:
            student["needs_assistance"] = True

    student_results = []
    for student in student_data.values():
        student["missing_subjects"] = [
            sub for sub in expected_subjects
            if sub not in student["recorded_subjects"]
        ]
        student["complete"] = (len(student["missing_subjects"]) == 0)
        student["percentage"] = (
            round((student["total"] / student["maximum"]) * 100, 2)
            if student["maximum"] > 0 else 0.0
        )
        student["subjects"].sort(
            key=lambda item: expected_subjects.index(item["subject"])
        )
        student_results.append(student)

    # Toppers: students with all expected subjects complete, ranked by percentage
    complete_students = [s for s in student_results if s["complete"]]
    complete_students.sort(key=lambda s: s["percentage"], reverse=True)
    toppers = complete_students[:3]

    # Students with one or more failed subjects
    assistance_students = [s for s in student_results if s["needs_assistance"]]

    # Students missing one or more subjects
    incomplete_students = [s for s in student_results if not s["complete"]]

    subject_averages = []
    for sub, data in subject_data.items():
        if data["count"] > 0:
            avg = data["total"] / data["count"]
            pct = (avg / max_per_subject) * 100
            subject_averages.append({
                "subject": sub,
                "average": round(avg, 2),
                "maximum": max_per_subject,
                "percentage": round(pct, 2),
                "student_count": data["count"]
            })

    # Render Chart to base64
    chart_image = None
    if subject_averages:
        labels = [item["subject"] for item in subject_averages]
        values = [item["percentage"] for item in subject_averages]

        fig, ax = plt.subplots(figsize=(8, 4), facecolor="#ffffff")
        bars = ax.bar(labels, values, color="#2563eb", width=0.55)
        ax.set_title(f"Subject Average Percentage — {assessment}", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Average Score (%)", fontsize=11)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Annotate percentages on bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1f}%",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center", va="bottom", fontsize=10, fontweight="bold"
            )

        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)

        chart_image = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template(
        "analytics.html",
        active_page="analytics",
        assessment=assessment,
        assessments=assessments,
        subject_averages=subject_averages,
        toppers=toppers,
        assistance_students=assistance_students,
        incomplete_students=incomplete_students,
        total_students=len(database_students),
        complete_count=len(complete_students),
        chart_image=chart_image
    )


# ============================================================================
# 6. SYSTEM UTILITIES & HEALTH CHECK
# ============================================================================

@app.route("/db-test")
@app.route("/health")
def db_health_check():
    """Verify database connection and table status."""
    try:
        s_count = query_db("SELECT COUNT(*) AS c FROM students", one=True)
        m_count = query_db("SELECT COUNT(*) AS c FROM marks", one=True)
        sub_count = query_db("SELECT COUNT(*) AS c FROM subjects", one=True)

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "driver": DRIVER,
            "students_count": s_count["c"] if s_count else 0,
            "subjects_count": sub_count["c"] if sub_count else 0,
            "marks_count": m_count["c"] if m_count else 0
        }), 200
    except Exception as e:
        logger.exception("Database health check failed")
        return jsonify({
            "status": "unhealthy",
            "database": "error",
            "error": str(e)
        }), 500


@app.route("/init-db")
def manual_init_db():
    """Manually trigger schema and subject table creation."""
    try:
        init_db()
        return jsonify({
            "success": True,
            "message": "Database tables and subjects initialized successfully!"
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/seed-demo-data")
def manual_seed_demo():
    """Seed 5 sample students and sample marks for immediate testing."""
    success, msg = seed_sample_data()
    flash(msg, "success" if success else "error")
    return redirect(url_for("dashboard"))


# ============================================================================
# MAIN APPLICATION ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

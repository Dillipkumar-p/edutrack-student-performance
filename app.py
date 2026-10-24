from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import base64
import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.secret_key = "review1-prototype-key"
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv(
            "DB_NAME", "student_performance_db"
        )
    )

students = [
    {"id": 1, "roll_no": "101", "name": "Arun Kumar", "section": "CSE-A"},
    {"id": 2, "roll_no": "102", "name": "Priya Reddy", "section": "CSE-A"},
    {"id": 3, "roll_no": "103", "name": "Rahul Kumar", "section": "CSE-B"},
    {"id": 4, "roll_no": "104", "name": "Sneha Devi", "section": "CSE-B"},
]

next_id = 5

# Temporary marks data
marks = []
next_mark_id = 1

# Subject details for the prototype

subjects = {
    "Java": {"max_marks": 100, "pass_marks": 40},
    "Python": {"max_marks": 100, "pass_marks": 40},
    "DBMS": {"max_marks": 100, "pass_marks": 40},
    "Mathematics": {"max_marks": 100, "pass_marks": 40}
}



def get_max_marks(assessment):
    if assessment in ["Internal 1", "Internal 2"]:
        return 50
    return 100





@app.route("/")
def dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Total students
        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cursor.fetchone()["total"]

        # Calculate marks statistics
        cursor.execute("""
            SELECT
                COUNT(*) AS total_marks,
                SUM(
                    CASE
                        WHEN m.marks_obtained >=
                            CASE
                                WHEN m.max_marks = 50 THEN 20
                                ELSE 40
                            END
                        THEN 1
                        ELSE 0
                    END
                ) AS passed_marks,
                COALESCE(SUM(m.marks_obtained), 0) AS total_obtained,
                COALESCE(SUM(m.max_marks), 0) AS total_possible
            FROM marks AS m
        """)

        stats = cursor.fetchone()

        total_marks = stats["total_marks"]
        passed_marks = stats["passed_marks"] or 0
        total_obtained = float(stats["total_obtained"])
        total_possible = float(stats["total_possible"])

        if total_marks > 0:
            pass_percentage = round(
                (passed_marks / total_marks) * 100, 1
            )
            class_average = round(
                (total_obtained / total_possible) * 100, 1
            ) if total_possible > 0 else 0
        else:
            pass_percentage = 0
            class_average = 0

        # Find the top-performing student
        cursor.execute("""
            SELECT
                s.name,
                SUM(m.marks_obtained) AS obtained,
                SUM(m.max_marks) AS possible
            FROM students AS s
            JOIN marks AS m ON s.student_id = m.student_id
            GROUP BY s.student_id, s.name
            HAVING SUM(m.max_marks) > 0
            ORDER BY
                SUM(m.marks_obtained) / SUM(m.max_marks) DESC,
                s.name ASC
            LIMIT 1
        """)

        top_student = cursor.fetchone()

        top_performer = (
            top_student["name"] if top_student else "N/A"
        )

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        total_students=total_students,
        pass_percentage=pass_percentage,
        class_average=class_average,
        top_performer=top_performer
    )



@app.route("/students")
def students_page():
    search = request.args.get("search", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            WHERE roll_no LIKE %s
               OR name LIKE %s
               OR section LIKE %s
            ORDER BY student_id
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))

        filtered_students = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cursor.fetchone()["total"]

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "students.html",
        active_page="students",
        students=filtered_students,
        search=search,
        total_students=total_students
    )


@app.route("/students/add", methods=["POST"])
def add_student():
    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()
    section = request.form.get("section", "").strip().upper()

    if not roll_no or not name or not section:
        flash("Please fill in all fields.", "error")
        return redirect(url_for("students_page"))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO students (roll_no, name, section)
            VALUES (%s, %s, %s)
        """, (roll_no, name, section))

        connection.commit()
        flash("Student added successfully!", "success")

    except mysql.connector.IntegrityError:
        connection.rollback()
        flash("This roll number already exists.", "error")

    except mysql.connector.Error:
        connection.rollback()
        flash("Could not save the student. Please try again.", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("students_page"))


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            roll_no = request.form.get("roll_no", "").strip()
            name = request.form.get("name", "").strip()
            section = request.form.get("section", "").strip().upper()

            if not roll_no or not name or not section:
                flash("Please fill in all fields.", "error")

            else:
                try:
                    cursor.execute("""
                        UPDATE students
                        SET roll_no = %s, name = %s, section = %s
                        WHERE student_id = %s
                    """, (roll_no, name, section, student_id))

                    if cursor.rowcount == 0:
                        cursor.execute(
                            "SELECT student_id FROM students WHERE student_id = %s",
                            (student_id,)
                        )

                        if cursor.fetchone() is None:
                            flash("Student not found.", "error")
                            return redirect(url_for("students_page"))

                    connection.commit()
                    flash("Student updated successfully!", "success")
                    return redirect(url_for("students_page"))

                except mysql.connector.IntegrityError:
                    connection.rollback()
                    flash("This roll number is already in use.", "error")

                except mysql.connector.Error:
                    connection.rollback()
                    flash("Could not update the student. Please try again.", "error")

        cursor.execute("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            WHERE student_id = %s
        """, (student_id,))

        student = cursor.fetchone()

        if student is None:
            flash("Student not found.", "error")
            return redirect(url_for("students_page"))

        return render_template(
            "edit_student.html",
            active_page="students",
            student=student
        )

    finally:
        cursor.close()
        connection.close()


@app.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM students WHERE student_id = %s",
            (student_id,)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Student deleted successfully!", "success")
        else:
            connection.rollback()
            flash("Student not found.", "error")

    except mysql.connector.Error:
        connection.rollback()
        flash(
            "Could not delete this student. Check whether marks are linked to the record.",
            "error"
        )

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("students_page"))


@app.route("/results")
def results():
    selected_id = request.args.get("student_id", type=int)
    assessment = request.args.get("assessment", "Internal 1")
    assessments = ["Internal 1", "Internal 2", "Semester Exam"]

    if assessment not in assessments:
        assessment = "Internal 1"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            ORDER BY student_id
        """)
        all_students = cursor.fetchall()

        selected_student = next(
            (s for s in all_students if s["id"] == selected_id),
            None
        )

        subject_results = []
        total_obtained = 0
        total_maximum = 0
        any_failed = False

        if selected_student:
            cursor.execute("""
                SELECT sub.subject_name AS subject,
                       m.marks_obtained AS obtained,
                       m.max_marks AS maximum
                FROM marks m
                JOIN subjects sub ON m.subject_id = sub.subject_id
                WHERE m.student_id = %s
                  AND m.assessment = %s
                ORDER BY sub.subject_id, m.mark_id
            """, (selected_id, assessment))

            student_marks = cursor.fetchall()

            for mark in student_marks:
                obtained = float(mark["obtained"])
                maximum = int(mark["maximum"])
                percentage = round(obtained / maximum * 100, 2)

                pass_marks = 20 if maximum == 50 else 40
                passed = obtained >= pass_marks

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

        overall_percentage = (
            round(total_obtained / total_maximum * 100, 2)
            if total_maximum else 0
        )

        overall_average = (
            round(total_obtained / len(subject_results), 2)
            if subject_results else 0
        )

        overall_status = (
            "Fail" if any_failed else "Pass"
        ) if subject_results else "No marks"

    finally:
        cursor.close()
        connection.close()

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


@app.route("/analytics")
def analytics():
    assessment = request.args.get("assessment", "Internal 1")
    assessments = ["Internal 1", "Internal 2", "Semester Exam"]
    expected_subjects = ["Java", "Python", "DBMS", "Mathematics"]

    if assessment not in assessments:
        assessment = "Internal 1"

    pass_marks = 20 if assessment in ["Internal 1", "Internal 2"] else 40
    maximum_per_subject = 50 if assessment in ["Internal 1", "Internal 2"] else 100

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            ORDER BY student_id
        """)
        database_students = cursor.fetchall()

        cursor.execute("""
            SELECT m.mark_id AS id,
                   m.student_id,
                   sub.subject_name AS subject,
                   m.assessment,
                   m.marks_obtained,
                   m.max_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            WHERE m.assessment = %s
            ORDER BY m.mark_id
        """, (assessment,))
        assessment_marks = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    subject_data = {
        subject: {"total": 0, "count": 0}
        for subject in expected_subjects
    }

    student_data = {
        student["id"]: {
            "id": student["id"],
            "roll_no": student["roll_no"],
            "name": student["name"],
            "section": student["section"],
            "total": 0,
            "maximum": 0,
            "subjects": [],
            "recorded_subjects": set(),
            "needs_assistance": False
        }
        for student in database_students
    }

    latest_marks = {}

    for mark in assessment_marks:
        key = (mark["student_id"], mark["subject"])
        latest_marks[key] = mark

    for mark in latest_marks.values():
        subject = mark["subject"]
        student_id = mark["student_id"]

        if subject not in subject_data or student_id not in student_data:
            continue

        obtained = float(mark["marks_obtained"])
        maximum = maximum_per_subject

        subject_data[subject]["total"] += obtained
        subject_data[subject]["count"] += 1

        student = student_data[student_id]
        student["total"] += obtained
        student["maximum"] += maximum
        student["recorded_subjects"].add(subject)

        percentage = round(obtained / maximum * 100, 2)
        passed = obtained >= pass_marks

        student["subjects"].append({
            "subject": subject,
            "obtained": obtained,
            "maximum": maximum,
            "percentage": percentage,
            "status": "Pass" if passed else "Fail"
        })

        if not passed:
            student["needs_assistance"] = True

    student_results = []

    for student in student_data.values():
        student["missing_subjects"] = [
            subject for subject in expected_subjects
            if subject not in student["recorded_subjects"]
        ]

        student["complete"] = len(student["missing_subjects"]) == 0

        student["percentage"] = (
            round(student["total"] / student["maximum"] * 100, 2)
            if student["maximum"] else 0
        )

        student["subjects"].sort(
            key=lambda item: expected_subjects.index(item["subject"])
        )

        student_results.append(student)

    complete_students = [
        student for student in student_results
        if student["complete"]
    ]
    complete_students.sort(
        key=lambda student: student["percentage"],
        reverse=True
    )
    toppers = complete_students[:3]

    assistance_students = [
        student for student in student_results
        if student["needs_assistance"]
    ]

    incomplete_students = [
        student for student in student_results
        if not student["complete"]
    ]

    subject_averages = []

    for subject, data in subject_data.items():
        if data["count"] > 0:
            average = data["total"] / data["count"]
            percentage = average / maximum_per_subject * 100

            subject_averages.append({
                "subject": subject,
                "average": round(average, 2),
                "maximum": maximum_per_subject,
                "percentage": round(percentage, 2),
                "student_count": data["count"]
            })

    chart_image = None

    if subject_averages:
        labels = [item["subject"] for item in subject_averages]
        values = [item["percentage"] for item in subject_averages]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(labels, values)
        ax.set_title(f"Subject Average Percentage - {assessment}")
        ax.set_ylabel("Average Percentage")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()

        image_buffer = io.BytesIO()
        fig.savefig(image_buffer, format="png", dpi=120)
        plt.close(fig)

        chart_image = base64.b64encode(
            image_buffer.getvalue()
        ).decode("utf-8")

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




def load_students():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT student_id AS id, roll_no, name, section
            FROM students
            ORDER BY student_id
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_subjects():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT subject_name, max_marks, pass_marks
            FROM subjects
            ORDER BY subject_id
        """)
        rows = cursor.fetchall()
        return {
            row["subject_name"]: {
                "max_marks": row["max_marks"],
                "pass_marks": row["pass_marks"]
            }
            for row in rows
        }
    finally:
        cursor.close()
        connection.close()


@app.route("/marks")
def marks_page():
    search = request.args.get("search", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT m.mark_id AS id,
                   m.student_id,
                   s.roll_no,
                   s.name AS student_name,
                   sub.subject_name AS subject,
                   m.assessment,
                   m.marks_obtained,
                   m.max_marks,
                   sub.pass_marks
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            JOIN subjects sub ON m.subject_id = sub.subject_id
            WHERE s.roll_no LIKE %s
               OR s.name LIKE %s
               OR sub.subject_name LIKE %s
               OR m.assessment LIKE %s
            ORDER BY m.mark_id DESC
        """, (
            f"%{search}%", f"%{search}%",
            f"%{search}%", f"%{search}%"
        ))
        display_marks = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

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
    try:
        student_id = int(request.form.get("student_id", ""))
        subject = request.form.get("subject", "").strip()
        assessment = request.form.get("assessment", "").strip()
        marks_obtained = float(request.form.get("marks_obtained", ""))
    except (ValueError, TypeError):
        flash("Please enter valid marks details.", "error")
        return redirect(url_for("marks_page"))

    if assessment not in ["Internal 1", "Internal 2", "Semester Exam"]:
        flash("Please select a valid assessment.", "error")
        return redirect(url_for("marks_page"))

    maximum = get_max_marks(assessment)

    if not 0 <= marks_obtained <= maximum:
        flash(f"Marks must be between 0 and {maximum}.", "error")
        return redirect(url_for("marks_page"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT student_id FROM students WHERE student_id = %s",
            (student_id,)
        )
        if cursor.fetchone() is None:
            flash("Please select a valid student.", "error")
            return redirect(url_for("marks_page"))

        cursor.execute("""
            SELECT subject_id, max_marks, pass_marks
            FROM subjects
            WHERE subject_name = %s
        """, (subject,))
        subject_row = cursor.fetchone()

        if subject_row is None:
            flash("Please select a valid subject.", "error")
            return redirect(url_for("marks_page"))

        cursor.execute("""
            INSERT INTO marks
                (student_id, subject_id, assessment,
                 marks_obtained, max_marks)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id, subject_row["subject_id"],
            assessment, marks_obtained, maximum
        ))

        connection.commit()
        flash("Marks saved successfully!", "success")

    except mysql.connector.Error:
        connection.rollback()
        flash("Could not save marks. Please check the entered details.", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("marks_page"))


@app.route("/marks/edit/<int:mark_id>", methods=["GET", "POST"])
def edit_mark(mark_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            try:
                student_id = int(request.form.get("student_id", ""))
                marks_obtained = float(
                    request.form.get("marks_obtained", "")
                )
            except (ValueError, TypeError):
                flash("Please enter valid marks details.", "error")
                return redirect(url_for("edit_mark", mark_id=mark_id))

            subject = request.form.get("subject", "").strip()
            assessment = request.form.get("assessment", "").strip()

            if assessment not in ["Internal 1", "Internal 2", "Semester Exam"]:
                flash("Please select a valid assessment.", "error")
                return redirect(url_for("edit_mark", mark_id=mark_id))

            maximum = get_max_marks(assessment)

            if not 0 <= marks_obtained <= maximum:
                flash(f"Marks must be between 0 and {maximum}.", "error")
                return redirect(url_for("edit_mark", mark_id=mark_id))

            cursor.execute(
                "SELECT student_id FROM students WHERE student_id = %s",
                (student_id,)
            )
            student_row = cursor.fetchone()

            cursor.execute(
                "SELECT subject_id FROM subjects WHERE subject_name = %s",
                (subject,)
            )
            subject_row = cursor.fetchone()

            if student_row is None or subject_row is None:
                flash("Please select a valid student and subject.", "error")
                return redirect(url_for("edit_mark", mark_id=mark_id))

            cursor.execute("""
                UPDATE marks
                SET student_id = %s,
                    subject_id = %s,
                    assessment = %s,
                    marks_obtained = %s,
                    max_marks = %s
                WHERE mark_id = %s
            """, (
                student_id, subject_row["subject_id"],
                assessment, marks_obtained, maximum, mark_id
            ))

            if cursor.rowcount == 0:
                cursor.execute(
                    "SELECT mark_id FROM marks WHERE mark_id = %s",
                    (mark_id,)
                )
                if cursor.fetchone() is None:
                    connection.rollback()
                    flash("Marks record not found.", "error")
                    return redirect(url_for("marks_page"))

            connection.commit()
            flash("Marks updated successfully!", "success")
            return redirect(url_for("marks_page"))

        cursor.execute("""
    SELECT
        m.mark_id AS id,
        m.student_id,
        sub.subject_name AS subject,
        m.assessment,
        m.marks_obtained,
        m.max_marks,
        sub.pass_marks
    FROM marks AS m
    JOIN subjects AS sub
        ON m.subject_id = sub.subject_id
    WHERE m.mark_id = %s
""", (mark_id,))
        mark = cursor.fetchone()

        if mark is None:
            flash("Marks record not found.", "error")
            return redirect(url_for("marks_page"))

        return render_template(
            "edit_mark.html",
            active_page="marks",
            mark=mark,
            all_students=load_students(),
            subjects=load_subjects()
        )

    except mysql.connector.Error as e:
     connection.rollback()
     print("MARKS EDIT DATABASE ERROR:", e)
     flash("A database error occurred while processing marks.", "error")
     return redirect(url_for("marks_page"))

    finally:
        cursor.close()
        connection.close()


@app.route("/marks/delete/<int:mark_id>", methods=["POST"])
def delete_mark(mark_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM marks WHERE mark_id = %s",
            (mark_id,)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Marks record deleted successfully!", "success")
        else:
            connection.rollback()
            flash("Marks record not found.", "error")

    except mysql.connector.Error:
        connection.rollback()
        flash("Could not delete the marks record.", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("marks_page"))

@app.route("/db-test")
def db_test():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM students")
        count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return f"MySQL connected successfully! Students: {count}"

    except Exception as e:
        return f"MySQL connection failed: {e}", 500

if __name__ == "__main__":
    app.run(debug=True)
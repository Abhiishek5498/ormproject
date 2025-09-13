from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)


# Database setup
def init_db():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     name
                     TEXT,
                     roll
                     TEXT
                     UNIQUE,
                     department
                     TEXT
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance
    (
        id
        INTEGER
        PRIMARY
        KEY
        AUTOINCREMENT,
        student_id
        INTEGER,
        check_in
        TEXT,
        check_out
        TEXT,
        FOREIGN
        KEY
                 (
        student_id
                 ) REFERENCES students
                 (
                     id
                 )
        )''')
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # total students
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    # today's date
    today = datetime.now().strftime("%Y-%m-%d")

    # present students
    c.execute("SELECT COUNT(DISTINCT student_id) FROM attendance WHERE DATE(check_in)=?", (today,))
    present_today = c.fetchone()[0]

    # absent = total - present
    absent_today = total_students - present_today

    # average hours
    c.execute("SELECT check_in, check_out FROM attendance WHERE DATE(check_in)=?", (today,))
    records = c.fetchall()
    total_hours = 0
    for rec in records:
        if rec[1]:  # check_out exists
            check_in_time = datetime.strptime(rec[0], "%Y-%m-%d %H:%M:%S")
            check_out_time = datetime.strptime(rec[1], "%Y-%m-%d %H:%M:%S")
            total_hours += (check_out_time - check_in_time).seconds / 3600
    avg_hours = round(total_hours / (present_today if present_today else 1), 1)

    # student attendance list
    c.execute('''SELECT s.id, s.name, s.roll, s.department, a.check_in, a.check_out
                 FROM students s
                          LEFT JOIN attendance a ON s.id = a.student_id
                     AND DATE (a.check_in)=?''', (today,))
    attendance_list = c.fetchall()

    conn.close()

    return render_template("dashboard.html",
                           total=total_students,
                           present=present_today,
                           absent=absent_today,
                           avg_hours=avg_hours,
                           attendance_list=attendance_list)


@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        department = request.form["department"]

        conn = sqlite3.connect("attendance.db")
        c = conn.cursor()
        c.execute("INSERT INTO students (name, roll, department) VALUES (?, ?, ?)", (name, roll, department))
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_student.html")


@app.route("/checkin/<int:student_id>")
def checkin(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO attendance (student_id, check_in) VALUES (?, ?)", (student_id, now))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/checkout/<int:student_id>")
def checkout(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE attendance SET check_out=? WHERE student_id=? AND check_out IS NULL", (now, student_id))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    c.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/report")
def report():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    c.execute('''SELECT s.id,
                        s.name,
                        s.roll,
                        s.department,
                        COUNT(a.id)                                             as total_records,
                        SUM(CASE WHEN a.check_in IS NOT NULL THEN 1 ELSE 0 END) as present_days
                 FROM students s
                          LEFT JOIN attendance a ON s.id = a.student_id
                 GROUP BY s.id''')
    report_data = c.fetchall()
    conn.close()

    return render_template("report.html", report_data=report_data)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey"


# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    roll TEXT UNIQUE,
                    department TEXT
                )''')

    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    check_in TEXT,
                    check_out TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id)
                )''')

    # Admin table
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT
                )''')

    # Create default admin if not exists
    c.execute("SELECT * FROM admins WHERE username=?", ("admin",))
    if not c.fetchone():
        c.execute("INSERT INTO admins (username, password) VALUES (?, ?)",
                  ("admin", generate_password_hash("admin123")))

    conn.commit()
    conn.close()


# ---------------- Helpers ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("You must log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.template_filter("datetimeformat")
def datetimeformat(value, format="%A"):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except:
        return value


# ---------------- Routes ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("attendance.db")
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE username=?", (username,))
        admin = c.fetchone()
        conn.close()

        if admin and check_password_hash(admin[2], password):
            session["admin"] = username
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("attendance.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO admins (username, password) VALUES (?, ?)",
                      (username, generate_password_hash(password)))
            conn.commit()
            flash("Signup successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
            return redirect(url_for("signup"))
        finally:
            conn.close()

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ---------- Dashboard ----------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # Total students
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    # Today date
    today = datetime.now().strftime("%Y-%m-%d")

    # Present today
    c.execute("SELECT COUNT(DISTINCT student_id) FROM attendance WHERE DATE(check_in)=?", (today,))
    present_today = c.fetchone()[0]

    # Absent today
    absent_today = total_students - present_today

    # Average hours
    c.execute("SELECT check_in, check_out FROM attendance WHERE DATE(check_in)=?", (today,))
    records = c.fetchall()
    total_hours = 0
    for rec in records:
        if rec[1]:
            check_in_time = datetime.strptime(rec[0], "%Y-%m-%d %H:%M:%S")
            check_out_time = datetime.strptime(rec[1], "%Y-%m-%d %H:%M:%S")
            total_hours += (check_out_time - check_in_time).seconds / 3600
    avg_hours = round(total_hours / (present_today if present_today else 1), 1)

    # Student list
    c.execute('''SELECT s.id, s.name, s.roll, s.department, a.check_in, a.check_out
                 FROM students s
                 LEFT JOIN attendance a ON s.id = a.student_id
                 AND DATE(a.check_in)=?''', (today,))
    attendance_list = c.fetchall()

    conn.close()
    return render_template("dashboard.html",
                           total=total_students,
                           present=present_today,
                           absent=absent_today,
                           avg_hours=avg_hours,
                           attendance_list=attendance_list)


# ---------- Student ----------
@app.route("/add_student", methods=["GET", "POST"])
@login_required
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
@login_required
def checkin(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO attendance (student_id, check_in) VALUES (?, ?)", (student_id, now))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/checkout/<int:student_id>")
@login_required
def checkout(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE attendance SET check_out=? WHERE student_id=? AND check_out IS NULL", (now, student_id))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/delete_student/<int:student_id>")
@login_required
def delete_student(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    c.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/report")
@login_required
def report():
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    c.execute('''SELECT s.id, s.name, s.roll, s.department,
                        COUNT(a.id) as total_records,
                        SUM(CASE WHEN a.check_in IS NOT NULL THEN 1 ELSE 0 END) as present_days
                 FROM students s
                 LEFT JOIN attendance a ON s.id = a.student_id
                 GROUP BY s.id''')
    report_data = c.fetchall()
    conn.close()

    return render_template("report.html", report_data=report_data)


# ---------- NEW: View Individual Attendance ----------
@app.route("/view_attendance/<int:student_id>")
@login_required
def view_attendance(student_id):
    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    # Get student info
    c.execute("SELECT name, roll, department FROM students WHERE id=?", (student_id,))
    student = c.fetchone()

    # Get attendance records
    c.execute("SELECT check_in, check_out FROM attendance WHERE student_id=? ORDER BY check_in DESC", (student_id,))
    records = c.fetchall()
    conn.close()

    return render_template("view_attendance.html", student=student, records=records)


# ---------------- Run ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from model.predict import predict_performance
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

def db():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        port=app.config["MYSQL_PORT"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"]
    )

def login_required():
    return "user_id" in session

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM students"); students = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM predictions"); predictions = cur.fetchone()[0]
    cur.close(); conn.close()
    return render_template("dashboard.html", students=students, predictions=predictions)

@app.route("/students")
def students():
    if not login_required(): return redirect(url_for("login"))
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students ORDER BY student_id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return render_template("students.html", students=rows)

@app.route("/students/add", methods=["GET","POST"])
def add_student():
    if not login_required(): return redirect(url_for("login"))
    if request.method == "POST":
        data = (
            request.form["roll_no"].strip(), request.form["name"].strip(),
            request.form.get("email","").strip(), request.form.get("mobile","").strip(),
            request.form.get("department","").strip(), request.form.get("semester") or None
        )
        conn = db(); cur = conn.cursor()
        try:
            cur.execute("""INSERT INTO students
                (roll_no,name,email,mobile,department,semester)
                VALUES (%s,%s,%s,%s,%s,%s)""", data)
            conn.commit(); flash("Student added successfully.", "success")
        except Error as e:
            conn.rollback(); flash(str(e), "danger")
        finally:
            cur.close(); conn.close()
        return redirect(url_for("students"))
    return render_template("student_form.html")

@app.route("/academic/<int:student_id>", methods=["GET","POST"])
def academic(student_id):
    if not login_required(): return redirect(url_for("login"))
    conn = db(); cur = conn.cursor(dictionary=True)
    if request.method == "POST":
        values = (
            float(request.form["attendance"]), float(request.form["internal_marks"]),
            float(request.form["assignment_marks"]), float(request.form["practical_marks"]),
            float(request.form["previous_cgpa"]), int(request.form["backlog_count"])
        )
        cur.execute("""INSERT INTO academic_records
            (student_id,attendance,internal_marks,assignment_marks,practical_marks,
             previous_cgpa,backlog_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE attendance=VALUES(attendance),
            internal_marks=VALUES(internal_marks), assignment_marks=VALUES(assignment_marks),
            practical_marks=VALUES(practical_marks), previous_cgpa=VALUES(previous_cgpa),
            backlog_count=VALUES(backlog_count)""", (student_id,)+values)
        conn.commit()
        flash("Academic record saved.", "success")
        cur.close(); conn.close()
        return redirect(url_for("students"))
    cur.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cur.fetchone()
    cur.execute("SELECT * FROM academic_records WHERE student_id=%s", (student_id,))
    record = cur.fetchone()
    cur.close(); conn.close()
    return render_template("academic.html", student=student, record=record)

@app.route("/predict/<int:student_id>", methods=["POST"])
def predict(student_id):
    if not login_required(): return redirect(url_for("login"))
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM academic_records WHERE student_id=%s", (student_id,))
    r = cur.fetchone()
    if not r:
        cur.close(); conn.close()
        flash("Enter academic data before prediction.", "warning")
        return redirect(url_for("academic", student_id=student_id))
    result, confidence, algorithm = predict_performance(
        r["attendance"], r["internal_marks"], r["assignment_marks"],
        r["practical_marks"], r["previous_cgpa"], r["backlog_count"]
    )
    cur.execute("""INSERT INTO predictions
        (student_id,predicted_result,confidence,algorithm)
        VALUES (%s,%s,%s,%s)""", (student_id,result,confidence,algorithm))
    conn.commit()
    cur.close(); conn.close()
    return render_template("prediction.html", result=result,
                           confidence=confidence, algorithm=algorithm,
                           student_id=student_id)

@app.route("/reports")
def reports():
    if not login_required(): return redirect(url_for("login"))
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT p.*, s.roll_no, s.name
                   FROM predictions p JOIN students s ON s.student_id=p.student_id
                   ORDER BY p.prediction_date DESC""")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return render_template("reports.html", rows=rows)

@app.route("/setup-admin")
def setup_admin():
    # Run once locally, then remove/disable this route in production.
    username = request.args.get("username","admin")
    password = request.args.get("password","admin123")
    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT INTO users(username,password_hash,role)
                   VALUES(%s,%s,'admin')
                   ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash),
                   role='admin'""", (username, generate_password_hash(password)))
    conn.commit(); cur.close(); conn.close()
    return "Admin created/updated. Remove the /setup-admin route before production."

if __name__ == "__main__":
    app.run(debug=True)

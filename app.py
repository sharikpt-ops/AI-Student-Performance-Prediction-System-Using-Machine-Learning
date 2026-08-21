from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from model.predict import predict_performance
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

def db():
    return mysql.connector.connect(host=app.config['MYSQL_HOST'], port=app.config['MYSQL_PORT'], user=app.config['MYSQL_USER'], password=app.config['MYSQL_PASSWORD'], database=app.config['MYSQL_DATABASE'])

def login_required():
    return 'user_id' in session

def close_db(cur, conn):
    if cur: cur.close()
    if conn: conn.close()

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip(); password = request.form['password']
        conn = db(); cur = conn.cursor(dictionary=True)
        try:
            cur.execute('SELECT * FROM users WHERE username=%s', (username,)); user = cur.fetchone()
        finally: close_db(cur, conn)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id']=user['user_id']; session['username']=user['username']; session['role']=user['role']
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) FROM students'); students=cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM faculty'); faculty=cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM predictions'); predictions=cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM academic_results'); results=cur.fetchone()[0]
    finally: close_db(cur,conn)
    return render_template('dashboard.html', students=students, faculty=faculty, predictions=predictions, results=results)

@app.route('/students')
def students():
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    try: cur.execute('SELECT * FROM students ORDER BY student_id DESC'); rows=cur.fetchall()
    finally: close_db(cur,conn)
    return render_template('students.html', students=rows)

@app.route('/students/add', methods=['GET','POST'])
def add_student():
    if not login_required(): return redirect(url_for('login'))
    if request.method=='POST':
        data=(request.form['roll_no'].strip(),request.form['name'].strip(),request.form.get('email','').strip(),request.form.get('mobile','').strip(),request.form.get('department','').strip(),request.form.get('semester') or None)
        conn=db(); cur=conn.cursor()
        try:
            cur.execute('INSERT INTO students (roll_no,name,email,mobile,department,semester) VALUES (%s,%s,%s,%s,%s,%s)',data); conn.commit(); flash('Student added successfully.','success')
        except Error as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('students'))
    return render_template('student_form.html')

@app.route('/faculty')
def faculty_list():
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    try: cur.execute('SELECT * FROM faculty ORDER BY faculty_id DESC'); rows=cur.fetchall()
    finally: close_db(cur,conn)
    return render_template('faculty.html', faculty=rows)

@app.route('/faculty/add', methods=['GET','POST'])
def add_faculty():
    if not login_required(): return redirect(url_for('login'))
    if request.method=='POST':
        name=request.form['faculty_name'].strip(); email=request.form.get('email','').strip(); mobile=request.form.get('mobile','').strip()
        if not name: flash('Faculty name is required.','danger'); return redirect(url_for('add_faculty'))
        conn=db(); cur=conn.cursor()
        try: cur.execute('INSERT INTO faculty (faculty_name,email,mobile) VALUES (%s,%s,%s)',(name,email,mobile)); conn.commit(); flash('Faculty added successfully.','success')
        except Error as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('faculty_list'))
    return render_template('faculty_form.html', faculty=None)

@app.route('/faculty/edit/<int:faculty_id>', methods=['GET','POST'])
def edit_faculty(faculty_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        name=request.form['faculty_name'].strip(); email=request.form.get('email','').strip(); mobile=request.form.get('mobile','').strip()
        if not name: close_db(cur,conn); flash('Faculty name is required.','danger'); return redirect(url_for('edit_faculty',faculty_id=faculty_id))
        try: cur.execute('UPDATE faculty SET faculty_name=%s,email=%s,mobile=%s WHERE faculty_id=%s',(name,email,mobile,faculty_id)); conn.commit(); flash('Faculty updated successfully.','success')
        except Error as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('faculty_list'))
    try: cur.execute('SELECT * FROM faculty WHERE faculty_id=%s',(faculty_id,)); faculty=cur.fetchone()
    finally: close_db(cur,conn)
    if not faculty: flash('Faculty record not found.','danger'); return redirect(url_for('faculty_list'))
    return render_template('faculty_form.html', faculty=faculty)

@app.route('/faculty/delete/<int:faculty_id>', methods=['POST'])
def delete_faculty(faculty_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor()
    try: cur.execute('DELETE FROM faculty WHERE faculty_id=%s',(faculty_id,)); conn.commit(); flash('Faculty deleted successfully.','success')
    except Error as e: conn.rollback(); flash(str(e),'danger')
    finally: close_db(cur,conn)
    return redirect(url_for('faculty_list'))

@app.route('/academic/<int:student_id>', methods=['GET','POST'])
def academic(student_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        try:
            values=(float(request.form['attendance']),float(request.form['internal_marks']),float(request.form['assignment_marks']),float(request.form['practical_marks']),float(request.form['previous_cgpa']),int(request.form['backlog_count']))
            cur.execute('''INSERT INTO academic_records (student_id,attendance,internal_marks,assignment_marks,practical_marks,previous_cgpa,backlog_count) VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE attendance=VALUES(attendance),internal_marks=VALUES(internal_marks),assignment_marks=VALUES(assignment_marks),practical_marks=VALUES(practical_marks),previous_cgpa=VALUES(previous_cgpa),backlog_count=VALUES(backlog_count)''',(student_id,)+values); conn.commit(); flash('Academic record saved successfully.','success')
        except (ValueError,Error) as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('students'))
    try:
        cur.execute('SELECT * FROM students WHERE student_id=%s',(student_id,)); student=cur.fetchone()
        cur.execute('SELECT * FROM academic_records WHERE student_id=%s',(student_id,)); record=cur.fetchone()
    finally: close_db(cur,conn)
    if not student: flash('Student record not found.','danger'); return redirect(url_for('students'))
    return render_template('academic.html',student=student,record=record)

@app.route('/results')
def results():
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute('''SELECT ar.*,s.roll_no,s.name,s.department FROM academic_results ar INNER JOIN students s ON s.student_id=ar.student_id ORDER BY ar.result_id DESC'''); rows=cur.fetchall()
    finally: close_db(cur,conn)
    return render_template('results.html', results=rows)

@app.route('/result/add', methods=['GET'])
def add_result_select():
    if not login_required(): return redirect(url_for('login'))
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute('SELECT student_id, roll_no, name, department, semester FROM students ORDER BY name')
        students_rows = cur.fetchall()
    finally:
        close_db(cur, conn)
    return render_template('result_add_select.html', students=students_rows)


@app.route('/result/add/<int:student_id>', methods=['GET','POST'])
def add_result(student_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        try:
            semester=int(request.form['semester']); total=float(request.form['total_marks']); percentage=float(request.form['percentage']); grade=request.form.get('grade','').strip().upper(); status=request.form['result_status'].strip()
            if not 0 <= percentage <= 100: raise ValueError('Percentage must be between 0 and 100.')
            cur.execute('INSERT INTO academic_results (student_id,semester,total_marks,percentage,grade,result_status) VALUES (%s,%s,%s,%s,%s,%s)',(student_id,semester,total,percentage,grade,status)); conn.commit(); flash('Academic result added successfully.','success')
        except (ValueError,Error) as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('results'))
    try: cur.execute('SELECT * FROM students WHERE student_id=%s',(student_id,)); student=cur.fetchone()
    finally: close_db(cur,conn)
    if not student: flash('Student record not found.','danger'); return redirect(url_for('students'))
    return render_template('result_form.html',student=student,result=None)

@app.route('/result/edit/<int:result_id>', methods=['GET','POST'])
def edit_result(result_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    if request.method=='POST':
        try:
            semester=int(request.form['semester']); total=float(request.form['total_marks']); percentage=float(request.form['percentage']); grade=request.form.get('grade','').strip().upper(); status=request.form['result_status'].strip()
            if not 0 <= percentage <= 100: raise ValueError('Percentage must be between 0 and 100.')
            cur.execute('UPDATE academic_results SET semester=%s,total_marks=%s,percentage=%s,grade=%s,result_status=%s WHERE result_id=%s',(semester,total,percentage,grade,status,result_id)); conn.commit(); flash('Academic result updated successfully.','success')
        except (ValueError,Error) as e: conn.rollback(); flash(str(e),'danger')
        finally: close_db(cur,conn)
        return redirect(url_for('results'))
    try:
        cur.execute('''SELECT ar.*,s.roll_no,s.name,s.department FROM academic_results ar INNER JOIN students s ON s.student_id=ar.student_id WHERE ar.result_id=%s''',(result_id,)); result=cur.fetchone()
    finally: close_db(cur,conn)
    if not result: flash('Academic result not found.','danger'); return redirect(url_for('results'))
    student={'student_id':result['student_id'],'roll_no':result['roll_no'],'name':result['name'],'department':result['department'],'semester':result['semester']}
    return render_template('result_form.html',student=student,result=result)

@app.route('/result/delete/<int:result_id>', methods=['POST'])
def delete_result(result_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor()
    try: cur.execute('DELETE FROM academic_results WHERE result_id=%s',(result_id,)); conn.commit(); flash('Academic result deleted successfully.','success')
    except Error as e: conn.rollback(); flash(str(e),'danger')
    finally: close_db(cur,conn)
    return redirect(url_for('results'))

@app.route('/predict/<int:student_id>', methods=['POST'])
def predict(student_id):
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute('SELECT * FROM academic_records WHERE student_id=%s',(student_id,)); r=cur.fetchone()
        if not r: flash('Enter academic data before prediction.','warning'); return redirect(url_for('academic',student_id=student_id))
        result,confidence,algorithm=predict_performance(r['attendance'],r['internal_marks'],r['assignment_marks'],r['practical_marks'],r['previous_cgpa'],r['backlog_count'])
        cur.execute('INSERT INTO predictions (student_id,predicted_result,confidence,algorithm) VALUES (%s,%s,%s,%s)',(student_id,result,confidence,algorithm)); conn.commit()
    except Error as e: conn.rollback(); flash(str(e),'danger'); return redirect(url_for('students'))
    finally: close_db(cur,conn)
    return render_template('prediction.html',result=result,confidence=confidence,algorithm=algorithm,student_id=student_id)

@app.route('/predictions')
def predictions():
    if not login_required(): return redirect(url_for('login'))
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''SELECT p.*, s.roll_no, s.name, s.department
                       FROM predictions p
                       INNER JOIN students s ON s.student_id=p.student_id
                       ORDER BY p.prediction_date DESC''')
        rows = cur.fetchall()
    finally:
        close_db(cur, conn)
    return render_template('predictions.html', rows=rows)


@app.route('/prediction/edit/<int:prediction_id>', methods=['GET','POST'])
def edit_prediction(prediction_id):
    if not login_required(): return redirect(url_for('login'))
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            predicted_result = request.form.get('predicted_result','').strip()
            algorithm = request.form.get('algorithm','').strip()
            confidence_raw = request.form.get('confidence','').strip()
            if not predicted_result or not algorithm:
                flash('Prediction result and algorithm are required.', 'danger')
                return redirect(url_for('edit_prediction', prediction_id=prediction_id))
            confidence = None if confidence_raw == '' else float(confidence_raw)
            if confidence is not None and not 0 <= confidence <= 1:
                raise ValueError('Confidence must be between 0 and 1.')
            cur.execute('''UPDATE predictions
                           SET predicted_result=%s, confidence=%s, algorithm=%s
                           WHERE prediction_id=%s''',
                        (predicted_result, confidence, algorithm, prediction_id))
            conn.commit()
            flash('Prediction updated successfully.', 'success')
            return redirect(url_for('predictions'))

        cur.execute('''SELECT p.*, s.roll_no, s.name, s.department
                       FROM predictions p
                       INNER JOIN students s ON s.student_id=p.student_id
                       WHERE p.prediction_id=%s''', (prediction_id,))
        prediction = cur.fetchone()
    except (ValueError, Error) as e:
        conn.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('predictions'))
    finally:
        close_db(cur, conn)
    if not prediction:
        flash('Prediction record not found.', 'danger')
        return redirect(url_for('predictions'))
    return render_template('prediction_form.html', prediction=prediction)


@app.route('/prediction/delete/<int:prediction_id>', methods=['POST','GET'])
def delete_prediction(prediction_id):
    if not login_required(): return redirect(url_for('login'))
    conn = db(); cur = conn.cursor()
    try:
        cur.execute('DELETE FROM predictions WHERE prediction_id=%s', (prediction_id,))
        conn.commit()
        flash('Prediction deleted successfully.', 'success')
    except Error as e:
        conn.rollback()
        flash(str(e), 'danger')
    finally:
        close_db(cur, conn)
    return redirect(url_for('predictions'))


@app.route('/reports/edit/<int:report_id>', methods=['GET','POST'])
def edit_report(report_id):
    # Reports are generated from the predictions table, so report editing
    # uses the same prediction record instead of the old/non-existent
    # prediction_reports table.
    return edit_prediction(report_id)


@app.route('/reports/delete/<int:report_id>', methods=['POST','GET'])
def delete_report(report_id):
    return delete_prediction(report_id)


@app.route('/reports')
def reports():
    if not login_required(): return redirect(url_for('login'))
    conn=db(); cur=conn.cursor(dictionary=True)
    try: cur.execute('''SELECT p.*,s.roll_no,s.name FROM predictions p JOIN students s ON s.student_id=p.student_id ORDER BY p.prediction_date DESC'''); rows=cur.fetchall()
    finally: close_db(cur,conn)
    return render_template('reports.html',rows=rows)

@app.route('/setup-admin')
def setup_admin():
    username=request.args.get('username','admin'); password=request.args.get('password','admin123'); conn=db(); cur=conn.cursor()
    try:
        cur.execute('''INSERT INTO users(username,password_hash,role) VALUES(%s,%s,'admin') ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash),role='admin' ''',(username,generate_password_hash(password))); conn.commit()
    finally: close_db(cur,conn)
    return 'Admin created/updated. Remove or disable /setup-admin after first use.'

if __name__ == '__main__':
    app.run(debug=True)

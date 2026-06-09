import os
import qrcode
import datetime
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, Response, flash, session
from functools import wraps
from models import db, Member, Attendance, Admin

app = Flask(__name__, instance_relative_config=True)

# Configure instance path
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
app.instance_path = instance_path

# Database setup
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
elif not database_url:
    database_url = f"sqlite:///{os.path.join(basedir, 'instance', 'attendance.db')}"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '2e6442d5ad6417606b868f8294d71521 ')
db.init_app(app)

# Schema Self-Healing & Table Initialization
def init_db():
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        need_recreation = False
        
        # Check if basic tables exist
        if not (inspector.has_table('member') and inspector.has_table('attendance') and inspector.has_table('admin')):
            need_recreation = True
        else:
            # Check if columns are updated in 'member' table
            columns = [col['name'] for col in inspector.get_columns('member')]
            if 'role' not in columns or 'department' not in columns:
                need_recreation = True
                
        if need_recreation:
            print("Initializing / Upgrading database schema...")
            db.drop_all()
            db.create_all()
            print("Database initialized successfully.")
        else:
            print("Database tables verified.")

init_db()

# Decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def home():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('register'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        admin = Admin.query.filter_by(username=request.form['username']).first()
        if admin and admin.check_password(request.form['password']):
            session['admin'] = admin.username
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

@app.route('/update_password', methods=['GET', 'POST'])
@admin_required
def update_password():
    error = None
    success = None
    admin_user = Admin.query.filter_by(username=session['admin']).first()
    if request.method == 'POST':
        current = request.form['current_password']
        new = request.form['new_password']
        confirm = request.form['confirm_password']
        if not admin_user.check_password(current):
            error = 'Current password is incorrect.'
        elif new != confirm:
            error = 'New passwords do not match.'
        else:
            admin_user.set_password(new)
            db.session.commit()
            success = 'Password updated successfully!'
    return render_template('update_password.html', error=error, success=success)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    error = None
    success = None
    if request.method == 'POST':
        username = request.form['username']
        new = request.form['new_password']
        confirm = request.form['confirm_password']
        admin_user = Admin.query.filter_by(username=username).first()
        if not admin_user:
            error = 'Admin user not found.'
        elif new != confirm:
            error = 'Passwords do not match.'
        else:
            admin_user.set_password(new)
            db.session.commit()
            success = 'Password reset successfully!'
    return render_template('reset_password.html', error=error, success=success)

@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    error = None
    success = None
    if Admin.query.count() > 0 and not session.get('admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']
        if password != confirm:
            error = 'Passwords do not match.'
        elif Admin.query.filter_by(username=username).first():
            error = 'Username already exists.'
        else:
            new_admin = Admin(username=username)
            new_admin.set_password(password)
            db.session.add(new_admin)
            db.session.commit()
            success = 'Admin registered successfully. You can now login!'
    return render_template('admin_register.html', error=error, success=success)

# Student & Employee Registration and QR generation
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        emp_code = request.form['emp_code']
        role = request.form.get('role', 'employee')
        department = request.form.get('department', '')
        
        # Salary is only applicable for employees
        daily_salary = 0.0
        if role == 'employee':
            try:
                daily_salary = float(request.form.get('daily_salary', 0.0))
            except ValueError:
                daily_salary = 500.0

        if Member.query.filter_by(emp_code=emp_code).first():
            flash('ID Code or Roll Number already exists.', 'danger')
            return render_template('register.html')

        qr_data = f"{role}:{emp_code}:{name}"
        member = Member(name=name, emp_code=emp_code, qr_data=qr_data, role=role, department=department, daily_salary=daily_salary)
        db.session.add(member)
        db.session.commit()

        # Generate and save QR code
        qr_img = qrcode.make(qr_data)
        qr_path = f"static/qr_codes/{emp_code}.png"
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        qr_img.save(qr_path)
        
        flash(f"{role.capitalize()} registered and QR code generated successfully!", 'success')
        return render_template('register.html', 
                               qr_code_url=url_for('static', filename=f'qr_codes/{emp_code}.png'), 
                               registered_member=member)

    return render_template('register.html')

# QR Code scanning and attendance marking
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    if not data or 'qr_data' not in data:
        return jsonify({"status": "error", "message": "No QR data found."}), 400
        
    qr_data = data['qr_data']
    
    # Check if QR data is formatted as role:code:name or just code
    parts = qr_data.split(':')
    if len(parts) >= 2:
        role = parts[0]
        emp_code = parts[1]
    else:
        emp_code = qr_data
        
    member = Member.query.filter_by(emp_code=emp_code).first()
    if not member:
        return jsonify({"status": "error", "message": f"Invalid QR Code. Member with ID '{emp_code}' not found."}), 404
        
    today = datetime.date.today()
    now = datetime.datetime.now().time()
    formatted_time = now.strftime('%I:%M %p')
    
    att = Attendance.query.filter_by(emp_code=member.emp_code, date=today).first()
    if not att:
        att = Attendance(emp_code=member.emp_code, date=today, time_in=now)
        db.session.add(att)
        db.session.commit()
        return jsonify({
            "status": "success",
            "type": "in",
            "message": f"Check-In Marked! Welcome, {member.name}.",
            "name": member.name,
            "role": member.role.upper(),
            "code": member.emp_code,
            "time": formatted_time
        })
    elif not att.time_out:
        att.time_out = now
        db.session.commit()
        return jsonify({
            "status": "success",
            "type": "out",
            "message": f"Check-Out Marked! Goodbye, {member.name}.",
            "name": member.name,
            "role": member.role.upper(),
            "code": member.emp_code,
            "time": formatted_time
        })
    else:
        return jsonify({
            "status": "warning",
            "message": f"Attendance already completed for {member.name} today.",
            "name": member.name,
            "role": member.role.upper(),
            "code": member.emp_code
        })

# Admin dashboard
@app.route('/admin')
@admin_required
def admin_dashboard():
    members = Member.query.all()
    
    # Stats
    total_students = Member.query.filter_by(role='student').count()
    total_employees = Member.query.filter_by(role='employee').count()
    
    today = datetime.date.today()
    today_presents = db.session.query(Attendance.emp_code).filter(Attendance.date == today).distinct().count()
    
    # Fetch recent logs with member details joined
    recent_logs = db.session.query(Attendance, Member).join(
        Member, Attendance.emp_code == Member.emp_code
    ).filter(
        Attendance.date == today
    ).order_by(
        Attendance.time_in.desc()
    ).limit(10).all()
    
    current_month = datetime.date.today().strftime('%Y-%m')
    return render_template('admin.html', 
                           members=members, 
                           total_students=total_students, 
                           total_employees=total_employees,
                           today_presents=today_presents,
                           recent_logs=recent_logs,
                           current_month=current_month)

# Member routing details
@app.route('/edit_member/<emp_code>', methods=['GET', 'POST'])
@admin_required
def edit_member(emp_code):
    member = Member.query.filter_by(emp_code=emp_code).first_or_404()
    if request.method == 'POST':
        member.name = request.form['name']
        member.role = request.form.get('role', 'employee')
        member.department = request.form['department']
        
        if member.role == 'employee':
            member.daily_salary = float(request.form.get('daily_salary', 0.0))
        else:
            member.daily_salary = 0.0
            
        db.session.commit()
        flash(f"{member.role.capitalize()} details updated!", 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_employee.html', employee=member)

@app.route('/edit_employee/<emp_code>', methods=['GET', 'POST'])
@admin_required
def edit_employee(emp_code):
    return redirect(url_for('edit_member', emp_code=emp_code))

@app.route('/delete_member/<emp_code>', methods=['POST', 'GET'])
@admin_required
def delete_member(emp_code):
    member = Member.query.filter_by(emp_code=emp_code).first_or_404()
    Attendance.query.filter_by(emp_code=emp_code).delete()
    db.session.delete(member)
    db.session.commit()
    
    # Delete QR code file
    qr_path = f"static/qr_codes/{emp_code}.png"
    if os.path.exists(qr_path):
        try:
            os.remove(qr_path)
        except OSError:
            pass
            
    flash('Record deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_employee/<emp_code>', methods=['POST', 'GET'])
@admin_required
def delete_employee(emp_code):
    return redirect(url_for('delete_member', emp_code=emp_code))

# Attendance reports
@app.route('/report')
@admin_required
def report():
    date_filter = request.args.get('date', '')
    emp_filter = request.args.get('emp_code', '')
    role_filter = request.args.get('role', '')
    
    query = db.session.query(Attendance, Member).join(Member, Attendance.emp_code == Member.emp_code)
    
    if date_filter:
        query = query.filter(Attendance.date == date_filter)
    if emp_filter:
        query = query.filter(Attendance.emp_code == emp_filter)
    if role_filter:
        query = query.filter(Member.role == role_filter)
        
    logs = query.order_by(Attendance.date.desc(), Attendance.time_in.desc()).all()
    return render_template('report.html', logs=logs, date_filter=date_filter, emp_filter=emp_filter, role_filter=role_filter)

# QR scan page
@app.route('/scan')
def scan():
    return render_template('scan.html')

# CSV export
@app.route('/export_csv')
@admin_required
def export_csv():
    from io import StringIO
    logs = db.session.query(Attendance, Member).join(Member, Attendance.emp_code == Member.emp_code).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID/RollNo', 'Name', 'Role', 'Department/Class', 'Date', 'Time_In', 'Time_Out'])
    for log, mem in logs:
        writer.writerow([mem.emp_code, mem.name, mem.role.capitalize(), mem.department, log.date, log.time_in, log.time_out])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=attendance_report.csv'})

# Salary calculation
@app.route('/salary')
@admin_required
def salary():
    from sqlalchemy import func, extract

    emp_code = request.args.get('emp_code', '')
    month = request.args.get('month', '')  # format 'YYYY-MM'
    member = Member.query.filter_by(emp_code=emp_code).first()

    if not member:
        return "Member not found", 404
        
    if member.role == 'student':
        return "Salary calculations are not applicable for students.", 400

    year, month_num = month.split("-")

    days_worked = db.session.query(
        func.count(func.distinct(Attendance.date))
    ).filter(
        Attendance.emp_code == emp_code,
        extract('year', Attendance.date) == int(year),
        extract('month', Attendance.date) == int(month_num)
    ).scalar() or 0

    total_salary = days_worked * member.daily_salary

    return render_template('salary.html',
                           emp=member,
                           days_worked=days_worked,
                           total_salary=total_salary,
                           month=month)

@app.route('/download_salary_sheet')
@admin_required
def download_salary_sheet():
    from sqlalchemy import func, extract

    month = request.args.get('month', '')
    year, month_num = month.split("-")

    employees = Member.query.filter_by(role='employee').all()
    data_rows = [['Emp_Code', 'Name', 'Department', 'Days_Worked', 'Daily_Salary', 'Total_Salary']]

    for e in employees:
        days_worked = db.session.query(
            func.count(func.distinct(Attendance.date))
        ).filter(
            Attendance.emp_code == e.emp_code,
            extract('year', Attendance.date) == int(year),
            extract('month', Attendance.date) == int(month_num)
        ).scalar() or 0

        total_salary = days_worked * e.daily_salary
        data_rows.append([e.emp_code, e.name, e.department, days_worked, e.daily_salary, total_salary])

    output = "\n".join([",".join(map(str, row)) for row in data_rows])

    return Response(output,
                    mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename=salary_sheet_{month}.csv"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

import os
import qrcode
import datetime
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, Response, flash, session
from functools import wraps
from models import db, Employee, Attendance, Admin

app = Flask(__name__)

# Railway provides DATABASE_URL environment variable
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///attendance.db"
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '2e6442d5ad6417606b868f8294d71521 ')
db.init_app(app)

# Create tables when app starts (works with gunicorn on Railway)
with app.app_context():
    db.create_all()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
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
    # Allow registration if no admins exist, or restrict to logged-in admins
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

# Employee registration and QR generation
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        emp_code = request.form['emp_code']
        daily_salary = float(request.form['daily_salary'])
        qr_data = f"{emp_code}:{name}"
        if Employee.query.filter_by(emp_code=emp_code).first():
            return "Employee code already exists."
        emp = Employee(name=name, emp_code=emp_code, qr_data=qr_data, daily_salary=daily_salary)
        db.session.add(emp)
        db.session.commit()
        qr_img = qrcode.make(qr_data)
        qr_path = f"static/qr_codes/{emp_code}.png"
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        qr_img.save(qr_path)
        flash('Employee registered and QR code generated successfully!', 'success')
        return send_file(qr_path, mimetype='image/png', as_attachment=True)
    return render_template('register.html')

# QR Code scanning and attendance marking
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    qr_data = data['qr_data']
    emp = Employee.query.filter_by(qr_data=qr_data).first()
    if not emp:
        return "Invalid QR Code.", 400
    today = datetime.date.today()
    now = datetime.datetime.now().time()
    att = Attendance.query.filter_by(emp_code=emp.emp_code, date=today).first()
    if not att:
        att = Attendance(emp_code=emp.emp_code, date=today, time_in=now)
        db.session.add(att)
        db.session.commit()
        return "Attendance marked!"
    elif not att.time_out:
        att.time_out = now
        db.session.commit()
        return "Time-out marked!"
    else:
        return "Attendance already marked."

# Admin dashboard
@app.route('/admin')
@admin_required
def admin_dashboard():
    employees = Employee.query.all()
    current_month = datetime.date.today().strftime('%Y-%m')
    return render_template('admin.html', employees=employees, current_month=current_month)

@app.route('/edit_employee/<emp_code>', methods=['GET', 'POST'])
@admin_required
def edit_employee(emp_code):
    employee = Employee.query.filter_by(emp_code=emp_code).first_or_404()
    if request.method == 'POST':
        employee.name = request.form['name']
        employee.daily_salary = float(request.form['daily_salary'])
        db.session.commit()
        flash('Employee updated!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_employee.html', employee=employee)

@app.route('/delete_employee/<emp_code>', methods=['POST', 'GET'])
@admin_required
def delete_employee(emp_code):
    employee = Employee.query.filter_by(emp_code=emp_code).first_or_404()
    # Remove related attendance records for referential integrity
    Attendance.query.filter_by(emp_code=emp_code).delete()
    db.session.delete(employee)
    db.session.commit()
    flash('Employee deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

# Attendance reports
@app.route('/report')
@admin_required
def report():
    date_filter = request.args.get('date', '')
    emp_filter = request.args.get('emp_code', '')
    query = Attendance.query
    if date_filter:
        query = query.filter_by(date=date_filter)
    if emp_filter:
        query = query.filter_by(emp_code=emp_filter)
    logs = query.all()
    return render_template('report.html', logs=logs)

# QR scan page
@app.route('/scan')
def scan():
    return render_template('scan.html')

# CSV export
@app.route('/export_csv')
def export_csv():
    from io import StringIO
    logs = Attendance.query.all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Emp_Code', 'Date', 'Time_In', 'Time_Out'])
    for log in logs:
        writer.writerow([log.emp_code, log.date, log.time_in, log.time_out])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=attendance.csv'})

# Salary calculation
@app.route('/salary')
@admin_required
def salary():
    from sqlalchemy import func, extract

    emp_code = request.args.get('emp_code', '')
    month = request.args.get('month', '')  # format 'YYYY-MM'
    employee = Employee.query.filter_by(emp_code=emp_code).first()

    if not employee:
        return "Employee not found"

    year, month_num = month.split("-")

    days_worked = db.session.query(
        func.count(func.distinct(Attendance.date))
    ).filter(
        Attendance.emp_code == emp_code,
        extract('year', Attendance.date) == int(year),
        extract('month', Attendance.date) == int(month_num)
    ).scalar()

    total_salary = days_worked * employee.daily_salary

    return render_template('salary.html',
                           emp=employee,
                           days_worked=days_worked,
                           total_salary=total_salary,
                           month=month)


@app.route('/download_salary_sheet')
@admin_required
def download_salary_sheet():
    from sqlalchemy import func, extract

    month = request.args.get('month', '')
    year, month_num = month.split("-")

    employees = Employee.query.all()
    data_rows = [['Emp_Code', 'Name', 'Days_Worked', 'Daily_Salary', 'Total_Salary']]

    for e in employees:
        days_worked = db.session.query(
            func.count(func.distinct(Attendance.date))
        ).filter(
            Attendance.emp_code == e.emp_code,
            extract('year', Attendance.date) == int(year),
            extract('month', Attendance.date) == int(month_num)
        ).scalar()

        total_salary = days_worked * e.daily_salary
        data_rows.append([e.emp_code, e.name, days_worked, e.daily_salary, total_salary])

    output = "\n".join([",".join(map(str, row)) for row in data_rows])

    return Response(output,
                    mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=salary_sheet.csv"})
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

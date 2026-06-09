from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Member(db.Model):
    __tablename__ = 'member'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    emp_code = db.Column(db.String(20), unique=True, nullable=False)  # Represents Student Roll Number or Employee Code
    qr_data = db.Column(db.String(150), unique=True, nullable=False)
    daily_salary = db.Column(db.Float, nullable=False, default=0.0)   # 0 for students, daily salary for employees
    role = db.Column(db.String(20), nullable=False, default='employee')  # 'student' or 'employee'
    department = db.Column(db.String(100), nullable=True)             # Class/Grade for students, department for employees

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(20), db.ForeignKey('member.emp_code'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_in = db.Column(db.Time, nullable=False)
    time_out = db.Column(db.Time)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

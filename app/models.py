from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return Employee.query.get(int(user_id))


class Employee(db.Model, UserMixin):
    status = db.Column(db.String(20), default='Active')
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # 'Admin' for CEO/Manager
    role = db.Column(db.String(20), default='Employee')
    department = db.Column(db.String(50), nullable=False)

    # Relationships
    # This links the employee to a specific Position ID
    position_id = db.Column(db.Integer, db.ForeignKey('position.id'))

    # Back-references to track activity
    attendance_records = db.relationship(
        'Attendance', backref='employee', lazy=True)
    leaves = db.relationship('LeaveRequest', backref='employee', lazy=True)
    managed_clients = db.relationship('Client', backref='employee', lazy=True)

    def __repr__(self):
        return f"Employee('{self.full_name}', '{self.email}', '{self.department}')"


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    check_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    check_out = db.Column(db.DateTime)
    employee_id = db.Column(db.Integer, db.ForeignKey(
        'employee.id'), nullable=False)


class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    leave_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    # Pending, Approved, Rejected
    status = db.Column(db.String(20), default='Pending')
    date_posted = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    employee_id = db.Column(db.Integer, db.ForeignKey(
        'employee.id'), nullable=False)

    def __repr__(self):
        return f"LeaveRequest('{self.leave_type}', '{self.status}')"


class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, unique=True)
    base_salary = db.Column(db.Float, default=0.0)
    # The backref 'job_position' allows you to do: employee.job_position.title
    employees = db.relationship('Employee', backref='job_position', lazy=True)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Active')
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('employee.id'))

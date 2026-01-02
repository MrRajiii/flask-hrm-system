from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return Employee.query.get(int(user_id))

# --- 1. EMPLOYEE MODEL ---


class Employee(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # HR Team, Company Owner, Manager, etc.
    role = db.Column(db.String(20), default='Employee')
    department = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Active')

    # Foreign Key for Position
    position_id = db.Column(db.Integer, db.ForeignKey('position.id'))

    # Relationships (backrefs defined in other models appear here automatically)
    # Accessible via: self.job_position, self.attendance_records, self.leaves, self.managed_clients

    attendance_records = db.relationship(
        'Attendance', backref='employee', lazy=True)
    leaves = db.relationship('LeaveRequest', backref='employee', lazy=True)
    managed_clients = db.relationship('Client', backref='employee', lazy=True)

    def __repr__(self):
        return f"Employee('{self.full_name}', '{self.email}', '{self.role}')"


# --- 2. ATTENDANCE MODEL ---
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    check_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    check_out = db.Column(db.DateTime)
    employee_id = db.Column(db.Integer, db.ForeignKey(
        'employee.id'), nullable=False)


# --- 3. LEAVE REQUEST MODEL ---
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


# --- 4. POSITION MODEL ---
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, unique=True)
    base_salary = db.Column(db.Float, default=0.0)
    department = db.Column(db.String(100), nullable=False)

    # This creates the link:
    # employee.job_position -> returns Position object
    # position.employees    -> returns list of Employees
    employees = db.relationship('Employee', backref='job_position', lazy=True)

    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))


# --- 5. CLIENT MODEL ---
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Active')
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('employee.id'))


# --- 6. DEPARTMENT MODEL ---
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    positions = db.relationship('Position', backref='dept', lazy=True)


class PayrollRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey(
        'employee.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    date_processed = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)
    # e.g., "December 2025"
    month_year = db.Column(db.String(20), nullable=False)

    employee = db.relationship(
        'Employee', backref=db.backref('payroll_history', lazy=True))


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    # e.g., Utilities, Rent, Hardware
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_incurred = db.Column(db.Date, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)


class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), default="My Company")
    company_logo_url = db.Column(
        db.String(500), nullable=True)  # Link to an image
    address = db.Column(db.String(200), nullable=True)

    @staticmethod
    def get_settings():
        # This helper ensures we always get the first row (the only one)
        settings = CompanySettings.query.first()
        if not settings:
            settings = CompanySettings(company_name="My Company")
            db.session.add(settings)
            db.session.commit()
        return settings

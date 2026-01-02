from flask import render_template, url_for, flash, redirect, request, abort
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm, LeaveForm, UpdateProfileForm, ChangePasswordForm, PositionForm, ClientForm, ExpenseForm
from app.models import Employee, Attendance, Client, Position, LeaveRequest, PayrollRecord, Expense, CompanySettings
from flask_login import login_user, current_user, logout_user, login_required
from flask import current_app as app
from functools import wraps
from datetime import datetime
from flask import jsonify
from fpdf import FPDF
from flask import send_file, abort
from werkzeug.utils import secure_filename
import os
import io
from flask import make_response

# --- 1. ACCESS CONTROL DECORATORS ---


def finance_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['Finance', 'Company Owner']:
            flash('Access restricted to Finance department.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/get-positions/<string:dept_name>")
def get_positions(dept_name):
    # Search the Position table for the department string name
    print(f"DEBUG: JavaScript requested positions for: {dept_name}")
    positions = Position.query.filter_by(department=dept_name).all()

    pos_list = []
    for pos in positions:
        pos_list.append({'id': pos.id, 'title': pos.title})

    return jsonify({
        'positions': [{'id': p.id, 'title': p.title} for p in positions]
    })


def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Company Owner':
            flash('Access denied. Company Owner privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Add 'Company Owner' to the allowed list
        if current_user.role not in ['HR Team', 'Company Owner']:
            flash('Access denied. HR Team privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Add 'Company Owner' to the allowed list
        if current_user.role not in ['Manager', 'Company Owner']:
            flash('Access denied. Manager privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- 2. DASHBOARD ---


@app.context_processor
def inject_settings():
    return dict(company_settings=CompanySettings.get_settings())


@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    # Gather counts for the Owner dashboard
    stats = {
        'employees': Employee.query.count(),
        'clients': Client.query.count(),
        'positions': Position.query.count()
    }

    # Gather Leave Requests based on role
    if current_user.role in ['HR Team', 'Manager', 'Company Owner']:
        leaves = LeaveRequest.query.filter_by(status='Pending').all()
    else:
        leaves = LeaveRequest.query.filter_by(
            employee_id=current_user.id).all()

    # Department data for Managers
    departments = db.session.query(Employee.department).distinct().all()
    org_data = {dept[0]: Employee.query.filter_by(
        department=dept[0]).all() for dept in departments}

    return render_template('dashboard.html',
                           stats=stats,
                           leaves=leaves,
                           org_data=org_data,
                           title="Dashboard")

# --- 3. AUTHENTICATION ---


@app.route("/register", methods=['GET', 'POST'])
def register():
    # 1. Access Control: Only HR or Owners can onboard new people
    #if not current_user.is_authenticated or current_user.role not in ['HR Team', 'Company Owner']:
        #flash('You do not have permission to access this page.', 'danger')
        #return redirect(url_for('dashboard'))

    form = RegistrationForm()

    # 2. Populate Department Choices (Unique names from the Position table)
    # This fetches all unique department names to fill the first dropdown
    depts = db.session.query(Position.department).distinct().all()
    form.department.choices = [(d[0], d[0]) for d in depts]

    # 3. Dynamic Position Logic
    if request.method == 'POST':
        # During POST, we populate choices with ALL positions.
        # This prevents the "Not a valid choice" validation error because
        # the submitted ID will be found in this full list.
        form.position.choices = [(p.id, p.title) for p in Position.query.all()]
    else:
        # During GET (initial load), we only show positions for the first department
        if depts:
            first_dept = depts[0][0]
            positions = Position.query.filter_by(department=first_dept).all()
            form.position.choices = [(p.id, p.title) for p in positions]
        else:
            form.position.choices = []

    # 4. Form Submission Handling
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(
            form.password.data).decode('utf-8')

        # Create the new Employee object
        user = Employee(
            full_name=form.full_name.data,
            email=form.email.data,
            password=hashed_pw,
            department=form.department.data,
            position_id=form.position.data,  # This stores the integer ID
            role=form.role.data,
            status='Pending'
        )

        try:
            db.session.add(user)
            db.session.commit()
            flash(
                f'Account created for {form.full_name.data} successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(
                'An error occurred while creating the account. Please try again.', 'danger')
            print(f"Error: {e}")

    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Employee.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            # NEW: Check if the user is Active
            if user.status != 'Active':
                flash('Your account is pending approval. Please contact HR.', 'warning')
                return redirect(url_for('login'))

            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Login Unsuccessful. Check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- 4. LEAVE MANAGEMENT ---


@app.route("/apply-leave", methods=['GET', 'POST'])
@login_required
def apply_leave():
    form = LeaveForm()  # Make sure LeaveForm is imported from forms.py
    if form.validate_on_submit():
        leave = LeaveRequest(
            leave_type=form.leave_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            employee_id=current_user.id,
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()
        flash('Leave request submitted!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('apply_leave.html', title='Apply Leave', form=form)


@app.route("/leave/approve/<int:leave_id>")
@login_required
def approve_leave(leave_id):
    # Only Allow HR, Manager, or Owner to approve
    if current_user.role not in ['HR Team', 'Manager', 'Company Owner']:
        abort(403)

    leave = LeaveRequest.query.get_or_404(leave_id)
    leave.status = 'Approved'
    db.session.commit()
    flash(
        f'Leave for {leave.employee.full_name} has been Approved.', 'success')
    return redirect(url_for('dashboard'))


@app.route("/leave/reject/<int:leave_id>")
@login_required
def reject_leave(leave_id):
    if current_user.role not in ['HR Team', 'Manager', 'Company Owner']:
        abort(403)

    leave = LeaveRequest.query.get_or_404(leave_id)
    leave.status = 'Rejected'
    db.session.commit()
    flash(f'Leave for {leave.employee.full_name} has been Rejected.', 'info')
    return redirect(url_for('dashboard'))

# --- 5. OTHER ROUTES (PROTECTED BY ROLES) ---


@app.route("/attendance/clock-in")
@login_required
def clock_in():
    # Check if there is already an open session
    unfinished = Attendance.query.filter_by(
        employee_id=current_user.id, check_out=None).first()
    if unfinished:
        flash('You are already clocked in!', 'warning')
    else:
        new_entry = Attendance(employee_id=current_user.id,
                               check_in=datetime.now())
        db.session.add(new_entry)
        db.session.commit()
        flash('Clocked in successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route("/attendance/clock-out")
@login_required
def clock_out():
    # Find the session that hasn't been closed yet
    record = Attendance.query.filter_by(
        employee_id=current_user.id, check_out=None).first()
    if record:
        record.check_out = datetime.now()
        db.session.commit()
        flash('Clocked out successfully!', 'success')
    else:
        flash('No active clock-in session found.', 'danger')
    return redirect(url_for('dashboard'))

@app.route("/clients")
@login_required
@owner_required
def view_clients():
    clients = Client.query.all()
    return render_template('clients.html', clients=clients)


@app.route("/payroll")
@login_required
@finance_required
def payroll():
    employees = Employee.query.all()
    total_payout = 0

    for emp in employees:
        # We use .job_position because that is the name defined in the backref
        if emp.job_position and emp.job_position.base_salary:
            total_payout += (emp.job_position.base_salary / 12)

    return render_template('payroll.html',
                           employees=employees,
                           total_payout=total_payout,
                           datetime=datetime)


@app.route("/org-chart")
@login_required
@manager_required
def org_chart():
    departments = db.session.query(Employee.department).distinct().all()
    org_data = {dept[0]: Employee.query.filter_by(
        department=dept[0]).all() for dept in departments}
    return render_template('org_chart.html', org_data=org_data)


@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    update_form = UpdateProfileForm()
    password_form = ChangePasswordForm()

    # Handle Profile Info Update
    if update_form.validate_on_submit() and 'full_name' in request.form:
        current_user.full_name = update_form.full_name.data
        current_user.email = update_form.email.data
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))

    # Handle Password Change
    if password_form.validate_on_submit() and 'new_password' in request.form:
        if bcrypt.check_password_hash(current_user.password, password_form.old_password.data):
            hashed_pw = bcrypt.generate_password_hash(
                password_form.new_password.data).decode('utf-8')
            current_user.password = hashed_pw
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Current password incorrect.', 'danger')

    # Pre-fill form with current data
    elif request.method == 'GET':
        update_form.full_name.data = current_user.full_name
        update_form.email.data = current_user.email

    return render_template('profile.html', title='My Profile',
                           update_form=update_form, password_form=password_form)
# --- PAYSLIPS ROUTE ---


@app.route("/my-payslips")
@login_required
def my_payslips():
    # In a full system, you would query a 'Salary' or 'Payroll' model here
    return render_template('my_payslips.html', title='My Payslips')


@app.route("/attendance")
@login_required
def attendance():
    # Fetch all attendance records for the current user, newest first
    page = request.args.get('page', 1, type=int)
    records = Attendance.query.filter_by(employee_id=current_user.id)\
        .order_by(Attendance.check_in.desc())\
        .paginate(page=page, per_page=10)

    return render_template('attendance.html', title='My Attendance', records=records)


@app.route("/positions")
@login_required
@owner_required
def view_positions():
    positions = Position.query.all()
    return render_template('positions.html', positions=positions)


@app.route("/positions/add", methods=['GET', 'POST'])
@login_required
@owner_required
def add_position():
    form = PositionForm()
    if form.validate_on_submit():
        new_pos = Position(
            title=form.title.data,
            department=form.department.data,
            base_salary=form.base_salary.data
        )
        db.session.add(new_pos)
        db.session.commit()
        flash('New position added successfully!', 'success')
        return redirect(url_for('view_positions'))
    return render_template('add_position.html', form=form)


@app.route("/clients/add", methods=['GET', 'POST'])
@login_required
@owner_required
def add_client():
    form = ClientForm()
    if form.validate_on_submit():
        new_client = Client(
            company_name=form.company_name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone=form.phone.data
        )
        db.session.add(new_client)
        db.session.commit()
        flash('Client added successfully!', 'success')
        return redirect(url_for('view_clients'))
    return render_template('add_client.html', form=form)


@app.route("/admin/records")
@login_required
@hr_required
def admin_records():
    pending_users = Employee.query.filter_by(status='Pending').all()
    
    all_attendance = Attendance.query.order_by(
        Attendance.check_in.desc()).limit(50).all()
    all_leaves = LeaveRequest.query.order_by(
        LeaveRequest.date_posted.desc()).all()
    return render_template('records.html', pending_users=pending_users, attendance=all_attendance, leaves=all_leaves)


@app.route("/admin/reject-user/<int:user_id>")
@login_required
@hr_required
def reject_user(user_id):
    user = Employee.query.get_or_404(user_id)
    if user.status == 'Pending':
        db.session.delete(user)
        db.session.commit()
        flash(
            f'Registration for {user.full_name} has been rejected and removed.', 'info')
    return redirect(url_for('admin_records'))

@app.route("/finance/process-payroll", methods=['POST'])
@login_required
@finance_required
def process_all_salaries():
    employees = Employee.query.filter_by(status='Active').all()
    current_month = datetime.now().strftime('%B %Y')

    # Simple check to prevent double-processing same month
    existing_record = PayrollRecord.query.filter_by(
        month_year=current_month).first()
    if existing_record:
        flash(
            f'Payroll for {current_month} has already been processed!', 'warning')
        return redirect(url_for('payroll'))

    for emp in employees:
        if emp.job_position:
            monthly_pay = emp.job_position.base_salary / 12
            record = PayrollRecord(
                employee_id=emp.id,
                amount_paid=monthly_pay,
                month_year=current_month
            )
            db.session.add(record)

    db.session.commit()
    flash(
        f'Successfully processed payroll for {len(employees)} employees for {current_month}.', 'success')
    return redirect(url_for('payroll'))


@app.route("/finance/expenses", methods=['GET', 'POST'])
@login_required
@finance_required
def manage_expenses():
    form = ExpenseForm()
    if form.validate_on_submit():
        new_expense = Expense(
            description=form.description.data,
            category=form.category.data,
            amount=form.amount.data,
            date_incurred=form.date_incurred.data
        )
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense logged successfully!', 'success')
        return redirect(url_for('manage_expenses'))

    all_expenses = Expense.query.order_by(Expense.date_incurred.desc()).all()
    total_expenses = sum(exp.amount for exp in all_expenses)
    return render_template('expenses.html', form=form, expenses=all_expenses, total=total_expenses)


@app.route("/employee/update_status/<int:emp_id>", methods=['POST'])
@login_required
def update_status(emp_id):
    if current_user.role not in ['HR Team', 'Manager', 'Company Owner']:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))

    employee = Employee.query.get_or_404(emp_id)
    employee.status = 'Inactive' if employee.status == 'Active' else 'Active'
    db.session.commit()
    flash(f'Status updated for {employee.full_name}', 'success')
    return redirect(url_for('org_chart'))


@app.route("/download-payslip/<int:record_id>")
@login_required
def download_payslip(record_id):
    record = PayrollRecord.query.get_or_404(record_id)

    # Get the dynamic settings
    settings = CompanySettings.get_settings()

    # Security check
    if record.employee_id != current_user.id and current_user.role != 'Company Owner':
        abort(403)

    pdf = FPDF()
    pdf.add_page()

    # --- DYNAMIC HEADER ---
    pdf.set_font("helvetica", 'B', 20)
    # Uses the name you set in the Settings page!
    pdf.cell(190, 10, f"{settings.company_name.upper()}", ln=True, align='C')

    pdf.set_font("helvetica", 'B', 12)
    pdf.cell(190, 10, "OFFICIAL PAYROLL STATEMENT", ln=True, align='C')
    pdf.ln(10)

    # Employee Details
    pdf.set_font("helvetica", '', 11)
    pdf.cell(95, 8, f"Employee: {record.employee.full_name}")
    pdf.cell(
        95, 8, f"Date: {record.date_processed.strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(95, 8, f"ID: #EMP-00{record.employee.id}")
    pdf.cell(95, 8, f"Period: {record.month_year}", ln=True, align='R')
    pdf.ln(10)

    # Earnings Table
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("helvetica", 'B', 11)
    pdf.cell(140, 10, "Description", border=1, fill=True)
    pdf.cell(50, 10, "Amount", border=1, fill=True, ln=True, align='C')

    pdf.set_font("helvetica", '', 11)
    pdf.cell(140, 10, f"Monthly Salary - {record.month_year}", border=1)
    pdf.cell(50, 10, f"${'{:,.2f}'.format(record.amount_paid)}",
             border=1, ln=True, align='C')

    # Total
    pdf.ln(5)
    pdf.set_font("helvetica", 'B', 12)
    pdf.cell(140, 10, "NET DISBURSED", border=0, align='R')
    pdf.cell(50, 10, f"${'{:,.2f}'.format(record.amount_paid)}",
             border=1, ln=True, align='C')

    # Footer
    pdf.ln(20)
    pdf.set_font("helvetica", 'I', 8)
    pdf.cell(
        190, 5, f"This is a computer-generated document from {settings.company_name} HRMS.", align='C', ln=True)

    pdf_output = pdf.output()
    buffer = io.BytesIO(pdf_output)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Payslip_{record.month_year.replace(' ', '_')}.pdf",
        mimetype='application/pdf'
    )


@app.route("/settings", methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'Company Owner':
        abort(403)

    settings = CompanySettings.get_settings()

    if request.method == 'POST':
        settings.company_name = request.form.get('company_name')
        if 'logo_file' in request.files:
            file = request.files['logo_file']
            if file and file.filename != '':
                # Secure the name and save it
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Save the relative path to the database
                settings.company_logo_url = url_for(
                    'static', filename='company_logos/' + filename)

        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', settings=settings)


@app.route("/admin/approve-user/<int:user_id>")
@login_required
@hr_required
def approve_user(user_id):
    user = Employee.query.get_or_404(user_id)
    user.status = 'Active'
    db.session.commit()
    flash(f'Account for {user.full_name} has been approved!', 'success')
    return redirect(url_for('admin_records'))


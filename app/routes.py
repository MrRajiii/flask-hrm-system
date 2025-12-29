from flask import render_template, url_for, flash, redirect, request, abort
from app import db, bcrypt
from app.forms import RegistrationForm, LoginForm, LeaveForm, UpdateProfileForm, ChangePasswordForm
from app.models import Employee, Attendance, Client, Position, LeaveRequest
from flask_login import login_user, current_user, logout_user, login_required
from flask import current_app as app
from functools import wraps
from datetime import datetime
from flask import jsonify

# --- 1. ACCESS CONTROL DECORATORS ---


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
        if not current_user.is_authenticated or current_user.role != 'HR Team':
            flash('Access denied. HR Team privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Manager':
            flash('Access denied. Manager privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- 2. DASHBOARD ---


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
            status='Active'
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
@hr_required
def payroll():
    employees = Employee.query.all()
    total_payout = 0

    for emp in employees:
        # We use .job_position because that is the name defined in the backref
        if emp.job_position and emp.job_position.base_salary:
            total_payout += (emp.job_position.base_salary / 12)

    return render_template('payroll.html',
                           employees=employees,
                           total_payout=total_payout)


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
    # You'll eventually need a PositionForm in forms.py for this
    # For now, this will just render a placeholder or the form page
    return render_template('add_position.html', title='Add New Position')


@app.route("/clients/add", methods=['GET', 'POST'])
@login_required
@owner_required
def add_client():
    # This is a placeholder until you create the ClientForm
    return render_template('add_client.html', title='Add New Client')
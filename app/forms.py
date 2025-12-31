from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import Employee, Position
from wtforms.fields import DateField
from flask_login import current_user


class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
                            DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])

    # Updated Department choices to align with new roles if necessary
    department = SelectField('Department', choices=[
        ('', 'Select Department'),  # Added an empty default choice
        ('IT', 'IT'),
        ('HR', 'HR'),
        ('Sales', 'Sales'),
        ('Executive', 'Executive')
    ], validators=[DataRequired()])

    # NEW: Role selection for strict access control
    role = SelectField('Access Level', choices=[
        ('Employee', 'Employee'),
        ('HR Team', 'HR Team'),
        ('Finance', 'Finance'),
        ('Manager', 'Manager'),
        ('Company Owner', 'Company Owner')
    ], validators=[DataRequired()])

    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])

    position = SelectField('Position', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Create Account')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        # Dynamically load positions from database into the dropdown
        # Added a check to prevent errors if the DB isn't initialized yet
        self.position.choices = []
        try:
            self.position.choices = [(p.id, p.title)
                                     for p in Position.query.all()]
        except:
            self.position.choices = []

    def validate_email(self, email):
        user = Employee.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already taken.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class LeaveForm(FlaskForm):
    leave_type = SelectField('Leave Type', choices=[(
        'Sick', 'Sick'), ('Annual', 'Annual'), ('Casual', 'Casual')])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    submit = SubmitField('Submit Request')


class UpdateProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update Profile')

    def validate_email(self, email):
        if email.data != current_user.email:
            user = Employee.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is already taken.')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField(
        'Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password',
                                      validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')


class PositionForm(FlaskForm):
    title = StringField('Position Title', validators=[DataRequired()])
    department = SelectField('Department', choices=[
        ('IT', 'IT'), ('HR', 'HR'), ('Sales', 'Sales'), ('Executive', 'Executive')
    ], validators=[DataRequired()])
    base_salary = FloatField('Annual Base Salary', validators=[DataRequired()])
    submit = SubmitField('Save Position')


class ClientForm(FlaskForm):
    company_name = StringField('Company Name', validators=[DataRequired()])
    contact_person = StringField('Contact Person')
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    submit = SubmitField('Add Client')


class ExpenseForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('Utilities', 'Utilities'),
        ('Rent', 'Rent'),
        ('Software', 'Software/Subscriptions'),
        ('Marketing', 'Marketing'),
        ('Office Supplies', 'Office Supplies'),
        ('Travel', 'Travel'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    date_incurred = DateField(
        'Date Incurred', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Log Expense')

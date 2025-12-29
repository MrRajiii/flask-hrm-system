from app import create_app, db, bcrypt
from app.models import Employee, Position

app = create_app()


def seed_database():
    with app.app_context():
        # 1. Clear existing data
        db.drop_all()
        db.create_all()

        print("Creating positions...")
        # 2. Define Positions grouped by Department
        positions_data = [
            # IT Department
            {'title': 'Software Engineer', 'dept': 'IT', 'salary': 60000},
            {'title': 'IT Support Specialist', 'dept': 'IT', 'salary': 35000},
            {'title': 'Cybersecurity Analyst', 'dept': 'IT', 'salary': 55000},

            # HR Department
            {'title': 'HR Manager', 'dept': 'HR', 'salary': 50000},
            {'title': 'Recruiter', 'dept': 'HR', 'salary': 30000},
            {'title': 'Payroll Officer', 'dept': 'HR', 'salary': 32000},

            # Executive Department
            {'title': 'CEO', 'dept': 'Executive', 'salary': 150000},
            {'title': 'Operations Manager', 'dept': 'Executive', 'salary': 80000}
        ]

        for pos in positions_data:
            new_pos = Position(
                title=pos['title'], department=pos['dept'], base_salary=pos['salary'])
            db.session.add(new_pos)

        # 3. Create a Default Admin/Owner
        hashed_password = bcrypt.generate_password_hash(
            'admin123').decode('utf-8')
        admin = Employee(
            full_name="Company Owner",
            email="owner@company.com",
            password=hashed_password,
            role="Company Owner",
            department="Executive",
            status="Active"
        )
        db.session.add(admin)

        db.session.commit()
        print("Database seeded successfully!")


if __name__ == "__main__":
    seed_database()

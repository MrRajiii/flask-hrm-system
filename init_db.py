from app import create_app, db
from app.models import Position

app = create_app()

with app.app_context():
    print("Deleting old database...")
    db.drop_all()  # This clears everything out automatically

    print("Creating new tables...")
    db.create_all()

    # Create the default CEO position so the forms work
    if not Position.query.filter_by(title="CEO").first():
        ceo = Position(title="CEO", base_salary=150000.0)
        db.session.add(ceo)
        db.session.commit()
        print("Success: Database reset and CEO position created.")

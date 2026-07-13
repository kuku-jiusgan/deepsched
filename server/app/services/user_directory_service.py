from app.models import User


def list_user_directory(db):
    return db.query(User).order_by(User.id).all()
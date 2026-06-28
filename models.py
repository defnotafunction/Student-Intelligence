from extension import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, index=True,  nullable=False)
    hashed_password = db.Column(db.String(20),  nullable=False)
    courses = db.relationship('Course', backref='user', lazy='dynamic', cascade="all, delete-orphan")

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String,  nullable=False)
    grade = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    assessment_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    practice_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
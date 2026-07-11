from extension import db
from flask_login import UserMixin
from datetime import datetime, timezone

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, index=True,  nullable=False)
    hashed_password = db.Column(db.String(20),  nullable=False)
    courses = db.relationship('Course', backref='user', lazy='dynamic', cascade='all, delete-orphan')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String,  nullable=False)
    grade = db.Column(db.Numeric(precision=5, scale=2), nullable=False)  # Current Grade
    assessment_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    practice_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    grades = db.relationship('Grade', backref='course', lazy='dynamic', cascade='all, delete-orphan')  # Tracks all grade inputs

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    percentage = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

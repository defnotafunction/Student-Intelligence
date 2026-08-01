from flask_login import UserMixin
from datetime import datetime, timezone
from extension import db

def get_default_school_start_datetime() -> datetime:
    """Returns a datetime object that holds the usual first day of school which is the third monday of August in the year the user is currently in."""

    year = datetime.today().year
    month = 8

    # Looking for the third monday
    mondays_counted = 0

    for day in range(1, 32):
        datetime_obj = datetime(year, month, day)

        if datetime_obj.strftime("%A") == 'Monday':
            mondays_counted += 1

        if mondays_counted >= 3:
            return datetime_obj

def get_default_school_end_datetime() -> datetime:
    """Returns a datetime object that holds the usual last day of school which is the last friday of May in the year after the year the user is currently in."""

    year = datetime.today().year + 1
    month = 5

    for day in range(31, 1, -1):
        datetime_obj = datetime(year, month, day, hour=23, minute=59)
        
        if datetime_obj.strftime("%A") == 'Friday':
            return datetime_obj


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, index=True,  nullable=False)
    hashed_password = db.Column(db.String(225),  nullable=False)
    courses = db.relationship('Course', backref='user', cascade='all, delete-orphan')
    start_of_school_date = db.Column(db.DateTime, default=get_default_school_start_datetime)
    end_of_school_date = db.Column(db.DateTime, default=get_default_school_end_datetime)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String,  nullable=False)
    grade = db.Column(db.Numeric(precision=5, scale=2), nullable=False)  # Current Grade
    assessment_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    practice_weight = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    grade_goal = db.Column(db.Numeric(precision=5, scale=2), nullable=False)  # Grade to reach
    grades = db.relationship('Grade', backref='course', cascade='all, delete-orphan')  # Tracks all grade inputs

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    percentage = db.Column(db.Numeric(precision=5, scale=2), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

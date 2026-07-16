from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, DecimalField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class LoginForm(FlaskForm):
    """Form used in the Login route."""
    username = StringField('Username', validators=[Length(min=5, max=22), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Submit')

class AddCourseForm(FlaskForm):
    """Form used in the Courses route."""
    course_name = StringField('Name', validators=[DataRequired()])
    practice_of_standards_weight = IntegerField('Practice of Standards Weight', validators=[DataRequired(), NumberRange(min=0)])
    assessment_of_standards_weight = IntegerField('Assessment of Standards Weight', validators=[DataRequired(), NumberRange(min=0)])
    practice_of_standards_grade = DecimalField('Practice of Standards Grade', validators=[DataRequired(), NumberRange(min=0)])
    assessment_of_standards_grade = DecimalField('Assessment of Standards Grade', validators=[DataRequired(), NumberRange(min=0)])
    grade_goal = DecimalField('Goal (Grade to reach)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit')

class DeleteCourseForm(FlaskForm):
    """Form used in the Courses route."""
    submit = SubmitField('Delete')

class UpdateCourseForm(FlaskForm):
    """Form used in the Courses route."""
    new_grade = DecimalField('New Grade', validators=[DataRequired(), NumberRange(min=0)])
    grade_goal = DecimalField('Goal (Not Required)', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Save')

class LoadCourseAdvice(FlaskForm):
    """Form used in the Dashboard route."""
    submit = SubmitField('Load')
    

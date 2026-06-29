from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[Length(min=5, max=22), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Submit')

class AddCourseForm(FlaskForm):
    course_name = StringField('Name', validators=[DataRequired()])
    practice_of_standards_weight = IntegerField('Practice of Standards Weight', validators=[DataRequired(), NumberRange(min=0)])
    assessment_of_standards_weight = IntegerField('Assessment of Standards Weight', validators=[DataRequired(), NumberRange(min=0)])
    practice_of_standards_grade = IntegerField('Practice of Standards Grade', validators=[DataRequired(), NumberRange(min=0)])
    assessment_of_standards_grade = IntegerField('Assessment of Standards Grade', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit')

class DeleteCourseForm(FlaskForm):
    submit = SubmitField('Delete')

class UpdateCourseForm(FlaskForm):
    new_grade = IntegerField('New Grade', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Save')
    

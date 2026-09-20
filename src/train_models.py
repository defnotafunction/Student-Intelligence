from .app import app
from .helper import train_model_on_user_grade_data

with app.app_context():
    train_model_on_user_grade_data(app)
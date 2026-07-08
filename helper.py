from sqlalchemy import select
from models import *
from extension import * 
from werkzeug.security import generate_password_hash
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator

def app_context_wrapper(func: callable):
    def inner(*args, **kwargs):        
        with app.app_context():
            result = func(*args, **kwargs)
            return result

    return inner

@app_context_wrapper
def get_user_from_username(db: SQLAlchemy, username: str):
    statement = select(User).where(User.username == username)
    return db.session.execute(statement).scalars().first()

def get_user_exists(db: SQLAlchemy, username: str) -> bool:
    return get_user_from_username(db, username) is not None

def create_and_save_user(db: SQLAlchemy, username: str, unhashed_password: str) -> User:
    hashed_password = generate_password_hash(unhashed_password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return new_user

def create_grades_vs_time(datetimes: list[datetime], grades: list[float]) -> str:
    if len(datetimes) < 1:
        return None
    
    min_date = min(datetimes)
    days_from_min =  sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])  # Convert seconds into days
    fig = go.Figure(data=go.Scatter(x=days_from_min, y=grades, mode='lines+markers'))
    fig.update_layout(
        title="Grades over time",
        xaxis_title="Days",
        yaxis_title="Grades"
                    )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
        )

    return graph_html

def predict_grades_from_datetimes(datetimes: list[datetime], grades: list[float], days_into_future: int):
    min_date = min(datetimes)
    days_from_min = sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])
    future_days = [days_from_min[-1] + i for i in range(1, days_into_future)]
    
    nested_days_from_min = [[d] for d in days_from_min]
    nested_future_days = [[d] for d in future_days]
    
    
    model_pipeline = Pipeline(steps=[
        ('spline', StandardScaler()),
        ('regressor', SVR(kernel='rbf', C=500, epsilon=0.1, gamma='scale'))
        ])
    model_pipeline.fit(nested_days_from_min, grades)
    current_days_predictions = model_pipeline.predict(nested_days_from_min)
    future_days_predictions = model_pipeline.predict(nested_future_days)
    predictions = [*current_days_predictions, * future_days_predictions]
    
    return predictions

def create_grades_vs_time_with_predictions(datetimes: list[datetime], grades: list[float], days_into_future: int) -> str:
    if len(datetimes) < 1:
        return None
    
    min_date = min(datetimes)
    days_from_min =  sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])  # Convert seconds into days
    
    predictions = predict_grades_from_datetimes(datetimes, grades, days_into_future)
    
    fig = go.Figure(data=go.Scatter(x=days_from_min, y=grades, mode='lines+markers'))
    
    fig.add_trace(
        go.Scatter(
        x=[*days_from_min, *[days_from_min[-1] + i for i in range(1, days_into_future)]],
        y=predictions,
        mode='lines',
        name='Estimation'
        )
    )
    fig.update_layout(
        title="Grades over time",
        xaxis_title="Days",
        yaxis_title="Grades"
                    )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
        )

    return graph_html
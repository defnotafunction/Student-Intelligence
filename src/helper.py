from sqlalchemy import select
from .models import *
from .extension import *
from datetime import timedelta
from werkzeug.security import generate_password_hash
from google import genai
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import joblib

torch.manual_seed(42)
np.random.seed(42)

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
GRADE_FORECASTER_MODEL_PATH = os.path.join('data', 'mlmodels', 'supervised_grade_forecaster.pkl')

def app_context_wrapper(func: callable):
    def inner(*args, **kwargs):        
        with app.app_context():
            result = func(*args, **kwargs)
            return result

    return inner

# SQLALCHEMY FUNCTIONS
@app_context_wrapper
def get_user_from_username(db: SQLAlchemy, username: str):
    statement = select(User).where(User.username == username)
    return db.session.execute(statement).scalars().first()

def get_user_exists(db: SQLAlchemy, username: str) -> bool:
    return get_user_from_username(db, username) is not None

def create_and_save_user(db: SQLAlchemy, username: str, unhashed_password: str, **extra_attributes) -> User:
    hashed_password = generate_password_hash(unhashed_password)
    new_user = User(username=username, hashed_password=hashed_password, **extra_attributes)
    db.session.add(new_user)
    db.session.commit()
    return new_user

# PLOTLY / SKLEARN FUNCTIONS
def create_grades_vs_time(title: str, datetimes: list[datetime], grades: list[float]) -> str:
    """
    Creates and returns a graph by using datetimes as the x-axis and grades as the y-axis.

    This function is for creating a visualization of a user's grade progress in a specific course.

    Args:
        title: A string that determines the title of the graph.
        datetimes: A list of datetime objects.
        grades: A list of floating point values within the range of 0-inf.

    Returns:
        A string with the HTML representation of the created graph.

    """
    import plotly.graph_objects as go
    
    if len(datetimes) < 1:
        return None
    
    min_date = min(datetimes)
    days_from_min =  sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])  # Convert seconds into days
    fig = go.Figure(data=go.Scatter(x=days_from_min, y=grades, mode='lines+markers'))
    fig.update_layout(
        title=title,
        xaxis_title="Day (Since Creation of Course)",
        yaxis_title="Grade"
                    )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
        )

    return graph_html

def create_data_for_grade_prediction(
        datetimes: list[datetime],
        grades: list[float],
        start_of_school_date: datetime,
        end_of_school_date: datetime
        ) -> tuple[list[list], list[float]]:
    """
    Creates examples with engineered features using datetimes and grades for grade prediction.
    
    Args:
        datetimes: A list of datetime objects.
        grades: A list of numbers ranging from 0-100.
        start_of_school_date: A datetime object representing a user's start of their school year's date.
        end_of_school_date: A datetime object representing a user's end of their school year's date.
    
    Returns:
        A list of examples and a list of float values representing grades.
    """ 
    examples = []

    def append_velocity_feature(examples: list[list]):
        """Appends the velocity, or rate of change, to the end of every example in examples."""
        # LAST KNOWN VELOCITY
        for example_idx, example in enumerate(examples):
            if example_idx == 0:
                examples[example_idx].append(0)
                continue

            # VELOCITY OF LAST POINT TO CURRENT POINT
            difference_of_time = float(example[0] - examples[example_idx-1][0])
            difference_of_grade = float(grades[example_idx] - grades[example_idx-1])

            velocity = difference_of_grade / difference_of_time
            examples[example_idx].append(velocity)

    # Split time from start_of_school_date to end_of_school_date into
    #  4 equal parts to add quarters of the school year as a feature 
    def append_one_hot_quarter_features() -> None:
        """Appends a one hot representation of what quarter the current user is in."""
        duration_of_school = end_of_school_date - start_of_school_date
        quarter_of_school = duration_of_school / 4

        dividers = [start_of_school_date + (quarter_of_school * i) for i in range(3)]  # Three dividers to divide the 4 quarters
        min_date = min(datetimes)

        # ONE HOT QUARTERS
        for day_datetime in datetimes:
            days_since_first_record = (day_datetime - min_date).total_seconds() / 86400  # To differentiate grades tracked on the same day

            if start_of_school_date <= day_datetime < dividers[0]:
                one_hot_quarter = [1, 0, 0, 0]
                
            elif dividers[0] <= day_datetime < dividers[1]:
                one_hot_quarter = [0, 1, 0, 0]

            elif dividers[1] <= day_datetime < dividers[2]:
                one_hot_quarter = [0, 0, 1, 0]

            elif dividers[2] <= day_datetime < end_of_school_date:
                one_hot_quarter = [0, 0, 0, 1]

            else:
                one_hot_quarter = [0, 0, 0, 0]

            examples.append([days_since_first_record, *one_hot_quarter])

    append_one_hot_quarter_features()
    append_velocity_feature(examples)

    return np.asarray(examples, dtype=np.float32), np.asarray(grades, dtype=np.float32)

def create_data_for_grade_prediction_from_course(user: User, course_index: int) -> list[float]:
    """
    Returns a list of samples with engineered features by using a user's course.
    
    Args:
        user: A User object.
        course_index: The index of the course in the user's course list to use for grade data.
    
    Returns:
        A sample with engineered features / A list with numbers.
    """

    course: Course = user.courses[course_index]
    course_grades = course.grades
    grades_datetimes_tracked = [grade.date_created for grade in course_grades]
    start_of_school_date = user.start_of_school_date
    end_of_school_date = user.end_of_school_date

    examples, targets = create_data_for_grade_prediction(
        datetimes=grades_datetimes_tracked,
        grades=course_grades,
        start_of_school_date=start_of_school_date,
        end_of_school_date=end_of_school_date
        )

    return examples, targets

def train_model_on_user_grade_data(app: Flask) -> None:
    """
    Extracts grade data from every user that enables the option to have their data used for training, trains a model to predict future grades, and saves it.
    
    Args:
        app: A Flask object.
    """
    # Lazy importing
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from skorch.net import NeuralNet

    with app.app_context():
        users: list[User] = db.session.scalars(db.select(User).where(User.data_analysis_consent == True)).all()
        examples = []
        targets = []

        if len(users) == 0:
            return 

        # Iterates through every grade in every course to create features
        for user in users:
            for course_index in range(len(user.courses)):
                course = user.courses[course_index]

                course_grades = [grade.percentage for grade in course.grades]
                grade_dates = [grade.date_created for grade in course.grades]

                if len(course_grades) == 0:
                    continue

                engineered_examples, grades = create_data_for_grade_prediction(
                    grade_dates,
                    course_grades,
                    start_of_school_date=user.start_of_school_date,
                    end_of_school_date=user.end_of_school_date
                    )
                examples.extend(engineered_examples)
                targets.extend(grades)

        examples = np.array(examples)
        targets = np.array(targets)

        if len(examples) == 0:
            return

        network = nn.Sequential(
                    nn.Linear(examples.shape[1], 16),
                    nn.ReLU(),
                    nn.Linear(16, 1),
                    nn.Sigmoid()  # Returns a decimal 0-1 which can then be multiplied by 100 to represent a grade
                )
        # CREATING / FITTING MODEL
        model_pipeline = Pipeline(steps=[
            ('scaler', StandardScaler()),
            ('regressor', NeuralNet(
                network,
                criterion=nn.MSELoss,
                optimizer=optim.Adam,
                lr=0.001,
                train_split=None,
                max_epochs=500
                )
            )
        ])

        model_pipeline.fit(examples, targets)
        joblib.dump(model_pipeline, GRADE_FORECASTER_MODEL_PATH)

def predict_grades(
        course_index: int,
        days_into_future: int,
        current_user: User
                    ) -> list[float]:
    """
    Predicts future grades by fitting a feed-forward network on grade data.

    This function converts the datetimes to the amount of days since the earliest datetime and calculates the rate of change in between each point for the features.
    
    Args:
        course_index: The index of the course in the user's courses list.
        days_into_future: An integer that determines how many future days the model will predict for.
        current_user: A user object

    Returns:
        A list of the model's predictions as floating point values.

    """

    course = current_user.courses[course_index]
    future_days = [
        course.grades[-1].date_created + timedelta(days=i+1) for i in range(days_into_future)
        ]
    examples_to_predict, _ = create_data_for_grade_prediction(
        datetimes=future_days,
        grades=[course.grades[-1].percentage for i in range(days_into_future)],  # A list full of the latest grade percentage
        start_of_school_date=current_user.start_of_school_date,
        end_of_school_date=current_user.end_of_school_date
    )
    examples_to_predict = np.asarray(examples_to_predict, dtype=np.float32)

    try:
        model = joblib.load(GRADE_FORECASTER_MODEL_PATH)
    except FileNotFoundError:
        return
    
    future_days_predictions = model.predict(examples_to_predict)
    predictions = np.array(future_days_predictions).flatten()

    return predictions * 100  # Convert decimals 0-1 to 0-100 since model uses sigmoid activation function in output layer

def create_grades_vs_time_with_predictions(
        title: str,
        datetimes: list[datetime],
        grades: list[float],
        grade_goal: int,
        days_into_future: int,
        current_user: User,
        course_index: int
        ) -> str:
    """
    Creates and returns a graph by using datetimes for the x-axis, using grades for the y-axis, and fitting a Support Vector Regression model.

    This function is for creating a visualization of a user's grade progress in a specific course.

    Args:
        title: A string that determines the title of the graph.
        datetimes: A list of datetime objects.
        grades: A list of floating point values within the range of 0-inf.
        grade_goal: A floating point value that determines the y-value of the horizontal line that represents the goal of the course.
        days_into_future: An integer that determines how many future days the model will predict for.
        current_user: A User object.
        course_index: The index of the course in the user's courses list that will have their grades plotted.

    Returns:
        A string with the HTML representation of the created graph.

    """
    import plotly.graph_objects as go

    if len(datetimes) < 1:
        return None

    min_date = min(datetimes)
    days_from_min =  sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])  # Convert seconds into days
    
    predictions = predict_grades(
        course_index=course_index,
        days_into_future=days_into_future,
        current_user=current_user
        )

    if predictions is None:
        return
    
    fig = go.Figure(data=go.Scatter(
        x=days_from_min,
        y=grades,
        mode='lines+markers',
        name='Grades')
        )
    
    fig.add_trace(
        go.Scatter(
        x=[days_from_min[-1] + i for i in range(1, days_into_future)],
        y=predictions,
        mode='lines',
        name='Prediction'
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Day",
        yaxis_title="Grade (%)"
                    )
    
    # Grade Goal minimum line
    fig.add_hline(
        y=grade_goal, 
        line_dash="dot", 
        annotation_text="Goal", 
        annotation_position="top left"
    )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'responsive': True}
    )

    return graph_html

# GOOGLE API FUNCTIONS
def query_youtube(query: str, num_results: int = 3) -> list[dict]:
    from youtube_search import YoutubeSearch

    result = YoutubeSearch(query, max_results=num_results)
    return result.videos

def get_gemini_response(user_input: str) -> str:
    interaction = client.interactions.create(
        model="gemini-3.5-flash",
        input=user_input
    )

    return interaction.output_text

# Replace with any other LLM if needed
def prompt_gemini_for_course_advice(course_objects: list[Course]) -> list[str]:
    """
    Sends a prompt to a Gemini Model along with data from every one of the user's courses and recieves a response.

    Args:
        course_objects: A list of the user's courses.
        
    Returns:
        A list with each element holding advice for a course.

    """
    course_prompts = []
    
    if not course_objects:
        return

    for course_obj in course_objects:
        prompt = f"""
                Give me tips and advice on my class, {course_obj.name}, based on the following attributes:
                Current Grade: {course_obj.grade}
                All Grades Oldest-Newest: {[grade_obj.percentage for grade_obj in course_obj.grades]}
                Date created for each list (Parallel list to 'All Grades'): {[grade_obj.date_created for grade_obj in course_obj.grades]}
                My Grade Goal: {course_obj.grade_goal}
                Assessment/Test weight: {course_obj.assessment_weight}
                Practice/Regular Assignment weight: {course_obj.practice_weight}
                Latest grade update: {list(course_obj.grades)[-1].date_created}
                """
        course_prompts.append(prompt)
    
    final_prompt = "\n".join(course_prompts) + "Respond in this format 'CLASS (Class Name): (Advice)'. At the beginning of your response, tell me what class to priortize in the format 'CLASS OVERALL: (your advice)'"

    response = get_gemini_response(final_prompt)
    response = response.split('CLASS')

    return response

# Note Scanner FUNCTIONS
def get_similar_sentences(text_block: str, user_text: str, amount_of_sentences: int):
    """
        Splits the sentences, embeds them, and returns the ones closest to the embedded user_text argument
    
        Args:
            text_block: A string of text.
            user_text: String that'll be used to find the most similar ones.
            amount_of_sentences: An integer that determines how many similar sentences to return.

        Returns:
            A list with the sentences most similar to user_text.
    
    """
    import spacy
    import en_core_web_md
    nlp = en_core_web_md.load()

    new_text = text_block.split('.')

    if len(new_text) == 1:  # If there aren't periods
        new_text = new_text[0].split('\n')

    elif len(new_text) >= 50:  # Convert into paragraphs (4 sentences) instead of block of text is large.
        condensed_new_text = []
        counter = 0
        new_string = ""

        for element in new_text:
            new_string += element + '.'
            counter += 1

            if counter == 4:
                condensed_new_text.append(new_string)
                counter = 0
                new_string = ""
        
        new_text = condensed_new_text

    amount_of_sentences = min(amount_of_sentences, len(new_text))  # Avoid n_neighbors > n_samples_fit error

    sentence_docs = [nlp(sentence) for sentence in new_text]
    user_doc = nlp(user_text)

    most_to_least_similar_sentences = sorted(sentence_docs, reverse=True, key=lambda x: user_doc.similarity(x))
    closest_sentences = most_to_least_similar_sentences[:3]

    closest_sentences = list(map(str, closest_sentences))
    
    return closest_sentences

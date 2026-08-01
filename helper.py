from sqlalchemy import select
from models import *
from extension import *
from datetime import timedelta
from werkzeug.security import generate_password_hash
import plotly.graph_objects as go
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from google import genai
import spacy
import en_core_web_sm

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
nlp = en_core_web_sm.load()

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

def create_and_save_user(db: SQLAlchemy, username: str, unhashed_password: str) -> User:
    hashed_password = generate_password_hash(unhashed_password)
    new_user = User(username=username, hashed_password=hashed_password)
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

def predict_grades(datetimes: list[datetime],
                    start_of_school_date: datetime,
                    end_of_school_date: datetime,
                    grades: list[float],
                    days_into_future: int
                    ) -> list[float]:
    """
    Predicts future grades by fitting datetimes and grades data to a Support Vector Regression model.

    This function converts the datetimes to the amount of days since the earliest datetime.
    It then normalizes the data using Z-score normalization before fitting it to a Support Vector Regression model to predict future grades.

    Args:
        datetimes: A list of datetime objects.
        start_of_school_date: A datetime object containing the first day of the user's school year.
        end_of_school_date: A datetime object containing the last day of the user's school year.
        grades: A list of floating point values within the range of 0-inf.
        days_into_future: An integer that determines how many future days the model will predict for.

    Returns:
        A list of the model's predictions as floating point values.

    """
    # FEATURE ENGINEERING
    min_date = min(datetimes)
    days_from_min = sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])
    future_days = [days_from_min[-1] + i for i in range(1, days_into_future)]

    # Split time from start_of_school_date to end_of_school_date into
    #  4 equal parts to add quarters of the school year as a feature 
    duration_of_school = end_of_school_date - start_of_school_date
    quarter_of_school = duration_of_school / 4
    dividers = [start_of_school_date + (quarter_of_school * i) for i in range(3)]  # Three dividers to divide the 4 quarters

    def create_examples(list_of_days: list[int]) -> list[int]:
        examples = []

        for day in list_of_days:
            day_datetime = min_date + timedelta(days=day)

            # One hot encode quarters
            if start_of_school_date <= day_datetime < dividers[0]:
                one_hot_quarter = [1, 0, 0, 0]
                examples.append([day, *one_hot_quarter])
    
            elif dividers[0] <= day_datetime < dividers[1]:
                one_hot_quarter = [0, 1, 0, 0]
                examples.append([day, *one_hot_quarter])
    
            elif dividers[1] <= day_datetime < dividers[2]:
                one_hot_quarter = [0, 0, 1, 0]
                examples.append([day, *one_hot_quarter])
    
            elif dividers[2] <= day_datetime < end_of_school_date:
                one_hot_quarter = [0, 0, 0, 1]
                examples.append([day, *one_hot_quarter])

            else:
                one_hot_quarter = [0, 0, 0, 0]
                examples.append([day, *one_hot_quarter])

        return examples

    future_inputs = create_examples(future_days)
    examples = create_examples(days_from_min)
    
    # CREATING / FITTING MODEL
    model_pipeline = Pipeline(steps=[
        ('scaler', StandardScaler()),
        ('regressor', SVR(kernel='rbf', C=1000, epsilon=0.1, gamma='scale'))
    ])
    model_pipeline.fit(examples, grades)
    current_days_predictions = model_pipeline.predict(examples)
    future_days_predictions = model_pipeline.predict(future_inputs)
    predictions = [*current_days_predictions, *future_days_predictions]

    return predictions

def create_grades_vs_time_with_predictions(
        title: str,
        datetimes: list[datetime],
        grades: list[float],
        grade_goal: int,
        school_start_date: datetime,
        school_end_time: datetime,
        days_into_future: int
        ) -> str:
    """
    Creates and returns a graph by using datetimes for the x-axis, using grades for the y-axis, and fitting a Support Vector Regression model.

    This function is for creating a visualization of a user's grade progress in a specific course.

    Args:
        title: A string that determines the title of the graph.
        datetimes: A list of datetime objects.
        grades: A list of floating point values within the range of 0-inf.
        grade_goal: A floating point value that determines the y-value of the horizontal line that represents the goal of the course.
        school_start_date: A datetime object that represents the start of the user's school year.
        school_end_date: A datetime object that represents the end of a the user's school year.
        days_into_future: An integer that determines how many future days the model will predict for.

    Returns:
        A string with the HTML representation of the created graph.

    """

    if len(datetimes) < 1:
        return None
    
    min_date = min(datetimes)
    days_from_min =  sorted([(d - min_date).total_seconds() / 86400 for d in datetimes])  # Convert seconds into days
    
    predictions = predict_grades(
        datetimes=datetimes,
        grades=grades,
        days_into_future=days_into_future,
        start_of_school_date=school_start_date,
        end_of_school_date=school_end_time
        )
    
    fig = go.Figure(data=go.Scatter(
        x=days_from_min,
        y=grades,
        mode='lines+markers',
        name='Grades')
        )
    
    fig.add_trace(
        go.Scatter(
        x=[*days_from_min, *[days_from_min[-1] + i for i in range(1, days_into_future)]],
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

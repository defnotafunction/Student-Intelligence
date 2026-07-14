from flask import render_template, redirect, url_for, flash, request
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from sqlalchemy import select
import os
from forms import *
from helper import *
from extension import *



login_manager = LoginManager()
login_manager.login_view = 'login'

db.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        input_username = login_form.username.data
        input_password = login_form.password.data
        
        if get_user_exists(db, input_username):
            user = get_user_from_username(db, input_username)
            
            if check_password_hash(user.hashed_password, input_password):
                login_user(user)
                return redirect(url_for('index'))
            
        flash('Wrong username or password.')

    return render_template('login.html', page_name='Login', form=login_form)

@app.route('/sign-in', methods=['GET', 'POST'])
def signin():
    signin_form = LoginForm()  # The LoginForm has the same fields signing in needs.
    
    if signin_form.validate_on_submit():
        input_username = signin_form.username.data
        input_password = signin_form.password.data
        
        if get_user_exists(db, input_username):
            flash('User already exists.')
        else:
            user = create_and_save_user(db, input_username, input_password)
            login_user(user, remember=True)
            return redirect(url_for('index'))

    return render_template('login.html', page_name='Sign In', form=signin_form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Creating graphs for each course
    made_graphs = []
    result_links = []

    for course in current_user.courses:
        data = [(g.date_created, g.percentage) for g in course.grades]
            
        datetimes, grades = zip(*data)
        datetimes, grades = list(datetimes), list(grades)
        graph_html = create_grades_vs_time_with_predictions(
            title=course.name,
            datetimes=datetimes,
            grades=grades,
            grade_goal=course.grade_goal,
            days_into_future=20,
            )
        made_graphs.append(graph_html)

    # Recommending videos based on difference of course grade and its goal (How far it is from goal)
    if list(current_user.courses):
        lowest_grade_course = min(current_user.courses, key=lambda x: x.grade_goal - x.grade)
        results = query_youtube(lowest_grade_course.name)
        result_links = ['https://youtube.com/embed/' + r['id'] for r in results]

    return render_template(
        'dashboard.html',
        made_graphs=made_graphs,
        recommended_videos=result_links
        )    
        
    


@app.route('/courses', methods=['GET', 'POST'])
@login_required
def courses():
    delete_course_form = DeleteCourseForm()
    add_course_form = AddCourseForm()
    update_course_form = UpdateCourseForm()
    dropdown_update_course = None
    dropdown_update_course_id = request.form.get('update_course_id')  # Course ID from the Dropdown Box of Change Courses
    dropdown_graph_course_id = request.form.get('graph_course_id')
    
    # Default update form / graph that'll pop up if user didn't select
    if len(list(current_user.courses)) >= 1:
        if dropdown_update_course_id is None:
            dropdown_update_course_id = current_user.courses[0].id

        if dropdown_graph_course_id is None:
            dropdown_graph_course_id = current_user.courses[0].id
       

    graph_html = None
    # ITEM 2 ADD COURSE
    if add_course_form.validate_on_submit():
        assessment_grade = float(add_course_form.assessment_of_standards_grade.data) * (add_course_form.assessment_of_standards_weight.data / 100)
        practice_grade = float(add_course_form.practice_of_standards_grade.data) * (add_course_form.practice_of_standards_weight.data / 100)
        final_grade = assessment_grade + practice_grade

        new_course = Course(
            user_id=current_user.id,
            name=add_course_form.course_name.data,
            grade=final_grade,
            assessment_weight=add_course_form.assessment_of_standards_weight.data,
            practice_weight=add_course_form.practice_of_standards_weight.data,
            grade_goal=float(add_course_form.grade_goal.data)
        )

        db.session.add(new_course)
        db.session.flush()

        initial_grade = Grade(course_id=new_course.id, percentage=final_grade)
        db.session.add(initial_grade)
        new_course.grades.append(initial_grade)
        current_user.courses.append(new_course)
        db.session.commit()

    # ITEM 3: UPDATE COURSE
    if dropdown_update_course_id:
        dropdown_update_course = db.session.get(Course, dropdown_update_course_id)

    if update_course_form.validate_on_submit():
        # Adds new grade to course's grade list
        new_grade = Grade(
            course_id=dropdown_update_course_id,
            percentage=update_course_form.new_grade.data
                          )
        dropdown_update_course.grades.append(new_grade)
        dropdown_update_course.grade = update_course_form.new_grade.data
        
        # If user fills in unrequired grade goal field
        new_grade_goal = update_course_form.grade_goal.data
        if new_grade_goal:
            dropdown_graph_course.grade_goal = new_grade_goal

        db.session.commit()
    
    # ITEM 4: GRAPH COURSE
    if dropdown_graph_course_id:
        dropdown_graph_course = db.session.get(Course, dropdown_graph_course_id)
        data = [(g.date_created, g.percentage) for g in dropdown_graph_course.grades]
        
        datetimes, grades = zip(*data)
        datetimes, grades = list(datetimes), list(grades)
        graph_html = create_grades_vs_time(dropdown_graph_course.name, datetimes, grades)
            

    current_courses = current_user.courses
    return render_template(
                            'courses.html',
                            current_courses=current_courses,
                            add_course_form=add_course_form,
                            delete_course_form=delete_course_form,
                            dropdown_update_course=dropdown_update_course,
                            update_course_form=update_course_form,
                            graph_html=graph_html
                            )

@app.route('/delete-course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id: int):
    course_to_delete = db.session.get(Course, course_id)
    current_user.courses.remove(course_to_delete)
    db.session.commit()

    return redirect(url_for('courses'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(threaded=True)
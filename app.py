from dotenv import load_dotenv
load_dotenv()

from flask import render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from forms import *
from helper import *
from extension import *
from pypdf import PdfReader

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
                login_user(user, remember=True)
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

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    session.permanent = True

    made_graphs = []
    result_links = []
    course_advice = []
    load_advice_form = LoadCourseAdvice()

    # Creating graphs for each course
    for course in current_user.courses:
        data = [(g.date_created, g.percentage) for g in course.grades]
            
        datetimes, grades = zip(*data)
        datetimes, grades = list(datetimes), list(grades)
        graph_html = create_grades_vs_time_with_predictions(
            title=course.name,
            datetimes=datetimes,
            grades=grades,
            school_start_date=current_user.start_of_school_date,
            school_end_time=current_user.end_of_school_date,
            grade_goal=course.grade_goal,
            days_into_future=20,
            )
        made_graphs.append(graph_html)

    # Recommending videos based on difference of course grade and its goal (How far it is from goal)
    if current_user.courses:
        lowest_grade_course = max(current_user.courses, key=lambda x: x.grade_goal - x.grade)
        results = query_youtube(
            query=f"{lowest_grade_course.name} help lessons",
            num_results=4
                                 )
        result_links = ['https://youtube.com/embed/' + r['id'] for r in results]

    # Giving user tips based on goals
    if load_advice_form.is_submitted():
        try:
            course_advice = prompt_gemini_for_course_advice(current_user.courses)
        except:
            course_advice = 'Please try again later.'  # In case RPM is exceeding RPM limit

        session['latest_course_advice'] = course_advice  # To prevent wasting API requests
            

    if course_advice is None:
        course_advice = ['You have no courses.']

    latest_course_advice = session.get('latest_course_advice')
    if latest_course_advice:
        course_advice = session.get('latest_course_advice')

    return render_template(
        'dashboard.html',
        made_graphs=made_graphs,
        recommended_videos=result_links,
        course_tips=course_advice,
        load_advice_form=load_advice_form
        )    
        
@app.route('/courses', methods=['GET', 'POST'])
@login_required
def courses():
    delete_grade_form = DeleteGradeForm()
    delete_course_form = DeleteCourseForm()
    add_course_form = AddCourseForm()
    update_course_form = UpdateCourseForm()
    dropdown_update_course = None
    dropdown_update_course_id = request.form.get('update_course_id')  # Course ID from the Dropdown Box of Change Courses
    dropdown_graph_course_id = request.form.get('graph_course_id')
    
    # Default update form / graph that'll pop up if user didn't select
    if len(current_user.courses) >= 1:
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
        
        initial_grade = Grade(course_id=new_course.id, percentage=final_grade)
        db.session.add(initial_grade)
        new_course.grades.append(initial_grade)
        
        current_user.courses.append(new_course)
        db.session.commit()

        return redirect('courses')

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
        return redirect('courses')
    
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
                            graph_html=graph_html,
                            delete_grade_form=delete_grade_form
                            )

@app.route('/note-scanner', methods=['GET', 'POST'])
@login_required
def note_scanner():
    session.permanent = False
    #if session.get('notes') is None:
    #    session['notes'] = []

    notes_text = None
    add_notes_form = AddNotesForm()
    search_form = BasicSearchForm()
    

    if add_notes_form.validate_on_submit():
        # User pasted text
        if add_notes_form.note_content.data:
            notes_text = add_notes_form.note_content.data
        
        # User uploaded PDF file
        elif add_notes_form.pdf_content.data:
            pdf_file = add_notes_form.pdf_content.data
            pdf_reader = PdfReader(pdf_file)

            extracted_text = ""
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:  # Ensure the page has text content
                    extracted_text += text + "\n"
            
            notes_text = extracted_text

        session.pop('similar_sentences', None)
        session.pop('user_notes_question', None)

        return render_template(
            'note_scanner.html',
            add_notes_form=add_notes_form,
            search_form=search_form,
            notes_text=notes_text
        )
 
    if search_form.validate_on_submit():
        note_from_html = request.form.get('note_from_html')
        similar_sentences = get_similar_sentences(
            text_block=note_from_html,
            user_text=search_form.text_input.data,
            amount_of_sentences=3
            )
        session['similar_sentences'] = similar_sentences
        session['user_notes_question'] = search_form.text_input.data
        notes_text = note_from_html

    return render_template(
        'note_scanner.html',
        add_notes_form=add_notes_form,
        search_form=search_form,
        notes_text=notes_text
        )

@app.route('/delete-course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id: int):
    course_to_delete = db.session.get(Course, course_id)

    db.session.delete(course_to_delete)
    db.session.commit()

    return redirect(url_for('courses'))

@app.route('/delete-grade/<int:grade_id>', methods=['POST'])
@login_required
def delete_grade(grade_id: int):
    grade_to_delete = db.session.get(Grade, grade_id)

    db.session.delete(grade_to_delete)
    db.session.commit()

    return redirect(url_for('courses'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    school_year_form = SchoolYearForm()

    if school_year_form.validate_on_submit():
        current_user.start_of_school_date = school_year_form.start_date.data
        current_user.end_of_school_date = school_year_form.end_date.data
        db.session.commit()

        return redirect('settings')

    # Set default values which allow user to see their current school year dates
    if request.method == 'GET':
        school_year_form.start_date.data = current_user.start_of_school_date
        school_year_form.end_date.data = current_user.end_of_school_date

    return render_template('settings.html', school_year_form=school_year_form)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(threaded=True)
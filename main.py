from flask import render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from sqlalchemy import select
import os
from forms import *
from helper import *
from extension import *


login_manager = LoginManager()


db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()


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
            login_user(user)
            return redirect(url_for('index'))

    return render_template('login.html', page_name='Sign In', form=signin_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
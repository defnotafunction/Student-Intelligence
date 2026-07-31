# Student Intelligence
Student Intelligence is a Flask app that aids students with organizing and improving their school lives.

## Features
- Authentication and Authorization - Secure user sign up and login using `Flask-SQLAlchemy` and `flask-login`.
- Database - Relational database that uses `Flask-SQLAlchemy` to store users, and information about their courses and grades.
- Frontend - Built with HTML, CSS, and Jinja2.
- Backend - Flask + Python handles users, API requests, routes, and logic.
- Grade Tracking - Saves and graphs grades of user's courses, and their goal to reach for their courses. Uses Support Vector Regressor to predict future grades, powered by `scikit-learn`.
- Course Assistance - Uses Gemini API, custom tools, and YouTube recommendations for advice and help with courses.

## Project Structure

```text
Student Intelligence/
├── app.py                  # Main Flask routes, authentication, and page rendering
├── extension.py            # Initializes the Flask app, SQLAlchemy, and app configuration
├── forms.py                # WTForm classes for login, courses, notes, search, and settings
├── helper.py               # Functions for Database management, Plotly graphs, SVR grade predictions, and API usage
├── models.py               # SQLAlchemy models for users, courses, and grades
├── README.md               # Project documentation
├── .gitignore              # Ignored files for version control
├── docs/                   # Project planning and documentation files
├── instance/               # Folder containing local SQLite database
├── static/                 # Static assets for frontend styles
│   ├── css/
│   └── src/
└── templates/              # Jinja2 templates for rendered HTML pages
```

## License
This project is not available for public use or distribution.

## Additional Information
Website will be up soon.
# Student Intelligence
Student Intelligence is a Flask app that aids students with organizing and improving their school lives.

## Core Features
- Course Creation - Users can create, alter, and delete courses.
- Grade Tracking - Saves and graphs grades of user's courses, and their goal to reach for their courses. Uses Support Vector Regresson to predict future grades, powered by `scikit-learn`.
- Course Assistance - Uses Gemini API, custom tools, and YouTube video recommendations for advice and help with courses.


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

## Stack
- Python 3
- pypdf
- python-dotenv
- Routing, Forms, Database: Flask, Flask-SQLAlchemy, Flask-WTF, WTForms
- Authentication: Werkzeug, Flask-Login
- Data Visualization: Plotly
- ML/AI: scikit-learn, spaCy, google-genai
- Frontend: HTML / CSS / Jinja2

## License
This project is not available for public use or distribution.

## Additional Information
Website: https://studentintelligence.onrender.com/
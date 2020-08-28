from flask import Flask, render_template, url_for, make_response, flash, redirect, request #import Flask class
from forms import SignUpForm, LoginForm, ProjectForm
import pyrebase
import os
import time
import json
from datetime import datetime
from firebase_config import firebase_config

# fixes an issue with pyrebase - allows you to get a data with a specific child key
def noquote(s):
    return s
pyrebase.pyrebase.quote = noquote

# Initialises Firebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()

# set app variable to instance of Flask class
app = Flask(__name__, static_url_path="", static_folder="../../static/", template_folder="templates/")

# config key setup
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY

# Functions
user = False
def key_from_email(email):
    return email.replace(".", "")

def get_user_id():
    email_key = key_from_email(auth.get_account_info(auth.current_user["idToken"])["users"][0]["email"])
    all_emails = dict(db.child("id_generator").get().val())
    return all_emails[email_key]

def get_user_data():
    user_id = get_user_id()
    user = dict(db.child("users").order_by_key().equal_to(user_id).get().val())[user_id]
    return user

# Routes
# @app.route is a decorator for routing to diff pages of website
@app.route("/")
@app.route("/home")
def index():
    if auth.current_user:
        print("logged in")
    else:
        print("logged out")
    global user
    global_projects = db.child("global-projects").child("projects").get().each()
    if global_projects:
        global_projects = [project.val() for project in global_projects]
    else:
        global_projects = []
    return render_template('index.html', user=user, global_projects=global_projects)

@app.route("/gmail")
def gmail():
    return render_template("mail.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    # If logged in, it prevents you from going to the register page
    if auth.current_user:
       return redirect(url_for("index"))
    form = SignUpForm()
    if form.validate_on_submit():
        try:
            user = {
                "firstname": form.firstname.data,
                "lastname": form.lastname.data,
                "email": form.email.data,
                "role": form.role.data,
                "location": form.location.data,
                "profile_description": form.profile_description.data,
                "projects": 0,
            }
            key = db.generate_key()
            updates = {}
            updates["users/" + key] = user
            updates["id_generator/" + key_from_email(form.email.data)] = key
            db.update(updates)
            # Only creates user in authentication after creating database entry
            auth.create_user_with_email_and_password(form.email.data, form.password.data)
            # flash("Registered!", "success")
            return redirect(url_for("login"))
        except Exception as error:
            error = json.loads(error.args[1])['error']['message']
            if error == "EMAIL_EXISTS":
                flash("This email has already been registered.", "danger")
            print(error)
    return render_template("signup.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, it redirects you to the homepage
    if not (auth.current_user):
        form = LoginForm()
        if form.validate_on_submit():
            try:
                auth.sign_in_with_email_and_password(form.email.data, form.password.data)
                global user
                user = get_user_data()
                flash("Login successful!", "success")
                next_page = request.args.get("next")
                return redirect(next_page) if next_page else redirect(url_for("user_homepage"))
            except Exception as error:
                auth.current_user = None
                print("Error: ", error)
                flash("Login Unsuccessful. Please check your credentials.", "danger")
    else:
        return redirect(url_for("index"))
    return render_template("login.html", form=form)

@app.route("/user", methods=["GET", "POST"])
def user_homepage():
    if not auth.current_user:
       return redirect(url_for("index"))
    global user
    form = ProjectForm()
    user_id = get_user_id()
    if form.validate_on_submit():
        project = {
            "title": form.project_title.data,
            "description": form.description.data,
            "timestamp": str(datetime.utcnow()),
            "status": form.status.data,
            "theme": form.theme.data
        }
        key = db.generate_key()
        db.child("users").child(user_id).child("projects").update({key: project})
        project_data = {
            "title": form.project_title.data,
            "status": form.status.data,
            "theme": form.theme.data,
            "location": form.location.data,
            "email": form.email.data,
        }
        db.child("global-projects").child("projects").update({key: project_data})
        # new = db.child("users").child(user_id).child("points").get().val() + task["p_earnt"]
        # db.child("users").child(user_id).update({"points": new})
        user = get_user_data()
        # flash('Your task has been added!', 'success')
        return redirect(url_for("user_homepage"))
        #^ have to do to avoid POST message...
    projects = db.child("users").child(user_id).child("projects").get().each()
    if projects:
        projects = [project.val() for project in projects]
    else:
        projects = []
    return render_template("user.html", user=user, form=form, projects=projects)


@app.route("/logout")
def logout():
    if auth.current_user:
        flash("Logout successful!", "success")
        auth.current_user = None
        global user
        user = False
    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run(debug=True)

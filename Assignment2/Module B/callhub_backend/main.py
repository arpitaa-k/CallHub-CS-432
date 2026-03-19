from flask import Flask, render_template, session, redirect
from config import *
from db import mysql

from routes.auth_routes import auth
from routes.member_routes import members
from routes.portfolio_routes import portfolio
from utils.rbac import can_edit_others


from datetime import timedelta

app = Flask(__name__, template_folder="templates", static_folder="static")
app.permanent_session_lifetime = timedelta(seconds=30)  # 30 seconds for demo; set to 900 for 15 min

# DB config
app.config['MYSQL_HOST'] = MYSQL_HOST
app.config['MYSQL_USER'] = MYSQL_USER
app.config['MYSQL_PASSWORD'] = MYSQL_PASSWORD
app.config['MYSQL_DB'] = MYSQL_DB

mysql.init_app(app)
app.secret_key = "supersecret"

# Blueprints
app.register_blueprint(auth)
app.register_blueprint(members)
app.register_blueprint(portfolio)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ------------------------
# FRONTEND ROUTES
# ------------------------

@app.route("/")
def login_page():
    if "member_id" in session:
        return redirect("/home")
    return render_template("Login.html")



@app.route("/home")
def home():
    if "member_id" not in session:
        return redirect("/")
    member_id = session.get("member_id")
    cur = mysql.connection.cursor()
    cur.execute("SELECT full_name, designation FROM Members WHERE member_id=%s", (member_id,))
    member = cur.fetchone()
    name = member[0] if member else "User"
    role = member[1] if member else "Member"
    return render_template("Homepage.html", username=member_id, name=name, role=role)


@app.route("/read")
def read_page():
    if "member_id" not in session:
        return redirect("/")
    return render_template("read.html", username=session.get("member_id"))


@app.route("/create")
def create_page():
    if "member_id" not in session:
        return redirect("/")

    if not can_edit_others(session.get("role")):
        return render_template("error.html")

    return render_template("create.html")


@app.route("/update")
def update_page():
    if "member_id" not in session:
        return redirect("/")

    if not can_edit_others(session.get("role")):
        return render_template("error.html")

    return render_template("update.html")


@app.route("/delete")
def delete_page():
    if "member_id" not in session:
        return redirect("/")

    if not can_edit_others(session.get("role")):
        return render_template("error.html")

    return render_template("delete.html")


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/portfolio")
def portfolio_page():
    if "member_id" not in session:
        return redirect("/")
    return render_template("portfolio.html", member_id=session.get("member_id"))


if __name__ == "__main__":
    app.run(debug=True)
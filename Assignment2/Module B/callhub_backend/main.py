from flask import Flask, render_template, session, redirect
from config import *
from db import mysql

from routes.auth_routes import auth
from routes.member_routes import members
from routes.portfolio_routes import portfolio
from utils.rbac import is_admin

app = Flask(__name__, template_folder="templates", static_folder="static")

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

# ------------------------
# FRONTEND ROUTES
# ------------------------

@app.route("/")
def login_page():
    return render_template("Login.html")


@app.route("/home")
def home():
    if "member_id" not in session:
        return redirect("/")
    return render_template("Homepage.html", username=session.get("member_id"))


@app.route("/read")
def read_page():
    if "member_id" not in session:
        return redirect("/")
    return render_template("read.html", username=session.get("member_id"))


@app.route("/create")
def create_page():
    if "member_id" not in session:
        return redirect("/")

    if not is_admin(session["member_id"]):
        return render_template("error.html")

    return render_template("create.html")


@app.route("/update")
def update_page():
    if "member_id" not in session:
        return redirect("/")

    if not is_admin(session["member_id"]):
        return render_template("error.html")

    return render_template("update.html")


@app.route("/delete")
def delete_page():
    if "member_id" not in session:
        return redirect("/")

    if not is_admin(session["member_id"]):
        return render_template("error.html")

    return render_template("delete.html")


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/error")
def error():
    return render_template("error.html")


if __name__ == "__main__":
    app.run(debug=True)
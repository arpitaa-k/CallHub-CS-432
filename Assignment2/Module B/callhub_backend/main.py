from flask import Flask, request, session
import bcrypt
from config import *
from db import mysql
from routes.member_routes import members
from routes.auth_routes import auth
from routes.portfolio_routes import portfolio

app = Flask(__name__)

app.config['MYSQL_HOST'] = MYSQL_HOST
app.config['MYSQL_USER'] = MYSQL_USER
app.config['MYSQL_PASSWORD'] = MYSQL_PASSWORD
app.config['MYSQL_DB'] = MYSQL_DB

mysql.init_app(app)
app.register_blueprint(portfolio)
app.register_blueprint(members)
app.register_blueprint(auth)
app.secret_key = "supersecret"

@app.route("/")
def home():
    return {"message": "CallHub Backend Running"}

@app.route("/testdb")
def test_db():
    cur = mysql.connection.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    return {"tables": str(tables)}

if __name__ == "__main__":
    app.run(debug=True)
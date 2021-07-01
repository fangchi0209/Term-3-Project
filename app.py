import json
import ssl
import traceback

import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling, Error
from flask import Flask, jsonify, render_template, request, session, redirect


load_dotenv()

connection_pool = pooling.MySQLConnectionPool(
    pool_name = os.getenv("DBpool"),
    pool_size = 5,
    host=os.getenv("DBhost"),
    user=os.getenv("DBuser"),
    password=os.getenv("DBpw"),
    database=os.getenv("DB")
)


app = Flask(__name__, static_folder="static", static_url_path="/")

# Pages
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def searchPage():
    return render_template("search.html")
@app.route("/bookInfo/<id>")
def bookPage(id):
    return render_template("bookInfo.html")


@app.route("/user", methods=["GET", "POST", "PATCH", "DELETE"])
def loginPage():
    mydb = connection_pool.get_connection()
    mycursor = mydb.cursor(buffered=True)

    if request.method == "PATCH":
        data = request.get_json()
        sqlEmail = data.get('email')
        sqlPassword = data['password']
        mycursor.execute(
            "SELECT * FROM member WHERE email = '%s'" % (sqlEmail))
        loginResult = mycursor.fetchone()
        try:
            if loginResult != None:
                if sqlPassword == loginResult[3]:
                    session["memberEmail"] = loginResult[2]
                    session["memberName"] = loginResult[1]
                    mydb.close()
                    return jsonify({
                        "data": {
                            "id": loginResult[0],
                            "name": loginResult[1],
                            "email": loginResult[2]
                        }
                    }), 200
                else:
                    mydb.close()
                    return jsonify({
                        "error": True,
                        "message": "密碼錯誤"
                    }), 400

        except:
            mydb.close()
            return jsonify({
                "error": True,
                "message": "無此帳號"
            }), 500

    elif request.method == "POST":
        data = request.get_json()
        sqlName = data['name']
        sqlEmail = data['email']
        sqlPassword = data['password']
        mycursor.execute(
            "SELECT * FROM member WHERE email = '%s'" % (sqlEmail))
        registerResult = mycursor.fetchone()

        try:
            if registerResult == None:
                if len(sqlName) == 0 or len(sqlEmail) == 0 or len(sqlPassword) == 0:
                    mydb.close()
                    return jsonify({
                        "error": True,
                        "message": "請填妥所有資料"
                    }), 400
                else:
                    mycursor.execute(
                        "INSERT INTO member (name, email, password) VALUES (%s, %s, %s)", (sqlName, sqlEmail, sqlPassword))
                    mydb.commit()
                    mydb.close()
                    return jsonify({
                        "ok": True,
                        "message": "註冊成功, 請重新登入"
                    }), 200

            else:
                mydb.close()
                return jsonify({
                    "error": True,
                    "message": "註冊失敗, Email重複註冊",
                }), 400

        except:
            mydb.close()
            return jsonify({
                "error": True,
                "message": "伺服器內部錯誤"
            }), 500

    elif request.method == "GET":
        if "memberEmail" in session:
            mydb.close()
            return jsonify({
                "data": True,
            })
        else:
            mydb.close()
            return jsonify({
                "data": None,
            })

    elif request.method == "DELETE":
        session.pop("memberEmail", None)
        mydb.close()
        return jsonify({
            "ok": True,
        })


app.run(host="0.0.0.0", port=3300, debug=True)
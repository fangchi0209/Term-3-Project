import json
import ssl
import traceback
from concurrent.futures import ThreadPoolExecutor
import requests
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling, Error
from flask import Flask, jsonify, render_template, request, session, redirect


load_dotenv()

connection_pool = pooling.MySQLConnectionPool(
    pool_name=os.getenv("DBpool"),
    pool_size=10,
    host=os.getenv("DBhost"),
    user=os.getenv("DBuser"),
    password=os.getenv("DBpw"),
    database=os.getenv("DB")
)


app = Flask(__name__, static_folder="static", static_url_path="/")
app.secret_key = os.getenv("secretKey")

# Pages


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/accounts")
def accounts():
    if "memberEmail" in session:
        return redirect("/")
    else:
        return render_template("accounts.html")


@app.route("/search")
def searchPage():
    return render_template("search.html")


@app.route("/bookInfo/<id>")
def bookPage(id):
    return render_template("bookInfo.html")


@app.route("/api/searchEngine", methods=["POST"])
def searchEngine():

    mydb = connection_pool.get_connection()
    mycursor = mydb.cursor(buffered=True)

    data = request.get_json()
    words = data["key"]

    mycursor.execute(f"SELECT DISTINCT title FROM books WHERE splitW LIKE '%{words}%' LIMIT 8")
    results = mycursor.fetchall()

    books = []
    for result in results:
        books.append(result)

    mydb.close()
    return jsonify({
        "ok": books
    })

@app.route("/api/eachPage")
def eachPage():

    keyword = request.args.get("q")
    # print(keyword)

    data = []

    first = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex=0&maxResults=1"
    f = requests.get(first)
    final = json.loads(f.text)
    totalCount = final["totalItems"] - 80

    i = 0
    while i < totalCount:
        links = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex={i}&maxResults=30"
        # links = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex={i}&maxResults=30&key=AIzaSyDbZ4ChEkPy6BsmTMPbLUmS55VWtfnrEJE&country=TW"
        data.append(links)
        i += 30

    def allBooks(url):

        r = requests.get(url)
        r.encoding = "utf-8"
        x = json.loads(r.text)

        return x

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(allBooks, data)

    resultsArr = []
    for n in results:
        resultsArr.append(n)

    # print(resultsArr)
    return jsonify(resultsArr)


@app.route("/api/reviews", methods=["GET", "POST"])
def reviews():

    mydb = connection_pool.get_connection()
    mycursor = mydb.cursor(buffered=True)

    if request.method == "POST":
        data = request.get_json()
        cTitle = data["title"]
        print(cTitle)
        cUser = session["memberName"]
        cTime = data["date"]
        cContent = data["content"]

        mycursor.execute(
            "INSERT INTO  reviews (book, user, time, content) VALUES (%s, %s, %s, %s)", (cTitle, cUser, cTime, cContent))
        mydb.commit()


        return jsonify({
            "user": session["memberName"],
            "date": cTime,
            "content": cContent
        })

    elif request.method == "GET":
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor(buffered=True)

        bookId = request.args.get("t")
        print(bookId)

        mycursor.execute(f"Select * FROM reviews WHERE book LIKE '%{bookId}%'")
        allReviews = mycursor.fetchall()

        reviewArr = []
        for arr in allReviews:
            reviewDic = {
                "name": arr[2],
                "time": arr[3],
                "content": arr[4]
            }

            reviewData = reviewDic.copy()
            reviewArr.append(reviewData)

        mydb.close()
        return jsonify({
            "allReviews": reviewArr
        })


@app.route("/api/user", methods=["GET", "POST", "PATCH", "DELETE"])
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
        # print(loginResult)
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
                        "message": "Wrong Password"
                    }), 400

            else:
                mydb.close()
                return jsonify({
                    "error": True,
                    "message": "Invalid Account"
                })

        except:
            mydb.close()
            return jsonify({
                "error": True,
                "message": "Invalid Server"
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
                        "message": "Please fill in the blanks"
                    }), 400
                else:
                    mycursor.execute(
                        "INSERT INTO member (name, email, password) VALUES (%s, %s, %s)", (sqlName, sqlEmail, sqlPassword))
                    mydb.commit()
                    mydb.close()
                    return jsonify({
                        "ok": True,
                        "message": "Your account has been successfully activated, please re-sign-in"
                    }), 200

            else:
                mydb.close()
                return jsonify({
                    "error": True,
                    "message": "Email is used by another account.",
                }), 400

        except:
            mydb.close()
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            }), 500

    elif request.method == "GET":
        if "memberEmail" in session:
            mydb.close()
            return jsonify({
                "data": session["memberName"],
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

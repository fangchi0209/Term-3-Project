import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import requests
import boto3
import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect
from flask_sqlalchemy import SQLAlchemy
from concurrent.futures import ThreadPoolExecutor


load_dotenv()

s3 = boto3.resource(
    service_name = 's3',
    aws_access_key_id = os.getenv('awsKeyId'),
    aws_secret_access_key = os.getenv('awsKey'),
    )

app = Flask(__name__, static_folder="static", static_url_path="/")
app.secret_key = os.getenv("secretKey")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("awsRDS")
db = SQLAlchemy(app)


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

    try:
        data = request.get_json()
        words = data["key"]
        sEngine = f"SELECT DISTINCT title FROM books WHERE splitW LIKE '%%{words}%%' LIMIT 8;"
        engine_data = db.engine.execute(sEngine)

        books = []
        for titles in engine_data:
            for title in titles:
                books.append(title)

        return jsonify({
            "ok": books
        })
    except:
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })
            
@app.route("/api/eachPage")
def eachPage():
    keyword = request.args.get("q")
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

    return jsonify(resultsArr)

@app.route("/api/reviews", methods=["GET", "POST"])
def reviews():
    
    if request.method == "POST":
        try:
            if "memberName" in session:
                if len(request.files) == 0:
                    cTitle = request.form.get('title')
                    cUser = session['memberName']
                    cTime = request.form.get('date')
                    cStar = request.form.get('stars')
                    cContent = request.form.get('content')
                    pReview = f"INSERT INTO reviews (book, user, time, rates, content) VALUES ('{cTitle}', '{cUser}', '{cTime}', '{cStar}', '{cContent}')"
                    db.engine.execute(pReview)

                    return jsonify({
                        "user": session["memberName"],
                        "date": cTime,
                        "rates":cStar,
                        "content": cContent,
                    })
                else:

                    uploadFile = request.files['selectFile']
                    cImage = request.files['selectFile'].filename
                    cTitle = request.form.get('title')
                    cUser = session['memberName']
                    cTime = request.form.get('date')
                    cStar = request.form.get('stars')
                    cContent = request.form.get('content')

                    s3.Bucket('t3-upload-bucket').put_object(ACL= 'public-read', Key=uploadFile.filename, Body=uploadFile)

                    pReviewI = f"INSERT INTO reviews (book, user, time, rates, content, image) VALUES ('{cTitle}', '{cUser}', '{cTime}', '{cStar}', '{cContent}', '{cImage}')"
                    db.engine.execute(pReviewI)

                    return jsonify({
                        "user": session["memberName"],
                        "date": cTime,
                        "rates":cStar,
                        "content": cContent,
                        "imageName": 'http://dqgc5yp61yvd.cloudfront.net/'+ cImage,
                    })
            else:
                return jsonify({
                    "error": True,
                    "message": "Please sign in"
                })
        except:
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

    elif request.method == "GET":
        try:
            bookId = request.args.get("t")
            gReview = f"SELECT * FROM reviews WHERE book = '{bookId}'"
            gReview_data = db.engine.execute(gReview)

            reviewArr = []
            for reviews in gReview_data:
                if reviews[6] == None:
                    reviewDic = {
                        "name": reviews[2],
                        "time": reviews[3],
                        "rates": reviews[4],
                        "content": reviews[5],
                    }
                    reviewData = reviewDic.copy()
                    reviewArr.append(reviewData)
                else:
                    reviewDic = {
                        "name": reviews[2],
                        "time": reviews[3],
                        "rates": reviews[4],
                        "content": reviews[5],
                        "image": 'http://dqgc5yp61yvd.cloudfront.net/' + reviews[6]
                    }
                    reviewData = reviewDic.copy()
                    reviewArr.append(reviewData)

            return jsonify({
                "allReviews": reviewArr
            })
        except:
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

@app.route("/api/user", methods=["GET", "POST", "PATCH", "DELETE"])
def loginPage():

        if request.method == "PATCH":
            data = request.get_json()
            sqlEmail = data.get('email')
            sqlPassword = data['password']

            login = f"SELECT * FROM member WHERE email = '{sqlEmail}'"
            login_data = db.engine.execute(login)
            loginResult = login_data.fetchone()

            try:
                if loginResult != None:
                    if sqlPassword == loginResult[3]:
                        session["memberEmail"] = loginResult[2]
                        session["memberName"] = loginResult[1]

                        return jsonify({
                            "data": {
                                "id": loginResult[0],
                                "name": loginResult[1],
                                "email": loginResult[2]
                            }
                        }), 200
                    else:
                        return jsonify({
                            "error": True,
                            "message": "Wrong Password"
                        }), 400

                else:
                    return jsonify({
                        "error": True,
                        "message": "Invalid Account"
                    })

            except:
                return jsonify({
                    "error": True,
                    "message": "Invalid Server"
                }), 500

        elif request.method == "POST":
            data = request.get_json()
            sqlName = data['name']
            sqlEmail = data['email']
            sqlPassword = data['password']

            register = f"SELECT * FROM member WHERE email = '{sqlEmail}'"
            register_data = db.engine.execute(register)
            registerResult = register_data.fetchone()

            try:
                if registerResult == None:
                    if len(sqlName) == 0 or len(sqlEmail) == 0 or len(sqlPassword) == 0:
                        
                        return jsonify({
                            "error": True,
                            "message": "Please fill in the blanks"
                        }), 400
                    else:
                        signin = f"INSERT INTO member (name, email, password) VALUES ({sqlName}, {sqlEmail}, {sqlPassword}))"
                        signin_data = db.engine.execute(signin)

                        return jsonify({
                            "ok": True,
                            "message": "Your account has been successfully activated, please re-sign-in"
                        }), 200

                else:
                    return jsonify({
                        "error": True,
                        "message": "Email is used by another account.",
                    }), 400

            except:
                return jsonify({
                    "error": True,
                    "message": "Invalid Server"
                }), 500

        elif request.method == "GET":
            if "memberEmail" in session:
                return jsonify({
                    "data": True,
                    "member": session["memberName"],
                })
            else:
                return jsonify({
                    "data": None,
                })

        elif request.method == "DELETE":
            session.pop("memberEmail", None)
            return jsonify({
                "ok": True,
            })


app.run(host="0.0.0.0", port=3300, debug=True)

import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import bs4
from bs4 import BeautifulSoup
import requests
import boto3
import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect
from flask_sqlalchemy import SQLAlchemy
from concurrent.futures import ThreadPoolExecutor
import email.message
import smtplib


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


@app.route("/events")
def events():
    return render_template("events.html")

@app.route("/e/<eventId>")
def e(eventId):
    return render_template("e.html")
@app.route("/api/searchEngine", methods=["POST"])
def searchEngine():

    try:
        data = request.get_json()
        words = data["key"]
        sEngine = f"SELECT DISTINCT title FROM books WHERE splitW = '{words}' LIMIT 8;"
        engine_data = db.engine.execute(sEngine)

        books = []
        for titles in engine_data:
            for title in titles:
                books.append(title)

        return jsonify({
            "ok": books
        })

    except Exception as e:
        print(e)
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })
            
@app.route("/api/eachPage")
def eachPage():

    try:
        keyword = request.args.get("q")
        data = []

        first = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex=0&maxResults=1"
        f = requests.get(first)
        final = json.loads(f.text)

        if final["totalItems"] < 10:
            totalCount = final["totalItems"]
        else:
            totalCount = final["totalItems"] - 80

        i = 0
        while i < totalCount:
            links = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex={i}&maxResults=30"
            # links = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex={i}&maxResults=30&key=AIzaSyDbZ4ChEkPy6BsmTMPbLUmS55VWtfnrEJE&country=TW"
            data.append(links)
            i += 30
    except Exception as e:
        print(e)
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })

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

@app.route("/api/authors")
def authors():

    bookIdforA = request.args.get("a")
    authorUrl = f"https://books.google.com.tw/books?id={bookIdforA}"

    authorHtml = requests.get(authorUrl)
    authorData = BeautifulSoup(authorHtml.text, 'html.parser')
    aboutAuthor = authorData.find("div", class_="textmodulecontent")

    try:
        if aboutAuthor != None:
            return jsonify({
                "aboutAuthor": aboutAuthor.text
            })
        else:
            return jsonify({
                "aboutAuthor": "no data"
            })
    except Exception as e:
        print(e)
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })

@app.route("/api/recommend")
def recommend():
    bookIdforRec = request.args.get("rec")
    count_data = db.engine.execute(f"SELECT * from counts WHERE bookId = '{bookIdforRec}'")
    count_Result = count_data.fetchone()

    try:
        if count_Result != None:
            countAdd = count_Result[2]+ 1
            db.engine.execute(f"UPDATE counts SET visitSite = '{countAdd}' WHERE (bookId = '{bookIdforRec}')")

            ctsRank = db.engine.execute("SELECT * FROM counts ORDER BY visitSite DESC LIMIT 17")

            def recBookInfo(recURL):
                recBookHTML = requests.get(recURL)
                recBook_data = json.loads(recBookHTML.text)

                return recBook_data

            ctsBookArr = []
            for ctsBook in ctsRank:
                recBook = f"https://www.googleapis.com/books/v1/volumes?q={ctsBook[1]}&maxResults=1"
                ctsBookArr.append(recBook)

            with ThreadPoolExecutor(max_workers=15) as executor:
                recBookResults = executor.map(recBookInfo, ctsBookArr)

            top13Arr = []
            for i in recBookResults:
                top13Arr.append(i)

            return jsonify({
                "recBooks": top13Arr,
            })

        else:
            db.engine.execute(f"INSERT INTO counts (bookId, visitSite) VALUES ('{bookIdforRec}', '1')")

            ctsRank = db.engine.execute("SELECT * FROM counts ORDER BY visitSite DESC LIMIT 13")

            def recBookInfo(recURL):
                recBookHTML = requests.get(recURL)
                recBook_data = json.loads(recBookHTML.text)

                return recBook_data

            ctsBookArr = []
            for ctsBook in ctsRank:
                recBook = f"https://www.googleapis.com/books/v1/volumes?q={ctsBook[1]}&maxResults=1"
                ctsBookArr.append(recBook)

            with ThreadPoolExecutor(max_workers=15) as executor:
                recBookResults = executor.map(recBookInfo, ctsBookArr)

            top13Arr = []
            for i in recBookResults:
                top13Arr.append(i)

            return jsonify({
                "recBooks": top13Arr,
            })

    except Exception as e:
        print(e)
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })

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
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

    elif request.method == "GET":
        try:
            bookId = request.args.get("r")
            gReview = f"SELECT * FROM reviews WHERE book = '{bookId}'"
            gReview_data = db.engine.execute(gReview)

            reviewArr = []
            starsArr = []
            for reviews in gReview_data:
                starsArr.append(reviews[4])
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
            
            avgStar = sum(starsArr) // len(starsArr)

            return jsonify({
                "allReviews": reviewArr,
                "avgStar": avgStar
            })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

@app.route("/api/bookievents", methods=["GET", "POST"])
def bookievents():

    if request.method == "POST":
        try:
            if len(request.files) == 0:
                return jsonify({
                    "error": True,
                    "message": "Please upload event image"
                })
            else:
                nTitle = request.form.get('eTitle')
                nUser = session['memberName']
                nsDateData = request.form.get('sDate')
                nsDate = bsDateData.split(",")
                nsTime = request.form.get('sTime')
                neDateData = request.form.get('eDate')
                neDate = beDateData.split(",")
                neTime = request.form.get('eTime')
                nURL = request.form.get('online')
                eventCover = request.files['selectFile']
                nImage = request.files['selectFile'].filename
                nDes = request.form.get('description')

                s3.Bucket('t3-upload-bucket').put_object(ACL= 'public-read', Key=eventCover.filename, Body=eventCover)

                db.engine.execute(
                    f"INSERT INTO events (organiser, eventName, sDay, sDate, sMonth, sYear, sTime, eDay, eDate, eMonth, eYear, eTime, location, cover, eventDes) VALUES ('{nUser}', '{nTitle}', '{nsDate[0]}', '{nsDate[1]}', '{nsDate[2]}', '{nsDate[3]}', '{nsTime}', '{neDate[0]}', '{neDate[1]}', '{neDate[2]}', '{neDate[3]}', '{neTime}', '{nURL}', '{nImage}', '{nDes}')")

                return jsonify({
                    "nTitle": nTitle,
                    "nUser": nUser,
                    "nsDay": nsDate[0],
                    "nsDate": nsDate[1],
                    "nsMonth": nsDate[2],
                    "nsYear": nsDate[3],
                    "nsTime": nsTime,
                    "neDay": neDate[0],
                    "neDate": neDate[1],
                    "neMonth": neDate[2],
                    "neYear": neDate[3],
                    "neTime": neTime,
                    "nURL": nURL,
                    "nCover": 'http://dqgc5yp61yvd.cloudfront.net/' + nImage,
                    "nDes": nDes
                })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

    if request.method == "GET":
        try:
            allEventsData = db.engine.execute("SELECT * FROM events ORDER BY id DESC")

            eventsArr = []
            for allEvents in allEventsData:
                eventsDict = {
                    "aTitle": allEvents[2],
                    "aUser": allEvents[1],
                    "asDay": allEvents[3],
                    "asDate": allEvents[4],
                    "asMonth": allEvents[5],
                    "asYear": allEvents[6],
                    "asTime": allEvents[7],
                    "aeDay": allEvents[8],
                    "aeDate": allEvents[9],
                    "aeMonth": allEvents[10],
                    "aeYear": allEvents[11],
                    "aeTime": allEvents[12],
                    "aURL": allEvents[13],
                    "aCover": 'http://dqgc5yp61yvd.cloudfront.net/' + allEvents[14],
                    "aDes": allEvents[15],
                }

                eventsData = eventsDict.copy()
                eventsArr.append(eventsData)
            
            return jsonify({
                "allEvents": eventsArr
            })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

@app.route("/api/theevent", methods=["GET", "POST"])
def theevent():

    if request.method == "GET":
        try:
            eventId = request.args.get("e")
            theEventData = db.engine.execute(f"SELECT * FROM events WHERE eventName = '{eventId}'")
            theEvent = theEventData.fetchone()

            return jsonify({
                "theTitle": theEvent[2],
                "theUser": theEvent[1],
                "thesDay": theEvent[3],
                "thesDate": theEvent[4],
                "thesMonth": theEvent[5],
                "thesYear": theEvent[6],
                "thesTime": theEvent[7],
                "theeDay": theEvent[8],
                "theeDate": theEvent[9],
                "theeMonth": theEvent[10],
                "theeYear": theEvent[11],
                "theeTime": theEvent[12],
                "theURL": theEvent[13],
                "theCover": 'http://dqgc5yp61yvd.cloudfront.net/' + theEvent[14],
                "theDes": theEvent[15]
            })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })
    if request.method == "POST":
        try:
            attendeeData = request.get_json()
            attendeeEmail = attendeeData["registerEmail"]

            msg = email.message.EmailMessage()
            msg["From"]= os.getenv('gmail')
            msg["To"]= f"{attendeeEmail}"
            msg["Subject"]="你好, 彭彭"

            msg.add_alternative("<h3>Online Event from BooKÏ</h3>滿五百送一百喔", subtype="html")

            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.login(os.getenv('gmail'), os.getenv('gmailP'))
            server.send_message(msg)
            server.close()

            return jsonify({
                "ok": "ok"
            })

        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

@app.route("/api/google", methods=["POST"])
def google():

    gdata = request.get_json()
    gn = gdata["gName"]
    ge = gdata["gEmail"]

    session["memberName"] = gn
    session["memberEmail"] = ge

    gmail = db.engine.execute(f"SELECT * FROM member WHERE email = '{ge}'")
    result = gmail.fetchone()

    try:
        if result != None:
            return jsonify({
                "gname": gn,
                "gmail": ge
            })
        else:
            demo = db.engine.execute(f"INSERT INTO member (name, email) VALUES ('{gn}', '{ge}')")
            return jsonify({
                "gname": gn,
                "gmail": ge
            })

    except Exception as e:
        print(e)
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

            except Exception as e:
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
                        signin = f"INSERT INTO member (name, email, password) VALUES ({sqlName}, {sqlEmail}, {sqlPassword})"
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

            except Exception as e:
                print(e)
                return jsonify({
                    "error": True,
                    "message": "Invalid Server"
                }), 500

        elif request.method == "GET":
            if "memberEmail" in session:
                return jsonify({
                    "data": True,
                    "member": session["memberName"]
                })
            else:
                return jsonify({
                    "data": None,
                })

        elif request.method == "DELETE":
            session.pop("memberName", None)
            session.pop("memberEmail", None)
            return jsonify({
                "ok": True,
            })


app.run(host="0.0.0.0", port=3300, debug=True)

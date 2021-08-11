import smtplib
import email.message
from concurrent.futures import ThreadPoolExecutor
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, render_template, request, session, redirect
from dotenv import load_dotenv
from flask_bcrypt import bcrypt
import os
import boto3
import requests
from bs4 import BeautifulSoup
import bs4
import json
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

s3 = boto3.resource(
    service_name='s3',
    aws_access_key_id=os.getenv('awsKeyId'),
    aws_secret_access_key=os.getenv('awsKey'),
)

app = Flask(__name__, static_folder="static", static_url_path="/")
app.secret_key = os.getenv("secretKey")
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json;charset=utf-8"
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


@app.route("/mycollection")
def mycollection():
    if "memberEmail" in session:
        return render_template("mycollection.html")
    else:
        return redirect("/events")


@app.route("/api/searchEngine", methods=["POST"])
def searchEngine():

    try:
        data = request.get_json()
        words = data["key"]
        sEngine = f'''SELECT DISTINCT title FROM books WHERE splitW = "{words}" LIMIT 8'''
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

@app.route("/api/eachPage", methods=["GET"])
def eachPage():

    try:
        keyword = request.args.get("q")
        data = []

        first = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&startIndex=0&maxResults=1"
        f = requests.get(first)
        final = json.loads(f.text)

        # if final["totalItems"] < 10:
        #     totalCount = final["totalItems"]
        # else:
        #     totalCount = final["totalItems"] - 150

        i = 0
        while i < 200:
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

@app.route("/api/authors", methods=["GET"])
def authors():
    try:
        bookIdforA = request.args.get("a")
        checkAuthorData = db.engine.execute(f'''SELECT * FROM author WHERE bookID = "{bookIdforA}"''')
        checkAuthor = checkAuthorData.fetchone()

        if checkAuthor != None:
            return jsonify({
                "aboutAuthor": checkAuthor[2]
            })

        else:

            authorUrl = f"https://books.google.com.tw/books?id={bookIdforA}"

            authorHtml = requests.get(authorUrl)
            authorData = BeautifulSoup(authorHtml.text, 'html.parser')
            aboutAuthor = authorData.find("div", class_="textmodulecontent")

            if aboutAuthor != None:
                db.engine.execute(f'''INSERT INTO author (bookID, aboutAuthor) VALUES ("{bookIdforA}", "{aboutAuthor.text}")''')

                return jsonify({
                    "aboutAuthor": aboutAuthor.text
                })
            else:
                return jsonify({
                    "error": True,
                    "message": "No author data"
                })
            
    except Exception as e:
        print(e)
        return jsonify({
            "error": True,
            "message": "Invalid Server"
        })

@app.route("/api/recommend", methods=["POST"])
def recommend():
    recData = request.get_json()
    bookIdforRec = recData["bookIdforRecommend"]
    bookCoverforRec = recData["bookCoverforRecommend"]
    count_data = db.engine.execute(
        f'''SELECT * from counts WHERE bookId = "{bookIdforRec}"''')
    count_Result = count_data.fetchone()

    try:
        if count_Result != None:
            countAdd = count_Result[2] + 1
            db.engine.execute(
                f'''UPDATE counts SET visitSite = "{countAdd}" WHERE (bookId = "{bookIdforRec}")''')

            ctsRank = db.engine.execute(
                "SELECT * FROM counts ORDER BY visitSite DESC LIMIT 17")
            
            top17arr = []
            for recBookData in ctsRank:

                recBookDict = {
                    "recBookId": recBookData[1],
                    "recBookCover": recBookData[3]
                }

                recBook = recBookDict.copy()
                top17arr.append(recBook)

            return jsonify({
                "recBooks": top17arr
            })

        else:
            db.engine.execute(
                f'''INSERT INTO counts (bookId, visitSite, bookCoverImg) VALUES ("{bookIdforRec}", "1", "{bookCoverforRec}")''')

            ctsRank = db.engine.execute(
                "SELECT * FROM counts ORDER BY visitSite DESC LIMIT 17")

            top17arr = []
            for recBookData in ctsRank:

                recBookDict = {
                    "recBookId": recBookData[1],
                    "recBookCover": recBookData[3]
                }

                recBook = recBookDict.copy()
                top17arr.append(recBook)

            return jsonify({
                "recBooks": top17arr,
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
                    cTime = request.form.get('date')
                    cStar = request.form.get('stars')
                    cContent = request.form.get('content')
                    print(cContent)
                    pReview = f'''INSERT INTO reviews (book, user, time, rates, content) VALUES ("{cTitle}", "{session['memberName']}", "{cTime}", "{cStar}", "{cContent}")'''
                    db.engine.execute(pReview)

                    return jsonify({
                        "user": session["memberName"],
                        "date": cTime,
                        "rates": cStar,
                        "content": cContent,
                    })
                else:

                    uploadFile = request.files['selectFile']
                    cImage = request.files['selectFile'].filename
                    cTitle = request.form.get('title')
                    cTime = request.form.get('date')
                    cStar = request.form.get('stars')
                    cContent = request.form.get('content')

                    s3.Bucket('t3-upload-bucket').put_object(ACL='public-read',
                                                             Key=uploadFile.filename, Body=uploadFile)

                    pReviewI = f'''INSERT INTO reviews (book, user, time, rates, content, image) VALUES ("{cTitle}", "{session['memberName']}", "{cTime}", "{cStar}", "{cContent}", "{cImage}")'''
                    db.engine.execute(pReviewI)

                    return jsonify({
                        "user": session["memberName"],
                        "date": cTime,
                        "rates": cStar,
                        "content": cContent,
                        "imageName": 'http://dqgc5yp61yvd.cloudfront.net/' + cImage,
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

        bookId = request.args.get("r")
        gReview = f'''SELECT * FROM reviews WHERE book = "{bookId}"'''
        gReview_data = db.engine.execute(gReview)
 
        try:
            bookId = request.args.get("r")
            gReview = f'''SELECT * FROM reviews WHERE book = "{bookId}"'''
            gReview_data = db.engine.execute(gReview)

            reviewArr = []
            starsArr = []
            for reviews in gReview_data:
                if reviews == " ":
                    print("nothing")
                else:
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
                nsDateData = request.form.get('sDate')
                nsDate = nsDateData.split(",")
                nsTime = request.form.get('sTime')
                nURL = request.form.get('online')
                eventCover = request.files['selectFile']
                nImage = request.files['selectFile'].filename
                nDes = request.form.get('description')
                nTags = request.form.get('hashtagsArr')

                imageRep = nImage.replace(" ", "_")

                s3.Bucket('t3-upload-bucket').put_object(ACL='public-read',
                                                         Key=imageRep, Body=eventCover)

                db.engine.execute(
                    f'''INSERT INTO events (organiser, organiser_email, eventName, sDay, sDate, sMonth, sYear, sTime, location, cover, eventDes, hashtags) VALUES ("{session['memberName']}", "{session['memberEmail']}", "{nTitle}", "{nsDate[0]}", "{nsDate[1]}", "{nsDate[2]}", "{nsDate[3]}", "{nsTime}", "{nURL}", "{imageRep}", "{nDes}", "{nTags}")''')

                selectData = db.engine.execute(f'''SELECT * FROM events WHERE eventName = "{nTitle}"''')
                theselect = selectData.fetchone()

                for i in nTags.split(","):
                    if i != "<br>":
                        
                        checkData = db.engine.execute(f'''SELECT * FROM tags WHERE tagName = "{i}"''')
                        thecheck = checkData.fetchone()

                        if thecheck != None:
                            newNum = thecheck[2] + 1
                            db.engine.execute(f'''UPDATE tags SET num = "{newNum}" WHERE tagName = "{i}"''')
                        else:
                            db.engine.execute(f'''INSERT INTO tags (tagName, num) VALUES ("{i}", "1")''')
                                                
                        idData = db.engine.execute(f'''SELECT * FROM tags WHERE tagName = "{i}"''')
                        theid = idData.fetchone()

                        db.engine.execute(f'''INSERT INTO tagmap (tagID, eventID) VALUES ("{theid[0]}", "{theselect[0]}")''')

                return jsonify({
                    "ok": True,
                })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

    if request.method == "GET":
        try:
            allEventsData = db.engine.execute(
                "SELECT * FROM events ORDER BY id DESC")

            eventsArr = []
            for allEvents in allEventsData:
                totalData = db.engine.execute(
                    f'''SELECT COUNT(memberEmail) FROM activity WHERE eventId = "{allEvents[3]}"''')
                totalP = totalData.fetchone()

                eventsDict = {
                    "aId": allEvents[0],
                    "aTitle": allEvents[3],
                    "aUser": allEvents[1],
                    "aUserE": allEvents[2],
                    "asDay": allEvents[4],
                    "asDate": allEvents[5],
                    "asMonth": allEvents[6],
                    "asYear": allEvents[7],
                    "asTime": allEvents[8],
                    "aURL": allEvents[9],
                    "aCover": 'http://dqgc5yp61yvd.cloudfront.net/' + allEvents[10],
                    "aDes": allEvents[11],
                    "aPeople": totalP[0]
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
            theEventData = db.engine.execute(
                f'''SELECT * FROM events WHERE eventName = "{eventId}"''')
            theEvent = theEventData.fetchone()

            theTagData = db.engine.execute(f'''SELECT * FROM booki.tagmap JOIN booki.tags ON booki.tagmap.tagID = booki.tags.id WHERE booki.tagmap.eventID = "{theEvent[0]}" ''')

            tagsArr = []
            for tags in theTagData:
                tagsDict = {
                    "tagId": tags[3],
                    "tagName": tags[4]
                }
                tagsData = tagsDict.copy()
                tagsArr.append(tagsData)
            

            if "memberEmail" in session:
                if theEvent[2] == session["memberEmail"]:
                    peopleArr = []
                    totalPeopleData = db.engine.execute(
                        f'''SELECT memberEmail, name FROM activity JOIN member ON activity.memberEmail = member.email WHERE eventId = "{theEvent[3]}"''')
                    for people in totalPeopleData:
                        peopleArr.append(people[1])

                    ttP = len(peopleArr)

                    return jsonify({
                        "theTitle": theEvent[3],
                        "theUser": theEvent[1],
                        "theUserE": theEvent[2],
                        "thesDay": theEvent[4],
                        "thesDate": theEvent[5],
                        "thesMonth": theEvent[6],
                        "thesYear": theEvent[7],
                        "thesTime": theEvent[8],
                        "theURL": theEvent[9],
                        "theCover": 'http://dqgc5yp61yvd.cloudfront.net/' + theEvent[10],
                        "theDes": theEvent[11],
                        "theHashtags": tagsArr,
                        "thePeopleAcount": ttP,
                        "thePeople": peopleArr 
                    })
                else:
                    peopleAccountData = db.engine.execute(f'''Select COUNT(memberEmail) FROM activity WHERE eventId = "{theEvent[3]}"''')
                    peopleAccount = peopleAccountData.fetchone()

                    return jsonify({
                        "theTitle": theEvent[3],
                        "theUser": theEvent[1],
                        "theUserE": theEvent[2],
                        "thesDay": theEvent[4],
                        "thesDate": theEvent[5],
                        "thesMonth": theEvent[6],
                        "thesYear": theEvent[7],
                        "thesTime": theEvent[8],
                        "theURL": theEvent[9],
                        "theCover": 'http://dqgc5yp61yvd.cloudfront.net/' + theEvent[10],
                        "theDes": theEvent[11],
                        "theHashtags": tagsArr,
                        "thePeopleAcount": peopleAccount[0]
                    })
            else:
                peopleAccountData = db.engine.execute(f'''Select COUNT(memberEmail) FROM activity WHERE eventId = "{theEvent[3]}"''')
                peopleAccount = peopleAccountData.fetchone()

                return jsonify({
                    "theTitle": theEvent[3],
                    "theUser": theEvent[1],
                    "theUserE": theEvent[2],
                    "thesDay": theEvent[4],
                    "thesDate": theEvent[5],
                    "thesMonth": theEvent[6],
                    "thesYear": theEvent[7],
                    "thesTime": theEvent[8],
                    "theURL": theEvent[9],
                    "theCover": 'http://dqgc5yp61yvd.cloudfront.net/' + theEvent[10],
                    "theDes": theEvent[11],
                    "theHashtags": tagsArr,
                    "thePeopleAcount": peopleAccount[0]
                })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })
    if request.method == "POST":
        if "memberEmail" in session:
            attendeeData = request.get_json()
            attendEvent = attendeeData["reEventId"]
            eventReplace = attendEvent.replace("%20", " ")

            try:
                checkEmail = db.engine.execute(
                    f'''SELECT * FROM activity WHERE memberEmail = "{session['memberEmail']}" and eventId = "{eventReplace}"''')
                checked = checkEmail.fetchone()
            
                if checked == None:
                    db.engine.execute(
                        f'''INSERT INTO activity (eventId, memberEmail) VALUES ("{eventReplace}", "{session['memberEmail']}")''')

                    eventData = db.engine.execute(
                        f'''SELECT * FROM events WHERE eventName = "{eventReplace}"''')
                    eventEmail = eventData.fetchone()

                    msg = email.message.EmailMessage()
                    msg["From"] = os.getenv('gmail')
                    msg["To"] = f"{session['memberEmail']}"
                    msg["Subject"] = f"Online Event from BooKÏ - {eventEmail[3]}"

                    msg.add_alternative(f"""\
                        <html>
                        <head></head>
                        <body>
                            <div>Hello <b>{session["memberName"]}</b>,</div><br>
                            <div>Thank you for registering <b>{eventEmail[3]}</b>, below please kindly find the event information:</div><br>
                            <div>Online Event Title:</div>
                            <a href="http://www.booki.tw/e/{eventEmail[3]}">{eventEmail[3]}</a><br><br>
                            <div>Online Event Date & Time:</div>
                            <div>{eventEmail[5]}, {eventEmail[6]}, {eventEmail[7]}, {eventEmail[8]}</div><br><br>
                            <div>Online Event Link:</div>
                            <div>{eventEmail[9]}</div><br><br>
                            <div>Event Description:</div>
                            <div>{eventEmail[11]}</div><br><br>
                            <a href="http://www.booki.tw/e/{eventEmail[3]}"><div><img src="http://dqgc5yp61yvd.cloudfront.net/{eventEmail[10]}"></div></a>
                        </body>
                        </html>
                        """, subtype="html")

                    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
                    server.login(os.getenv('gmail'), os.getenv('gmailP'))
                    server.send_message(msg)
                    server.close()

                    return jsonify({
                        "ok": True
                    })
                else:
                    return jsonify({
                        "error": True,
                        "message": "Already registered"
                    })

            except Exception as e:
                print(e)
                return jsonify({
                    "error": True,
                    "message": "Invalid Server"
                })
        else:
            return jsonify({
                "error": True,
                "message": "Please sign in"
            })

@app.route("/api/registered", methods=["GET"])
def registered():
    registeredEventId = request.args.get("reg")
    try:
        if "memberEmail" in session:
            registeredEventData = db.engine.execute(f'''SELECT * FROM activity WHERE eventId = "{registeredEventId}" and memberEmail = "{session["memberEmail"]}"''')
            registeredEvent = registeredEventData.fetchone()

            if registeredEvent != None:
                return jsonify({
                    "ok": True
                })
            else:
                return jsonify({
                    "ok": False
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

@app.route("/api/getAllRegistered", methods=["GET"])
def getAllRegistered():
    try:
        if "memberEmail" in session:
            getAllRegisteredData = db.engine.execute(f'''SELECT * FROM booki.events LEFT JOIN booki.activity ON booki.events.eventName = booki.activity.eventId WHERE memberEmail = "{session["memberEmail"]}"''')
            reTitleArr = []
            for getAllRegistered in getAllRegisteredData:
                reTitleArr.append(getAllRegistered[3])

            return jsonify({
                "registeredTitle": reTitleArr
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

@app.route("/api/eventfav", methods=["GET", "POST"])
def collectevent():

    if request.method == "POST":
        try:
            if session["memberEmail"]:
                eventFavData = request.get_json()
                favEventId = eventFavData["eventId"]

                collectCheckData = db.engine.execute(
                    f'''SELECT * FROM eventFav WHERE event_num = "{favEventId}" AND collector = "{session['memberEmail']}"''')
                collectCheck = collectCheckData.fetchone()

                if collectCheck != None:
                    db.engine.execute(
                        f'''DELETE FROM eventFav WHERE event_num = "{favEventId}" AND collector = "{session['memberEmail']}"''')
                    return jsonify({
                        "ok": True
                    })
                else:
                    db.engine.execute(
                        f'''INSERT INTO eventFav (event_num, collector) VALUES ("{favEventId}", "{session['memberEmail']}")''')

                    return jsonify({
                        "ok": False
                    })
            else:
                return jsonify({
                    "error": True,
                    "message": "Sign in with your BooKÏ Account to collect an event"
                })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })
    if request.method == "GET":
        try:
            if session["memberEmail"]:
                getCollectFullInfoData = db.engine.execute(
                    f'''SELECT * FROM events JOIN eventFav ON events.id = eventFav.event_num WHERE collector = "{session["memberEmail"]}"''')

                collection = []
                for getCollect in getCollectFullInfoData:
                    totalPeoData = db.engine.execute(
                        f'''SELECT COUNT(memberEmail) FROM activity WHERE eventId = "{getCollect[3]}"''')
                    totalPeople = totalPeoData.fetchone()
                    favDict = {
                        "getCollect": getCollect[0],
                        "favOrganiser": getCollect[1],
                        "favOrganiserE": getCollect[2],
                        "favTitle": getCollect[3],
                        "favDay": getCollect[4],
                        "favDate": getCollect[5],
                        "favMonth": getCollect[6],
                        "favYear": getCollect[7],
                        "favTime": getCollect[8],
                        "favCover": 'http://dqgc5yp61yvd.cloudfront.net/' + getCollect[10],
                        "totalPeople": totalPeople[0]
                    }
                    favData = favDict.copy()
                    collection.append(favData)

                return jsonify({
                    "favCollection": collection
                })
            else:
                return jsonify({
                    "ok": True,
                    "message": "please sign in"
                })

        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })

@app.route("/api/mycollection", methods=["GET"])
def mycollectionAPI():

    if session["memberEmail"]:
        try:
            myOwnEventData = db.engine.execute(f'''SELECT * FROM events WHERE organiser_email = "{session["memberEmail"]}"''')
            
            myOwnEventArr = []
            for myOwnEvent in myOwnEventData:
                totalPeopleData = db.engine.execute(
                    f'''SELECT COUNT(memberEmail) FROM activity WHERE eventId = "{myOwnEvent[3]}"''')
                People = totalPeopleData.fetchone()

                ownDict = {
                    "getCollect": myOwnEvent[0],
                    "ownOrganiser": myOwnEvent[1],
                    "ownOrganiserE": myOwnEvent[2],
                    "ownTitle": myOwnEvent[3],
                    "ownDay": myOwnEvent[4],
                    "ownDate": myOwnEvent[5],
                    "ownMonth": myOwnEvent[6],
                    "ownYear": myOwnEvent[7],
                    "ownTime": myOwnEvent[8],
                    "ownCover": 'http://dqgc5yp61yvd.cloudfront.net/' + myOwnEvent[10],
                    "totalPeople": People[0]
                }
                ownData = ownDict.copy()
                myOwnEventArr.append(ownData)

            if len(myOwnEventArr) > 0:
                return jsonify({
                    "myOwnEvent": myOwnEventArr
                })
            else:
                return jsonify({
                    "error": True
                })
        except Exception as e:
            print(e)
            return jsonify({
                "error": True,
                "message": "Invalid Server"
            })
    else:
        return jsonify({
            "error": True,
            "message": "Please sign in"
        })

@app.route("/api/hashtag", methods=["GET"])
def hashtag():
    getTagId = request.args.get("tagID")
    
    getHashtagDataAll = db.engine.execute(f'''SELECT * FROM booki.events JOIN booki.tagmap ON booki.events.id = booki.tagmap.eventID WHERE booki.tagmap.tagID = "{getTagId}"''')

    hashArr = []
    for h in getHashtagDataAll:
        hashPeoData = db.engine.execute(
        f'''SELECT COUNT(memberEmail) FROM activity WHERE eventId = "{h[3]}"''')
        hashPeople = hashPeoData.fetchone()

        getHashtagDict = {
            "getHashE": h[0],
            "hOrganiser": h[1],
            "hOrganiserE": h[2],
            "hTitle": h[3],
            "hDay": h[4],
            "hDate": h[5],
            "hMonth": h[6],
            "hYear": h[7],
            "hTime": h[8],
            "hCover": 'http://dqgc5yp61yvd.cloudfront.net/' + h[10],
            "hPeople": hashPeople[0]
        }
        getHashtagData = getHashtagDict.copy()
        hashArr.append(getHashtagData)


    return jsonify({
        "hashEvent": hashArr
    })

@app.route("/api/google", methods=["POST"])
def google():

    gdata = request.get_json()
    gn = gdata["gName"]
    ge = gdata["gEmail"]

    session["memberName"] = gn
    session["memberEmail"] = ge

    gmail = db.engine.execute(f'''SELECT * FROM member WHERE email = "{ge}"''')
    result = gmail.fetchone()

    try:
        if result != None:
            return jsonify({
                "gname": gn,
                "gmail": ge
            })
        else:
            demo = db.engine.execute(
                f'''INSERT INTO member (name, email) VALUES ("{gn}", "{ge}")''')
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

        login = f'''SELECT * FROM member WHERE email = "{sqlEmail}"'''
        login_data = db.engine.execute(login)
        loginResult = login_data.fetchone()

        try:
            if loginResult != None:
                if bcrypt.checkpw(sqlPassword.encode('utf-8'), loginResult[3].encode('utf-8')):
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

        register = f'''SELECT * FROM member WHERE email = "{sqlEmail}"'''
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

                    hashed = bcrypt.hashpw(sqlPassword.encode('utf-8'), bcrypt.gensalt())
                    signin = f'''INSERT INTO member (name, email, password) VALUES ("{sqlName}", "{sqlEmail}", "{hashed.decode('utf-8')}")'''
                    signin_data = db.engine.execute(signin)


                    return jsonify({
                        "ok": True,
                        "message": "Your account has been successfully activated, please re-sign-in",
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

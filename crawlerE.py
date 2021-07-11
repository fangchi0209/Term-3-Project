import nltk
import requests
import bs4
from bs4 import BeautifulSoup
import nltk.corpus 
from nltk.text import Text
import requests
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import urllib.request as req
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import json
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="/")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("awsRDS")

db = SQLAlchemy(app)

@app.route("/")
def index():

    n = 0
    while n <= 3: 
        url = f"https://www.goodreads.com/list/show/1.Best_Books_Ever?page={n}"
        n += 1

        # with req.urlopen(url) as response:
        #     html =response.read().decode("utf-8") #根據觀察, 取得的資料是JSON格式

        request = requests.get(url)
        request.encoding = 'utf8'

        raw = BeautifulSoup(request.text, 'html.parser')
        # print(raw)

        # titles = raw.find("table", class_="tableList js-dataTooltip")
        # print(titles)

        titles=raw.select("a.bookTitle span")
        for i in titles:
            bookTitle = i.get_text()
            tokens = nltk.word_tokenize(bookTitle)
            print(tokens)
            for token in tokens:
                tokenW = f'INSERT INTO books (title, splitW) VALUES ("{bookTitle}", "{token}")'
                db.engine.execute(tokenW)

        # for title in titles:
        #     bookTitle = title.get_text()
        #     tokens = nltk.word_tokenize(bookTitle)
        # print(tokens)
            # for token in tokens:
            #     tokenW = f'INSERT INTO books (title, splitW) VALUES ("{bookTitle}", "{token}")'
            #     db.engine.execute(tokenW)
    return 'ok'

if __name__ == "__main__":
    app.run()


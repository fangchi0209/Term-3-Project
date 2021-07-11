import jieba
import jieba.analyse
import urllib.request as req
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import json
import requests
import bs4
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__, static_folder="static", static_url_path="/")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("awsRDS")

db = SQLAlchemy(app)

@app.route("/")
def index():

    url = "https://www.books.com.tw/web/annual100_cat/2101?loc=P_0004_002"

    request = requests.get(url)
    request.encoding = 'utf8'

    raw = BeautifulSoup(request.text, 'html.parser')

    titlesC = raw.select("div.table-td h4 a")
    for title in titlesC:
        titleC = title.get_text()
        titleC = titleC.replace("%", "%%")
        titleC = titleC.replace(" ", "")
        jiebaTs = jieba.cut(titleC)
        for jiebaT in jiebaTs:
            # print(jiebaT)
            jiebaT = jiebaT.replace("%", "%%")
            db.engine.execute(f"""INSERT INTO books (title, splitW) VALUES ('{titleC}', '{jiebaT}')""")
    
    return 'ok'

if __name__ == "__main__":
    app.run()


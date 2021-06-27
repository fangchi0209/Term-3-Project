import json
import ssl
import traceback

import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect


app = Flask(__name__, static_folder="static", static_url_path="/")

# Pages
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/bookInfo")
def bookInfo():
    return render_template("bookInfo.html")

@app.route("/bookInfo/<id>")
def bookPage(id):
    return render_template("bookInfo.html")

# @app.route("/api/bookInfo/<bookId")

app.run(host="0.0.0.0", port=3300, debug=True)
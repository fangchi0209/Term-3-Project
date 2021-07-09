import nltk
import requests
import bs4
from bs4 import BeautifulSoup
import nltk.corpus 
from nltk.text import Text
import requests
from flask import Flask, jsonify, render_template, request, session, redirect
import urllib.request as req
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import json
import mysql.connector
from concurrent.futures import ThreadPoolExecutor

mydb = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="mydog8229",
    database="booki"
)

mycursor = mydb.cursor(buffered=True)

n = 0
while n <= 1000: 
    url = f"https://www.gutenberg.org/ebooks/search/?sort_order=downloads&start_index={n}"
    n += 25

    with req.urlopen(url) as response:
        html =response.read().decode("utf-8") #根據觀察, 取得的資料是JSON格式

    raw = BeautifulSoup(html, 'html.parser')

    titles=raw.select("li.booklink a span.title")

    for title in titles:
        bookTitle = title.get_text()
        tokens = nltk.word_tokenize(bookTitle)
        for token in tokens:
            mycursor.execute("INSERT INTO books (title, splitW) VALUES (%s, %s)", (bookTitle, token))
            mydb.commit()


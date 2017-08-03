import sched
import threading
import time
import urllib2
import json
import unirest
import redis
import datetime
from flask import Flask, request, render_template, Markup, send_from_directory, session
from newspaper import Article
import random

API_KEY = 'ccfdc66609fc4b7b87258020b85d4380'
BASE_URL = 'https://newsapi.org/v1/'
sources = ""
json_sources = ""
articles = []

app = Flask(__name__)
app.debug = True
app.secret_key = '\x1dv\x86\xcedW\xd6\xea\xfe\x92\xd5\xbb\x80\xadYn\x14>\xa8\x06\xd8(\x19\xf6'

r = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
s = sched.scheduler(time.time, time.sleep)

rsources = r.get('sources')
rtimestamp = None


def get_sources():
    sources = urllib2.urlopen(BASE_URL + "/sources?language=en").read()
    r.set('sources', sources)
    # change later to avoid DB call
    rsources = r.get('sources')


def add_to_articles(response):
    if response.code is 200:
        rsources = r.get('sources')
        rsources = json.loads(rsources)['sources']
        for source in rsources:
            if source['id'] == response.body['source']:
                category = source['category']
                r.set('articles:' + category + ":" +
                      response.body['source'], json.dumps(response.body))
    else:
        print(response.code)


def set_timestamp():
    now = datetime.datetime.now()
    r.set('sources_timestamp', now.month)


def check_timestamp():
    rtimestamp = r.get('sources_timestamp')
    if rtimestamp:
        rtimestamp = int(rtimestamp)
    now = datetime.datetime.now()
    if not rtimestamp is None:
        if not rtimestamp == now.month:
            # Get new sources
            rtimestamp = now.month
            set_timestamp()
            print(rtimestamp)
            get_sources()
            print("Got new sources")
    else:
        print("Timestamp empty")
        set_timestamp()
        check_timestamp()
    if rsources is None:
        get_sources()
    print("Timestamp OK")


def getNewArticles():
    print("Getting new articles")
    rsources = r.get('sources')
    if rsources:
        rsources = json.loads(rsources)['sources']
        rtimestamp = None
    if rsources and len(rsources) > 0:
        check_timestamp()
        for source in rsources:
            response = unirest.get(BASE_URL + "/articles?apikey=" + API_KEY,
                                   headers={"Accept": "application/json"}, params={"source": source['id']},
                                   callback=add_to_articles)
    else:
        check_timestamp()
        print("Got new sources")
    # try:
    #     threading.Timer(1200, getNewArticles).start()
    # except (KeyboardInterrupt, SystemExit):
    #     sys.exit()


@app.route('/styles/<path:path>')
def send_styles(path):
    return send_from_directory('styles', path)


@app.route('/')
def index():
    articles = []
    for key in r.keys(pattern="articles:*"):
        data = r.get(key)
        data = json.loads(data)
        for article in data['articles']:
            articles.append(article)
    articles = sorted(articles, key=lambda x: x['publishedAt'])
    articles.reverse()
    session['index'] = 9
    return render_template("index.html", articles=articles[0:9], category="none")


@app.route('/get10')
def get10(previousIndex=0):
    articles = []
    for key in r.keys(pattern="articles:*"):
        data = r.get(key)
        data = json.loads(data)
        for article in data['articles']:
            articles.append(article)
    articles = sorted(articles, key=lambda x: x['publishedAt'])
    articles.reverse()

    previousIndex = int(request.args.get('previousIndex'))
    previousIndex = previousIndex + 1
    session['index'] = previousIndex + 9

    i = session.get('index')
    print(i);
    p = previousIndex
    return json.dumps({"articles": json.dumps(articles[p:i])})


@app.route('/article')
def getArticle(url=None, category=None):
    url = request.args.get('url')
    url_string = url.replace(':', '')

    try:
        ip = request.environ['REMOTE_ADDR']
        if request.headers.get('X-Forwarded-For'):
            ip = request.headers.get('X-Forwarded-For', ip)
        print(str.format("IP: {0}, Article: {1}", ip, url))
        print("ROUTE: " + request.access_route[-1])
    except:
        print("ERROR GETTING IP ADDRESS OR KEY")

    category = request.args.get('category')

    isHTML = False

    title = ""
    html = ""
    img = ""
    movies = []
    try:
        for key in r.keys(pattern="html:" + category + ":" + url_string):
            data = r.get(key)
            data = json.loads(data)
            isHTML = True
    except:
        print("Error fetching keys for article: " + url)

    if category:
        if isHTML:
            title = data['title']
            html = data['html']
            img = data['img']
            movies = data['movies']
            print("LOADED FROM DB")
        else:
            article = Article(url, keep_article_html=True)
            article.download()
            article.parse()
            title = article.title
            html = article.article_html
            img = article.top_image
            movies = article.movies
            print("CATEGROY: ", category)
            print("Title: ", article.title)
            r.set('html:' + category + ":" + url_string,
                  json.dumps({"title": title, "html": html, "img": img, "movies": movies}))

    return render_template("article.html",
                           url=url,
                           title=title,
                           body=Markup(html),
                           header_image=img,
                           video=movies)


@app.route('/category')
def getCategory(category=""):
    category = request.args.get('cat')
    print(len(r.keys(pattern="articles:" + category + ":*")))
    articles = []
    for key in r.keys(pattern="articles:" + category + ":*"):
        print(key)
        data = r.get(key)
        data = json.loads(data)
        for article in data['articles']:
            date = article['publishedAt']
            print(date)
            articles.append(article)
        articles.sort(key=lambda x: x['publishedAt'])
        articles.reverse()
    return render_template("category.html", articles=articles, category=category)


def main():
    getNewArticles()
    app.run(host='localhost', port=5000)


if __name__ == "__main__":
    main()

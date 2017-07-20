import json
import urllib2
from flask import Flask, request, render_template, Markup, send_from_directory
from newspaper import Article
import unirest
import redis
import datetime

API_KEY = 'ccfdc66609fc4b7b87258020b85d4380'
BASE_URL = 'https://newsapi.org/v1/'
sources = ""
json_sources = ""
articles = []

app = Flask(__name__)
app.debug = True

r = redis.StrictRedis(host='localhost', port=6379, db=0)

rsources = r.get('sources')
rtimestamp = None

def get_sources():
    sources = urllib2.urlopen(BASE_URL + "/sources").read()
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
                r.set('articles:' + category + ":" + response.body['source'], json.dumps(response.body))
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

def main():
    rsources = r.get('sources')
    rsources = json.loads(rsources)['sources']
    rtimestamp = None
    if rsources and len(rsources) > 0:
        check_timestamp()
        for source in rsources:
            response = unirest.get(BASE_URL + "/articles?apikey=" + API_KEY,
                                headers={ "Accept": "application/json" }, params={ "source": source['id']},
                                callback = add_to_articles)
    else:
        check_timestamp()
        print("Got new sources")
    app.run(host= '0.0.0.0')

    

# @app.route('/scripts/<path:path>')
# def send_scripts(path):
#     return send_from_directory('scripts', path)

@app.route('/styles/<path:path>')
def send_styles(path):
    return send_from_directory('styles', path)

@app.route('/')
def index():
    return render_template("index.html", articles = articles)

@app.route('/article')
def getArticle(url = None):
    url = request.args.get('url')
    article = Article(url, keep_article_html=True)
    article.download()
    article.parse()
    print(article.title)
    return render_template("article.html", 
                            url=url, 
                            title=article.title, 
                            body= Markup(article.article_html), 
                            header_image = article.top_image,
                            video = article.movies)

@app.route('/category')
def getCategory(category = ""):
    category = request.args.get('cat')
    print(len(r.keys(pattern="articles:" + category + ":*")))
    articles = []
    for key in r.keys(pattern="articles:" + category + ":*"):
        print(key)
        data = r.get(key)
        data = json.loads(data)
        for article in data['articles']:
            articles.append(article)
    return render_template("category.html", articles = articles)

if __name__ == "__main__":
    main()

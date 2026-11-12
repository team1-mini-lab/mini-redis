from flask import Flask

app = Flask(__name__)


@app.get("/")
def index():
    return {"message": "mini-redis is running"}


if __name__ == "__main__":
    app.run(port=8000, debug=True)

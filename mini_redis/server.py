"""서버 모듈: HTTP 요청을 받아 저장소 함수를 호출하고 JSON으로 응답한다 (접점 2)."""
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def health():
    """0단계: 서버가 떠 있는지 확인하는 응답 하나."""
    return jsonify({"message": "mini-redis is running"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)

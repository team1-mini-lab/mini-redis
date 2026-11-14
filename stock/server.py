"""주식 화면 서버. 화면 파일을 내주고, 화면의 요청을 데모 API로 전달한다.

    브라우저 → 주식 화면 서버(8010) → 데모 API(8001) → mini-redis(8000) / DB

화면이 데모 API를 직접 부르지 않는 이유는, 브라우저가 다른 포트로 보내는 요청을
막기 때문이다 (CORS). 같은 포트의 /api/... 로 받아서 대신 전달한다.
"""
import argparse
import os

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json.ensure_ascii = False

HOST = os.environ.get("STOCK_HOST", "127.0.0.1")
PORT = int(os.environ.get("STOCK_PORT", "8010"))
DEMO_API_URL = os.environ.get("STOCK_DEMO_API_URL", "http://127.0.0.1:8001")
FORWARDED_METHODS = ["GET", "POST", "PUT", "DELETE"]
# 가짜 DB 조회가 3초 걸리므로 그보다 넉넉하게 기다린다.
DEMO_API_TIMEOUT_SECONDS = 15


@app.get("/")
def stock_page():
    return app.send_static_file("index.html")


@app.route("/api/<path:demo_api_path>", methods=FORWARDED_METHODS)
def forward_to_demo_api(demo_api_path):
    try:
        demo_response = send_same_request_to_demo_api(demo_api_path)
    except requests.RequestException:
        return demo_api_is_down()
    return Response(
        demo_response.content,
        status=demo_response.status_code,
        content_type=demo_response.headers.get("Content-Type", "application/json"),
    )


def send_same_request_to_demo_api(demo_api_path):
    return requests.request(
        request.method,
        f"{DEMO_API_URL}/{demo_api_path}",
        params=request.args,
        json=request.get_json(silent=True),
        timeout=DEMO_API_TIMEOUT_SECONDS,
    )


def demo_api_is_down():
    return jsonify({"error": f"데모 API({DEMO_API_URL})에 연결할 수 없습니다"}), 502


def main():
    global HOST, PORT, DEMO_API_URL
    args = parse_arguments()
    HOST = args.host
    PORT = args.port
    DEMO_API_URL = args.demo_api
    print(f"주식 화면 http://{HOST}:{PORT} (데모 API {DEMO_API_URL})")
    app.run(host=HOST, port=PORT, threaded=True)


def parse_arguments():
    parser = argparse.ArgumentParser(description="mini-redis 주식 화면 서버")
    parser.add_argument("--host", default=HOST, help="받을 주소 (기본 127.0.0.1, 배포할 때는 0.0.0.0)")
    parser.add_argument("--port", type=int, default=PORT, help="포트 (기본 8010)")
    parser.add_argument("--demo-api", default=DEMO_API_URL, help="데모 API 주소 (기본 http://127.0.0.1:8001)")
    return parser.parse_args()


if __name__ == "__main__":
    main()

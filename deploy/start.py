"""배포용 실행 스크립트. 서버 3개를 한 서비스 안에서 함께 켠다.

    바깥 → 주식 화면 서버(0.0.0.0:$PORT) → 데모 API(127.0.0.1:8001) → mini-redis(127.0.0.1:8000)

호스팅 서비스는 포트 하나만 바깥에 열어 준다. 그래서 화면 서버만 바깥 요청을 받고,
나머지 둘은 서비스 안에서만 닿는 주소에 둔다.
"""
import os
import subprocess
import sys
import time

import requests

MINI_REDIS_URL = "http://127.0.0.1:8000"
DEMO_API_URL = "http://127.0.0.1:8001"
PUBLIC_HOST = "0.0.0.0"
PUBLIC_PORT = os.environ.get("PORT", "8010")
STARTUP_TIMEOUT_SECONDS = 30
CHECK_INTERVAL_SECONDS = 0.5


def main():
    servers = []
    try:
        servers.append(start_server("mini_redis.server"))
        wait_until_up(MINI_REDIS_URL)
        servers.append(start_server("demo.app"))
        wait_until_up(DEMO_API_URL)
        servers.append(start_server(
            "stock.server", "--host", PUBLIC_HOST, "--port", PUBLIC_PORT, "--demo-api", DEMO_API_URL,
        ))
        wait_until_one_stops(servers)
    finally:
        stop_all(servers)
    # 서버 하나라도 꺼지면 전체를 실패로 끝내서, 호스팅 서비스가 통째로 다시 켜게 한다.
    sys.exit(1)


def start_server(module, *arguments):
    return subprocess.Popen([sys.executable, "-m", module, *arguments])


def wait_until_up(url):
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_up(url):
            return
        time.sleep(CHECK_INTERVAL_SECONDS)
    raise RuntimeError(f"{url} 서버가 {STARTUP_TIMEOUT_SECONDS}초 안에 켜지지 않았습니다")


def is_up(url):
    try:
        return requests.get(url, timeout=1).ok
    except requests.RequestException:
        return False


def wait_until_one_stops(servers):
    while all(server.poll() is None for server in servers):
        time.sleep(CHECK_INTERVAL_SECONDS)


def stop_all(servers):
    for server in servers:
        if server.poll() is None:
            server.terminate()


if __name__ == "__main__":
    main()

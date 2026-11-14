"""시연: 앱 서버가 두 대일 때 로컬 캐시와 mini-redis가 어떻게 다른가.

같은 데모 API를 두 대씩 띄우고, 캐시만 바꿔 끼운 뒤 똑같은 순서로 요청을 보낸다.
    1부  로컬 캐시   서버 A(8101), 서버 B(8102)   캐시가 각 서버 안 dict에
    2부  mini-redis  서버 A(8201), 서버 B(8202)   캐시가 서버 밖 mini-redis(8000)에
두 부 모두 원본(DB)은 하나를 함께 쓴다.

    python -m demo.scenario              처음부터 끝까지 자동으로
    python -m demo.scenario --step       Enter를 누를 때마다 한 단계씩
    python -m demo.scenario --delay 1    DB 지연을 1초로 (기본 3초)

서버는 이 스크립트가 띄우고 끝나면 끈다. mini-redis가 이미 8000에서 돌고 있으면 그것을 쓴다.
원본은 임시 파일에 두어 다른 데모의 데이터를 건드리지 않는다.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
import unicodedata

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "http://127.0.0.1"
MINI_REDIS_URL = f"{HOST}:8000"

KEYBOARD_ID = 1
OLD_PRICE = 50000
NEW_PRICE = 40000
USER = "guest"

# 단계마다 멈춰 설명하는 동안 캐시가 만료되면 장면이 재현되지 않는다.
CACHE_TTL_DURING_SCENARIO = "600"
STARTUP_WAIT_SECONDS = 10
RULE = "━" * 64

LOCAL_PART = {"mode": "local", "title": "1부  로컬 캐시 (캐시가 각 서버 안에)", "ports": (8101, 8102)}
REDIS_PART = {"mode": "redis", "title": "2부  mini-redis (캐시가 서버 밖 한 곳에)", "ports": (8201, 8202)}


def main():
    args = parse_arguments()
    servers = Servers(db_delay=args.delay)
    print_how_to_read(args.delay)
    try:
        servers.start_mini_redis()
        local_result = ScenarioPart(LOCAL_PART, servers, args.step).run()
        redis_result = ScenarioPart(REDIS_PART, servers, args.step).run()
        print_summary(local_result, redis_result)
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except RuntimeError as error:
        print(f"\n[오류] {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        servers.stop_all()


def parse_arguments():
    parser = argparse.ArgumentParser(description="서버 두 대로 로컬 캐시와 mini-redis 비교")
    parser.add_argument("--step", action="store_true", help="Enter를 누를 때마다 한 단계씩")
    parser.add_argument("--delay", type=float, default=3.0, help="가짜 DB 지연(초), 기본 3")
    return parser.parse_args()


def print_how_to_read(db_delay):
    print(f"원본(DB) 지연 {db_delay:g}초. 서버를 띄우는 중...")
    print("한 줄 읽는 법:  서버 A(8101)가 응답 · DB에서 3008.1ms · SW-AI 50,000원")
    print("               어느 서버가 / 어디서 가져와 / 얼마나 걸려 / 무슨 가격을 보여 줬나")


class ScenarioPart:
    """캐시 종류 하나로 서버 두 대를 띄워 일곱 단계를 차례로 보여 준다."""

    def __init__(self, part, servers, wait_for_enter):
        self.title = part["title"]
        self.mode = part["mode"]
        self.port_a, self.port_b = part["ports"]
        self.servers = servers
        self.wait_for_enter = wait_for_enter
        self.price_has_changed = False
        self.result = {}

    @property
    def uses_local_cache(self):
        return self.mode == "local"

    @property
    def cache_of_server_a(self):
        return "서버 A 자기 메모리의 캐시" if self.uses_local_cache else "mini-redis"

    def run(self):
        self.print_title()
        self.start_both_servers()
        self.reset_db_and_cache()

        self.server_a_reads_with_empty_cache()
        self.server_b_reads_the_same_data()
        self.admin_discounts_keyboard_through_server_a()
        self.customer_refreshes_on_both_servers()
        self.server_a_restarts_and_reads()
        token = self.customer_logs_in_on_server_a()
        self.server_b_checks_the_session(token)

        self.report_total_db_queries()
        self.stop_both_servers()
        return self.result

    def print_title(self):
        print(f"\n{RULE}\n  {self.title}\n{RULE}")

    def start_both_servers(self):
        self.servers.start_demo_api(self.port_a, self.mode)
        self.servers.start_demo_api(self.port_b, self.mode)

    def stop_both_servers(self):
        self.servers.stop_demo_api(self.port_a)
        self.servers.stop_demo_api(self.port_b)

    def reset_db_and_cache(self):
        request_price_change(self.port_a, OLD_PRICE)
        requests.delete(f"{HOST}:{self.port_a}/cache", timeout=5)
        requests.post(f"{HOST}:{self.port_a}/stats/reset", timeout=5)

    def server_a_reads_with_empty_cache(self):
        self.begin_step("① 서버 A로 인기 상품 조회 (캐시가 비어 있음)")
        self.show_popular_products(self.port_a, "A")
        note(f"→ 캐시가 비어 있어 DB에서 50,000원을 가져오고, {self.cache_of_server_a}에 저장")

    def server_b_reads_the_same_data(self):
        self.begin_step("② 이번엔 같은 요청이 서버 B로 감 (로드밸런서가 번갈아 보냄)")
        source, _ = self.show_popular_products(self.port_b, "B")
        self.result["b_first"] = source
        self.result["fill_queries"] = db_query_count(self.port_a)
        if self.uses_local_cache:
            note("→ B의 캐시는 A와 따로라 비어 있음 → B도 DB에 가서 B 자기 캐시에 저장")
            note("  같은 내용이 서버마다 한 벌씩 (장면 ④ 값이 같아도 낭비다)")
        else:
            note("→ B도 같은 mini-redis를 봄 → A가 저장한 걸 그대로 꺼냄. DB는 한 번만")

    def admin_discounts_keyboard_through_server_a(self):
        self.begin_step(f"③ 관리자가 SW-AI를 {NEW_PRICE:,}원으로 할인. 요청은 서버 A로 감")
        cache_invalidated = request_price_change(self.port_a, NEW_PRICE)["cache_invalidated"]
        print(f"    서버 A({self.port_a})  가격 수정 → SW-AI {NEW_PRICE:,}원"
              f"   (캐시 삭제: {cache_invalidated})")
        self.price_has_changed = True
        note(f"→ DB에 {NEW_PRICE:,}원으로 저장하고, {self.cache_of_server_a}에서 인기 상품을 지움")
        note("  캐시에 새 값을 넣지는 않음. 새 값은 다음 조회 때 DB에서 가져와 채움")
        if self.uses_local_cache:
            note("  서버 B의 캐시는 A가 지울 수 없음 → B엔 50,000원이 그대로")
        else:
            note("  mini-redis가 하나뿐이라 이제 어디에도 50,000원이 없음")

    def customer_refreshes_on_both_servers(self):
        self.begin_step("④ 고객이 새로고침 — A로 한 번, B로 한 번")
        self.show_popular_products(self.port_a, "A")
        _, price_on_b = self.show_popular_products(self.port_b, "B")
        self.result["b_price"] = price_on_b
        if self.uses_local_cache:
            note("→ A: 캐시가 지워졌으니 DB에서 40,000원을 가져와 A 캐시에 저장")
            note("  B: 자기 캐시에 남은 50,000원을 그대로 보여 줌 (장면 ① 새로고침할 때마다 가격이 바뀐다)")
        else:
            note("→ A: mini-redis가 비어 있어 DB에서 40,000원을 가져와 mini-redis에 새로 저장")
            note("  B: A가 방금 저장한 40,000원을 mini-redis에서 바로 꺼냄")

    def server_a_restarts_and_reads(self):
        self.begin_step("⑤ 배포: 서버 A를 재시작하고 조회")
        self.servers.stop_demo_api(self.port_a)
        self.servers.start_demo_api(self.port_a, self.mode)
        source, _ = self.show_popular_products(self.port_a, "A")
        self.result["after_restart"] = source
        if self.uses_local_cache:
            note("→ 서버 A 프로그램이 꺼지면서 A 메모리의 캐시도 사라짐 → 다시 DB로")
            note("  (장면 ③ 배포할 때마다 DB가 휘청인다)")
        else:
            note("→ 서버 A 프로그램만 껐다 켬. mini-redis는 다른 프로그램이라 40,000원이 그대로")
            note("  → 재시작 직후에도 DB에 가지 않고 바로 응답")

    def customer_logs_in_on_server_a(self):
        self.begin_step("⑥ 고객이 서버 A로 로그인")
        login = requests.post(f"{HOST}:{self.port_a}/login", json={"user": USER}, timeout=10).json()
        print(f"    서버 A({self.port_a})가 응답 · 로그인 성공 · 사용자 {login['user']}"
              f" (토큰 {login['token']})")
        if self.uses_local_cache:
            note("→ 로그인 정보(세션)를 서버 A 자기 메모리에 저장")
        else:
            note("→ 로그인 정보(세션)를 mini-redis에 저장 (키 session:토큰, 30분 유지)")
        return login["token"]

    def server_b_checks_the_session(self, token):
        self.begin_step("⑦ 같은 고객의 다음 요청은 서버 B로 감 — B는 이 고객을 알아볼까?")
        self.result["session_b"] = self.show_whether_server_b_knows(token)
        if self.uses_local_cache:
            note("→ B의 메모리엔 이 세션이 없음 → 로그인이 풀림")
            note("  (장면 ② 로그인했는데 다음 클릭에서 풀린다)")
        else:
            note("→ B도 같은 mini-redis에서 세션을 찾음 → 로그인 유지")

    def report_total_db_queries(self):
        self.result["total_queries"] = db_query_count(self.port_a)
        print(f"\n  이번 부에서 DB 조회: 총 {self.result['total_queries']}번"
              "   (세션은 DB를 쓰지 않음)")

    def begin_step(self, headline):
        print(f"\n  {headline}")
        if self.wait_for_enter:
            input("    (Enter를 누르면 진행) ")

    def show_popular_products(self, port, server_label):
        """(가져온 곳, SW-AI 가격)을 돌려준다."""
        data = requests.get(f"{HOST}:{port}/products/popular", timeout=30).json()
        price = keyboard_price(data["products"])
        came_from = "캐시에서" if data["source"] == "cache" else "DB에서  "
        stale_mark = "   ← 옛 가격!" if self.price_has_changed and price == OLD_PRICE else ""
        print(f"    서버 {server_label}({port})가 응답 · {came_from} {data['elapsed_ms']:>7.1f}ms"
              f" · SW-AI {price:,}원{stale_mark}")
        return data["source"], price

    def show_whether_server_b_knows(self, token):
        response = requests.get(f"{HOST}:{self.port_b}/me", params={"token": token}, timeout=10)
        session_is_known = response.status_code == 200
        if session_is_known:
            print(f"    서버 B({self.port_b})가 응답 · 알아봄   ·"
                  f" {response.json()['user']}님 환영합니다")
        else:
            print(f"    서버 B({self.port_b})가 응답 · 모름     ·"
                  f" 401 로그인이 필요합니다   ← 로그인이 풀림!")
        return session_is_known


def note(text):
    print(f"    {text}")


def keyboard_price(products):
    return next(product["price"] for product in products if product["id"] == KEYBOARD_ID)


def request_price_change(port, price):
    return requests.put(
        f"{HOST}:{port}/products/{KEYBOARD_ID}/price", json={"price": price}, timeout=10
    ).json()


def db_query_count(port):
    return requests.get(f"{HOST}:{port}/stats", timeout=5).json()["db_query_count"]


class Servers:
    """mini-redis와 데모 API 프로세스를 띄우고 끈다."""

    def __init__(self, db_delay):
        self.demo_api_processes = {}
        self.mini_redis_process = None
        self.environment = dict(
            os.environ,
            DEMO_DB_PATH=os.path.join(tempfile.mkdtemp(prefix="mini-redis-demo-"), "demo.sqlite3"),
            DEMO_DB_DELAY=str(db_delay),
            DEMO_CACHE_TTL=CACHE_TTL_DURING_SCENARIO,
            PYTHONWARNINGS="ignore",
        )

    def start_mini_redis(self):
        if is_responding(MINI_REDIS_URL):
            print("mini-redis(8000)가 이미 떠 있어서 그대로 씁니다.")
            return
        self.mini_redis_process = self.run_module("mini_redis.server")
        wait_until_responding(MINI_REDIS_URL, "mini-redis")

    def start_demo_api(self, port, cache_mode):
        url = f"{HOST}:{port}/"
        if is_responding(url):
            raise RuntimeError(f"{port}번 포트를 이미 다른 프로그램이 쓰고 있습니다")
        self.demo_api_processes[port] = self.run_module(
            "demo.app", "--port", str(port), "--cache", cache_mode
        )
        wait_until_responding(url, f"데모 API {port}")

    def stop_demo_api(self, port):
        terminate(self.demo_api_processes.pop(port, None))

    def stop_all(self):
        for port in list(self.demo_api_processes):
            self.stop_demo_api(port)
        terminate(self.mini_redis_process)

    def run_module(self, module, *arguments):
        return subprocess.Popen(
            [sys.executable, "-m", module, *arguments],
            cwd=PROJECT_ROOT, env=self.environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def is_responding(url):
    try:
        return requests.get(url, timeout=0.5).status_code == 200
    except requests.RequestException:
        return False


def wait_until_responding(url, server_description):
    deadline = time.monotonic() + STARTUP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if is_responding(url):
            return
        time.sleep(0.1)
    raise RuntimeError(f"{server_description}가 켜지지 않았습니다 ({url})")


def terminate(process):
    if process:
        process.terminate()
        process.wait(timeout=5)


def print_summary(local, redis):
    rows = [
        ("② 처음 채울 때 DB 조회 (장면 ④)", times(local["fill_queries"]), times(redis["fill_queries"])),
        ("④ 할인 후 서버 B가 본 가격 (장면 ①)", won(local["b_price"]), won(redis["b_price"])),
        ("⑤ 재시작 후 첫 조회 (장면 ③)", source_name(local["after_restart"]), source_name(redis["after_restart"])),
        ("⑦ 서버 B가 로그인을 알아보나 (장면 ②)", session_status(local["session_b"]), session_status(redis["session_b"])),
        ("전체 DB 조회", times(local["total_queries"]), times(redis["total_queries"])),
    ]
    print(f"\n{RULE}\n  정리: 같은 코드, 같은 순서, 캐시 위치만 다름\n{RULE}")
    print_summary_row("", "로컬 캐시", "mini-redis")
    for label, local_value, redis_value in rows:
        print_summary_row(label, local_value, redis_value)
    print()
    print("  로컬 캐시는 상태가 각 서버 안에 묶여 있어서 서버끼리 어긋나고, 서버와 함께 사라진다.")
    print("  mini-redis는 상태를 서버 밖 한 곳으로 빼서, 서버가 몇 대든 같은 값을 본다.")
    print()


def print_summary_row(label, local_value, redis_value):
    print(f"  {pad_right(label, 44)}{pad_left(local_value, 12)}{pad_left(redis_value, 14)}")


def times(count):
    return f"{count}번"


def won(price):
    return f"{price:,}원"


def source_name(source):
    return "캐시" if source == "cache" else "DB"


def session_status(session_is_known):
    return "알아봄" if session_is_known else "모름(401)"


def pad_right(text, width):
    return text + " " * max(0, width - terminal_width(text))


def pad_left(text, width):
    return " " * max(0, width - terminal_width(text)) + text


def terminal_width(text):
    """한글처럼 폭이 넓은 글자는 터미널에서 두 칸을 차지한다."""
    return sum(2 if unicodedata.east_asian_width(character) in "WF" else 1 for character in text)


if __name__ == "__main__":
    main()

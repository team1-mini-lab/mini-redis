"""시연: 서버가 여러 대가 되면 로컬 캐시와 mini-redis가 어떻게 다른가.

3차 체크인 코치 피드백("서버가 여러 대가 되면?")과 발표한 다섯 장면 중
①(가격이 왔다 갔다), ②(로그인이 풀림), ③(재시작하면 캐시가 사라짐),
④(같은 데이터를 서버마다 따로 조회)를 실제 서버 두 대로 재현한다.

같은 데모 API 코드를 두 대씩 띄우고, 캐시만 바꿔 끼운 뒤 똑같은 순서로 요청을 보낸다.
    1부  로컬 캐시   서버 A(8101), 서버 B(8102)   캐시가 각 서버 안 dict에
    2부  mini-redis  서버 A(8201), 서버 B(8202)   캐시가 서버 밖 mini-redis(8000)에
두 부 모두 원본(DB)은 하나를 함께 쓴다.

실행
    python -m demo.scenario              처음부터 끝까지 자동으로
    python -m demo.scenario --step       Enter를 누를 때마다 한 단계씩 (발표용)
    python -m demo.scenario --delay 1    DB 지연을 1초로 (기본 3초)

서버는 이 스크립트가 직접 띄우고 끝나면 끈다. mini-redis가 이미 8000에서 돌고 있으면
그것을 쓰고, 없으면 직접 띄운다. 원본은 임시 파일을 써서 다른 데모에 영향을 주지 않는다.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
import unicodedata

import requests

REDIS_URL = "http://127.0.0.1:8000"
KEYBOARD = 1
OLD_PRICE = 50000
NEW_PRICE = 40000
USER = "eungi"

PARTS = [
    {"mode": "local", "title": "1부  로컬 캐시 (캐시가 각 서버 안에)", "ports": (8101, 8102)},
    {"mode": "redis", "title": "2부  mini-redis (캐시가 서버 밖 한 곳에)", "ports": (8201, 8202)},
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Demo:
    def __init__(self, delay, step):
        self.step = step
        self.procs = {}                       # port → Popen
        self.redis_proc = None
        self.db_path = os.path.join(tempfile.mkdtemp(prefix="mini-redis-demo-"), "demo.sqlite3")
        self.env = dict(os.environ, DEMO_DB_PATH=self.db_path, DEMO_DB_DELAY=str(delay),
                        PYTHONWARNINGS="ignore",
                        # 단계마다 멈춰 설명하는 사이 TTL(기본 60초)이 지나면 캐시가 사라져
                        # 장면이 재현되지 않는다. 시연에서는 10분으로 늘린다.
                        DEMO_CACHE_TTL="600")

    # ── 서버 띄우고 끄기 ───────────────────────────────────

    @staticmethod
    def _alive(url):
        try:
            return requests.get(url, timeout=0.5).status_code == 200
        except requests.RequestException:
            return False

    def _wait(self, url, what):
        for _ in range(100):                  # 최대 10초
            if self._alive(url):
                return
            time.sleep(0.1)
        raise RuntimeError(f"{what}가 켜지지 않았습니다 ({url})")

    def start_redis(self):
        if self._alive(REDIS_URL):
            print("mini-redis(8000)가 이미 떠 있어서 그대로 씁니다.")
            return
        self.redis_proc = subprocess.Popen(
            [sys.executable, "-m", "mini_redis.server"], cwd=ROOT, env=self.env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._wait(REDIS_URL, "mini-redis")

    def start(self, port, mode):
        url = f"http://127.0.0.1:{port}/"
        if self._alive(url):
            raise RuntimeError(f"{port}번 포트를 이미 다른 프로그램이 쓰고 있습니다")
        self.procs[port] = subprocess.Popen(
            [sys.executable, "-m", "demo.app", "--port", str(port), "--cache", mode],
            cwd=ROOT, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._wait(url, f"데모 API {port}")

    def stop(self, port):
        proc = self.procs.pop(port, None)
        if proc:
            proc.terminate()
            proc.wait(timeout=5)

    def stop_all(self):
        for port in list(self.procs):
            self.stop(port)
        if self.redis_proc:
            self.redis_proc.terminate()
            self.redis_proc.wait(timeout=5)

    # ── 요청 보내기 ────────────────────────────────────────

    def popular(self, port, label):
        """인기 상품을 조회하고 한 줄로 보여 준다. (source, 키보드 가격)을 돌려준다."""
        data = requests.get(f"http://127.0.0.1:{port}/products/popular", timeout=30).json()
        keyboard = next(p for p in data["products"] if p["id"] == KEYBOARD)
        price = keyboard["price"]
        mark = "   ← 옛 가격!" if price == OLD_PRICE and self.price_changed else ""
        where = "캐시에서" if data["source"] == "cache" else "DB에서  "
        print(f"    서버 {label}({port})가 응답 · {where} {data['elapsed_ms']:>7.1f}ms"
              f" · 키보드 {price:,}원{mark}")
        return data["source"], price

    def set_price(self, port, label, price):
        data = requests.put(f"http://127.0.0.1:{port}/products/{KEYBOARD}/price",
                            json={"price": price}, timeout=10).json()
        print(f"    서버 {label}({port})  가격 수정 → 키보드 {price:,}원"
              f"   (캐시 삭제: {data['cache_invalidated']})")

    def login(self, port, label):
        """로그인하고 토큰을 받는다. 세션은 그 서버가 쓰는 캐시에 저장된다."""
        data = requests.post(f"http://127.0.0.1:{port}/login",
                             json={"user": USER}, timeout=10).json()
        print(f"    서버 {label}({port})가 응답 · 로그인 성공 · 사용자 {data['user']}"
              f" (토큰 {data['token']})")
        return data["token"]

    def me(self, port, label, token):
        """이 서버가 그 세션을 알아보는지 본다. 알아보면 True, 401이면 False."""
        response = requests.get(f"http://127.0.0.1:{port}/me",
                                params={"token": token}, timeout=10)
        if response.status_code == 200:
            print(f"    서버 {label}({port})가 응답 · 알아봄   ·"
                  f" {response.json()['user']}님 환영합니다")
            return True
        print(f"    서버 {label}({port})가 응답 · 모름     ·"
              f" 401 로그인이 필요합니다   ← 로그인이 풀림!")
        return False

    def db_count(self, port):
        return requests.get(f"http://127.0.0.1:{port}/stats", timeout=5).json()["db_query_count"]

    # ── 화면 ───────────────────────────────────────────────

    def say(self, text):
        print(f"\n  {text}")

    def note(self, text):
        print(f"    {text}")

    def pause(self):
        if self.step:
            input("    (Enter를 누르면 진행) ")

    # ── 한 부 ─────────────────────────────────────────────

    def run_part(self, part):
        mode, (a, b) = part["mode"], part["ports"]
        self.price_changed = False
        print("\n" + "━" * 64)
        print(f"  {part['title']}")
        print("━" * 64)

        self.start(a, mode)
        self.start(b, mode)
        # 원본과 캐시를 처음 상태로
        self.set_quiet(a, OLD_PRICE)
        requests.delete(f"http://127.0.0.1:{a}/cache", timeout=5)
        requests.post(f"http://127.0.0.1:{a}/stats/reset", timeout=5)
        result = {}

        local = mode == "local"
        here = "서버 A 자기 메모리의 캐시" if local else "mini-redis"

        self.say("① 서버 A로 인기 상품 조회 (캐시가 비어 있음)")
        self.pause()
        self.popular(a, "A")
        self.note(f"→ 캐시가 비어 있어 DB에서 50,000원을 가져오고, {here}에 저장")

        self.say("② 이번엔 같은 요청이 서버 B로 감 (로드밸런서가 번갈아 보냄)")
        self.pause()
        source, _ = self.popular(b, "B")
        result["b_first"] = source
        result["fill_queries"] = self.db_count(a)
        if local:
            self.note("→ B의 캐시는 A와 따로라 비어 있음 → B도 DB에 가서 B 자기 캐시에 저장")
            self.note("  같은 내용이 서버마다 한 벌씩 (장면 ④ 값이 같아도 낭비다)")
        else:
            self.note("→ B도 같은 mini-redis를 봄 → A가 저장한 걸 그대로 꺼냄. DB는 한 번만")

        self.say(f"③ 관리자가 키보드를 {NEW_PRICE:,}원으로 할인. 요청은 서버 A로 감")
        self.pause()
        self.set_price(a, "A", NEW_PRICE)
        self.price_changed = True
        self.note(f"→ DB에 {NEW_PRICE:,}원으로 저장하고, {here}에서 인기 상품을 지움")
        self.note("  캐시에 새 값을 넣지는 않음. 새 값은 다음 조회 때 DB에서 가져와 채움")
        if local:
            self.note("  서버 B의 캐시는 A가 지울 수 없음 → B엔 50,000원이 그대로")
        else:
            self.note("  mini-redis가 하나뿐이라 이제 어디에도 50,000원이 없음")

        self.say("④ 고객이 새로고침 — A로 한 번, B로 한 번")
        self.pause()
        self.popular(a, "A")
        _, b_price = self.popular(b, "B")
        result["b_price"] = b_price
        if local:
            self.note("→ A: 캐시가 지워졌으니 DB에서 40,000원을 가져와 A 캐시에 저장")
            self.note("  B: 자기 캐시에 남은 50,000원을 그대로 보여 줌 (장면 ① 새로고침할 때마다 가격이 바뀐다)")
        else:
            self.note("→ A: mini-redis가 비어 있어 DB에서 40,000원을 가져와 mini-redis에 새로 저장")
            self.note("  B: A가 방금 저장한 40,000원을 mini-redis에서 바로 꺼냄")

        self.say("⑤ 배포: 서버 A를 재시작하고 조회")
        self.pause()
        self.stop(a)
        self.start(a, mode)
        source, _ = self.popular(a, "A")
        result["after_restart"] = source
        if local:
            self.note("→ 서버 A 프로그램이 꺼지면서 A 메모리의 캐시도 사라짐 → 다시 DB로")
            self.note("  (장면 ③ 배포할 때마다 DB가 휘청인다)")
        else:
            self.note("→ 서버 A 프로그램만 껐다 켬. mini-redis는 다른 프로그램이라 40,000원이 그대로")
            self.note("  → 재시작 직후에도 DB에 가지 않고 바로 응답")

        self.say("⑥ 고객이 서버 A로 로그인")
        self.pause()
        token = self.login(a, "A")
        if local:
            self.note("→ 로그인 정보(세션)를 서버 A 자기 메모리에 저장")
        else:
            self.note("→ 로그인 정보(세션)를 mini-redis에 저장 (키 session:토큰, 30분 유지)")

        self.say("⑦ 같은 고객의 다음 요청은 서버 B로 감 — B는 이 고객을 알아볼까?")
        self.pause()
        result["session_b"] = self.me(b, "B", token)
        if local:
            self.note("→ B의 메모리엔 이 세션이 없음 → 로그인이 풀림")
            self.note("  (장면 ② 로그인했는데 다음 클릭에서 풀린다)")
        else:
            self.note("→ B도 같은 mini-redis에서 세션을 찾음 → 로그인 유지")

        result["total_queries"] = self.db_count(a)
        self.say(f"이번 부에서 DB 조회: 총 {result['total_queries']}번"
                 "   (세션은 DB를 쓰지 않음)")
        self.stop(a)
        self.stop(b)
        return result

    def set_quiet(self, port, price):
        requests.put(f"http://127.0.0.1:{port}/products/{KEYBOARD}/price",
                     json={"price": price}, timeout=10)


def _width(text):
    """터미널에서 차지하는 칸 수. 한글은 두 칸이다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _ljust(text, width):
    return text + " " * max(0, width - _width(text))


def _rjust(text, width):
    return " " * max(0, width - _width(text)) + text


def print_summary(local, redis):
    def src(s):
        return "캐시" if s == "cache" else "DB"

    def known(flag):
        return "알아봄" if flag else "모름(401)"

    rows = [
        ("② 처음 채울 때 DB 조회 (장면 ④)", f"{local['fill_queries']}번", f"{redis['fill_queries']}번"),
        ("④ 할인 후 서버 B가 본 가격 (장면 ①)", f"{local['b_price']:,}원", f"{redis['b_price']:,}원"),
        ("⑤ 재시작 후 첫 조회 (장면 ③)", src(local["after_restart"]), src(redis["after_restart"])),
        ("⑦ 서버 B가 로그인을 알아보나 (장면 ②)", known(local["session_b"]), known(redis["session_b"])),
        ("전체 DB 조회", f"{local['total_queries']}번", f"{redis['total_queries']}번"),
    ]
    print("\n" + "━" * 64)
    print("  정리: 같은 코드, 같은 순서, 캐시 위치만 다름")
    print("━" * 64)
    print(f"  {_ljust('', 44)}{_rjust('로컬 캐시', 12)}{_rjust('mini-redis', 14)}")
    for label, a, b in rows:
        print(f"  {_ljust(label, 44)}{_rjust(a, 12)}{_rjust(b, 14)}")
    print()
    print("  로컬 캐시는 상태가 각 서버 안에 묶여 있어서 서버끼리 어긋나고, 서버와 함께 사라진다.")
    print("  mini-redis는 상태를 서버 밖 한 곳으로 빼서, 서버가 몇 대든 같은 값을 본다.")
    print()


def main():
    parser = argparse.ArgumentParser(description="서버 두 대로 로컬 캐시와 mini-redis 비교")
    parser.add_argument("--step", action="store_true", help="Enter를 누를 때마다 한 단계씩")
    parser.add_argument("--delay", type=float, default=3.0, help="가짜 DB 지연(초), 기본 3")
    args = parser.parse_args()

    demo = Demo(args.delay, args.step)
    print(f"원본(DB) 지연 {args.delay:g}초. 서버를 띄우는 중...")
    print("한 줄 읽는 법:  서버 A(8101)가 응답 · DB에서 3008.1ms · 키보드 50,000원")
    print("               어느 서버가 / 어디서 가져와 / 얼마나 걸려 / 무슨 가격을 보여 줬나")
    try:
        demo.start_redis()
        local = demo.run_part(PARTS[0])
        redis = demo.run_part(PARTS[1])
        print_summary(local, redis)
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except RuntimeError as error:
        print(f"\n[오류] {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        demo.stop_all()


if __name__ == "__main__":
    main()

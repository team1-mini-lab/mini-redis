"""미니 DBMS API 서버: POST /query 로 SQL을 받아 엔진(engine.py)에서 실행하고 JSON으로 답한다.

이 파일에는 과제에 꼭 필요한 것만 있습니다.
- Phase 3(15단계) Thread Pool: 요청을 큐에 줄 세우고, 미리 만든 스레드 N개가 꺼내서 처리. 큐가 꽉 차면 503
- Phase 3(17단계) 오류 응답: 모든 오류를 {"error": {"code", "message"}} 한 모양의 JSON으로
- GET / 또는 GET /docs: 외부 라이브러리 없이 표준 라이브러리만으로 API 테스트 HTML 화면 제공

느린 연결, 이상한 Content-Length 같은 엣지 케이스 방어는 server_guard.py에 따로 있습니다.
`python3 server.py`로 켜면 그 방어까지 켜진 서버가 뜹니다 (맨 아래 참고).
"""
import argparse
import json
import queue
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

from engine import Engine


def error_body(code, message, **extra):
    """Phase 3(17단계): 모든 오류를 {"error": {"code", "message"}} 한 모양으로 만든다."""
    return {"error": {"code": code, "message": message}, **extra}


# Phase 3(17단계): http.server가 스스로 내는 오류를 우리 오류 목록(D38)의 번호와 code로 바꿔 줌
#   501(모르는 방식) → 405, 414·431(주소·머리가 너무 김) → 413, 505와 그 밖 → 400
HTTP_ERRORS = {
    400: (400, "bad_request", "요청 형식이 잘못됐습니다"),
    408: (408, "timeout", "요청을 제한 시간 안에 다 받지 못했습니다"),
    414: (413, "too_large", "주소가 너무 깁니다"),
    431: (413, "too_large", "요청 머리가 너무 큽니다"),
    501: (405, "method_not_allowed", "POST만 받습니다"),
    505: (400, "bad_request", "HTTP/1.0 또는 HTTP/1.1만 받습니다"),
}

BUSY_BODY = json.dumps(
    error_body("busy", "서버가 바쁩니다. 잠시 후 다시 보내 주세요"), ensure_ascii=False
).encode("utf-8")
BUSY_RESPONSE = (                             # 503은 받는 스레드가 Handler 없이 바로 보내므로 미리 만들어 둠
    b"HTTP/1.0 503 Service Unavailable\r\n"
    b"Content-Type: application/json; charset=utf-8\r\n"
    + f"Content-Length: {len(BUSY_BODY)}\r\n".encode()
    + b"Connection: close\r\n\r\n"
    + BUSY_BODY
)

API_PAGE_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>mini-dbms API 테스트</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 28px 16px; }
    .wrap { max-width: 920px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px; }
    h1 { font-size: 20px; margin: 0 0 6px; }
    p { font-size: 13px; color: #475569; margin: 0 0 14px; line-height: 1.5; }
    .box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
    .guard-box { background: #fff1f2; border: 1px solid #fecdd3; border-radius: 10px; padding: 12px; margin-bottom: 14px; }
    .label { font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px; }
    .guard-box .label { color: #881337; }
    .btns { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
    button { border: 1px solid #cbd5e1; background: #fff; color: #0f172a; border-radius: 8px; padding: 6px 11px; font-size: 12px; font-weight: 600; cursor: pointer; }
    button:hover { background: #f1f5f9; }
    button.err-btn { border-color: #fecdd3; color: #9f1239; }
    button.err-btn:hover { background: #ffe4e6; }
    button.primary { background: #0284c7; border-color: #0284c7; color: #fff; }
    button.primary:hover { background: #0369a1; }
    textarea { width: 100%; box-sizing: border-box; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 10px; resize: vertical; }
    pre { background: #0f172a; color: #86efac; border: 1px solid #1e293b; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; padding: 14px; border-radius: 10px; overflow-x: auto; margin: 8px 0 0; line-height: 1.5; }
    pre.is-error { background: #450a0a; color: #fecaca; border: 1px solid #ef4444; }
    .meta { font-family: ui-monospace, monospace; font-size: 12px; color: #0369a1; font-weight: 700; margin-top: 12px; }
    .meta.is-error { color: #dc2626; }
    table { width: 100%; border-collapse: collapse; font-family: ui-monospace, monospace; font-size: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
    th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #f1f5f9; }
    th { background: #f1f5f9; color: #475569; font-weight: 700; }
    .note { font-size: 11px; color: #64748b; margin-top: 6px; line-height: 1.45; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>mini-dbms API 테스트 페이지 (POST /query)</h1>
    <p>외부 라이브러리 없이 파이썬 표준 라이브러리(<code>http.server</code>)로 직접 띄운 화면입니다. 오류가 나면 응답 박스가 빨갛게 변합니다.</p>

    <div class="box">
      <div class="label">현재 서버가 읽은 data/schema.json</div>
      <pre id="schema" style="background:#fff;color:#0f172a;border:1px solid #e2e8f0;margin:0;"></pre>
    </div>

    <div class="label">SQL 프리셋 8종 (POST /query)</div>
    <div class="btns">
      <button onclick="runPreset(`INSERT INTO users (age, name) VALUES (25, '현지');`)">1. INSERT (열 순서 바꿈) · 200</button>
      <button onclick="runPreset(`SELECT * FROM users;`)">2. 쌓인 데이터 전체 보기 · 200</button>
      <button onclick="runPreset(`SELECT * FROM users WHERE id = 2;`)">3. SELECT WHERE id = 2 · 200</button>
      <button onclick="runPreset(`SELECT * FROM users WHERE name = '민수';`)">4. SELECT WHERE name = '민수' · 200</button>
      <button class="err-btn" onclick="runPreset(`INSERT INTO users (name, age) VALUES ('민수', 30); SELECTT * FROM users;`)">5. 여러 문장 중 2번째 오타 · 400</button>
      <button class="err-btn" onclick="runPreset(`INSERT INTO users (id, name, age) VALUES (99, '오류', 20);`)">6. id 직접 입력 금지 · 400</button>
      <button class="err-btn" onclick="runPreset(`INSERT INTO users (name, nick) VALUES ('길동', '별명');`)">7. 빠진 열 / 없는 열 오류 · 400</button>
      <button class="err-btn" onclick="runPreset(`SELECT * FROM users WHERE id = '2';`)">8. 타입 불일치 (id = '2') · 400</button>
    </div>

    <div class="guard-box">
      <div class="label">server_guard.py · server.py HTTP 입력 오류 실제 테스트 (오류 시 아래 응답이 빨갛게 변합니다)</div>
      <div class="btns" style="margin-bottom:6px;">
        <button class="err-btn" onclick="sendGuardTest('bad_key')">{"query":...} (400)</button>
        <button class="err-btn" onclick="sendGuardTest('bad_json')">깨진 JSON (400)</button>
        <button class="err-btn" onclick="sendGuardTest('not_found')">POST /users (404)</button>
        <button class="err-btn" onclick="sendGuardTest('method')">GET /query (405)</button>
        <button class="err-btn" onclick="sendGuardTest('too_large')">본문 1MB 초과 (413)</button>
      </div>
      <div class="note">
        * <code>HTTP/0.9</code>, <code>Transfer-Encoding: chunked</code>, <code>Content-Length: 3_4</code>, 짧은 본문(400), 요청 줄 65KB(413), 감시 5초(408), 큐 16칸 포화(503)는 브라우저가 비정상 HTTP 규격을 막기 때문에 터미널에서 <code>python3 checks/check_guard.py</code> · <code>python3 checks/check_threadpool.py</code>로 검증합니다.
      </div>
    </div>

    <textarea id="sql" rows="3">INSERT INTO users (age, name) VALUES (25, '현지');</textarea>
    <div style="margin-top:8px; display:flex; justify-content:flex-end; gap:8px;">
      <button onclick="loadRows()">쌓인 데이터 새로고침</button>
      <button class="primary" onclick="runQuery()">POST /query 실행</button>
    </div>

    <div id="status" class="meta">아직 요청을 보내지 않았습니다.</div>
    <pre id="out">응답 JSON이 여기에 표시됩니다.</pre>

    <div class="box" style="margin-top:16px; margin-bottom:0;">
      <div class="label" id="rows-title">현재 data/users.tbl에 쌓인 데이터</div>
      <table>
        <thead><tr id="rows-head"></tr></thead>
        <tbody id="rows-body"></tbody>
      </table>
    </div>
  </div>

  <script>
    const SCHEMA = __SCHEMA_JSON__;
    const TABLE = Object.keys(SCHEMA)[0] || "users";
    document.getElementById("schema").textContent = JSON.stringify(SCHEMA, null, 2);

    function runPreset(sql) {
      document.getElementById("sql").value = sql;
      runQuery();
    }

    function renderResult(res, text) {
      const worker = res.headers.get("X-Worker") || "-";
      const statusEl = document.getElementById("status");
      const outEl = document.getElementById("out");
      const isErr = res.status >= 400;
      statusEl.textContent = `HTTP ${res.status} · X-Worker: ${worker}`;
      statusEl.className = isErr ? "meta is-error" : "meta";
      outEl.className = isErr ? "is-error" : "";
      try {
        outEl.textContent = JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        outEl.textContent = text;
      }
    }

    async function runQuery() {
      const sql = document.getElementById("sql").value;
      const res = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql })
      });
      const text = await res.text();
      renderResult(res, text);
      loadRows();
    }

    async function sendGuardTest(kind) {
      let method = "POST";
      let path = "/query";
      let body = null;
      if (kind === "bad_key") body = JSON.stringify({ query: `SELECT * FROM ${TABLE};` });
      else if (kind === "bad_json") body = '{"sql": ';
      else if (kind === "not_found") { path = "/users"; body = JSON.stringify({ sql: `SELECT * FROM ${TABLE};` }); }
      else if (kind === "method") { method = "GET"; }
      else if (kind === "too_large") { body = "x".repeat(1048577); }

      const opts = { method };
      if (body !== null) {
        opts.headers = { "Content-Type": "application/json" };
        opts.body = body;
      }
      const res = await fetch(path, opts);
      const text = await res.text();
      renderResult(res, text);
    }

    async function loadRows() {
      const res = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: `SELECT * FROM ${TABLE};` })
      });
      if (!res.ok) return;
      const data = await res.json();
      const sel = data.results && data.results[0];
      if (!sel || sel.type !== "select") return;
      document.getElementById("rows-title").textContent = `현재 ${TABLE}.tbl에 쌓인 데이터 (총 ${sel.rows.length}건)`;
      document.getElementById("rows-head").innerHTML = sel.columns.map(c => `<th>${c}</th>`).join("");
      document.getElementById("rows-body").innerHTML = sel.rows.length
        ? sel.rows.map(r => `<tr>${r.map(v => `<td>${String(v)}</td>`).join("")}</tr>`).join("")
        : `<tr><td colspan="${sel.columns.length}" style="color:#64748b;">(비어 있음)</td></tr>`;
    }

    loadRows();
  </script>
</body>
</html>"""


def linger_close(sock, timeout=0.2, idle=0.02):
    """Phase 3(15·17단계): 답을 보낸 뒤 '보내기'만 먼저 닫고, 클라이언트가 보내던 요청을 잠깐 읽어 버린다.

    요청을 읽지 않은 채 바로 닫으면 운영체제가 연결을 강제로 끊어서(RST) 클라이언트가 503을 못 읽을 수 있다.
    최대 timeout초까지 읽되, idle초 동안 아무것도 안 오면 바로 끝낸다 (받는 스레드를 오래 붙잡지 않게).
    """
    try:
        sock.shutdown(socket.SHUT_WR)             # "답은 다 보냈다"고 알림
    except OSError:
        return
    try:
        sock.settimeout(idle)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not sock.recv(65536):              # 클라이언트가 닫으면 끝
                break
    except OSError:                               # idle초 동안 아무것도 안 옴(timeout)도 여기로
        pass


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/query":
            self.send_error(501)                  # GET /query → 기존 테스트(check_errors)대로 405 유지
            return
        if self.path == "/health":                # 살아 있는지 (Render가 잠들었는지 확인할 때도 씀)
            self._send(200, {"status": "ok"})
            return
        if self.path == "/stats":                 # Thread Pool이 지금 어떤 상태인지
            self._send(200, self.server.stats())
            return
        if self.path not in ("/", "/docs"):
            self._error(404, "not_found", f"없는 주소입니다: {self.path} (브라우저는 / 또는 /docs, 상태는 /health · /stats, API는 POST /query)")
            return
        schema_json = json.dumps(self.server.engine.schema, ensure_ascii=False).replace("</", "<\\/")
        out = API_PAGE_HTML.replace("__SCHEMA_JSON__", schema_json).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("X-Worker", threading.current_thread().name)
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):
        if self.path != "/query":
            self._error(404, "not_found", f"없는 주소입니다: {self.path} (POST /query 만 있습니다)")
            return
        raw = self._read_body()
        if raw is None:                           # 이미 오류로 답함
            return
        sql = self._parse_sql(raw)
        if sql is None:                           # 이미 오류로 답함
            return
        try:
            results = self.server.engine.execute(sql, stop_on_error=True)   # 첫 오류에서 멈춤 (D30)
        except Exception:
            # Phase 3(17단계, D39): SQL이 틀린 게 아니라 서버가 고장. 자세한 내용은 서버 로그에만
            traceback.print_exc()
            self._error(500, "internal", "서버 내부 오류입니다. 이 요청의 앞쪽 문장은 이미 저장됐을 수 있습니다")
            return
        if results and results[-1]["type"] == "error":
            done = results[:-1]                   # 실패 전까지 실행된(이미 저장된) 문장
            if results[-1].get("stage") == "parse":   # 문법 오류는 문장 전체를 거절 (몇 번째 문장인지는 메시지의 줄:칸에)
                message = results[-1]["message"]
            else:
                message = f"{len(done) + 1}번째 문장: {results[-1]['message']}"
            self._send(400, error_body("bad_sql", message, results=done))
            return
        self._send(200, {"results": results})

    def _read_body(self):
        """본문을 Content-Length만큼 읽는다. 숫자가 아니면 400으로 답하고 None. (server_guard.py가 검사를 더함)"""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._error(400, "bad_request", f"잘못된 Content-Length입니다: {self.headers.get('Content-Length')}")
            return None
        return self.rfile.read(length)

    def _parse_sql(self, raw):
        """본문 JSON에서 sql 문자열을 꺼낸다. 틀리면 400으로 답하고 None."""
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or "sql" not in body:
                raise ValueError('본문은 {"sql": "..."} 모양이어야 합니다')
            if not isinstance(body["sql"], str):
                raise ValueError("sql은 문자열이어야 합니다")
            return body["sql"]
        except (ValueError, RecursionError) as e:   # JSON 오류도 ValueError. RecursionError는 [[[[... 처럼 아주 깊은 JSON
            self._error(400, "bad_request", f"본문을 읽을 수 없습니다: {e}")
            return None

    def send_error(self, code, message=None, explain=None):
        """Phase 3(17단계): http.server가 스스로 내는 오류도 JSON으로 (원래는 HTML).

        요청 줄이 깨졌거나, 주소·머리가 너무 길거나, do_GET 같은 함수가 없을 때 http.server가 이 함수를 부른다.
        """
        self.close_connection = True
        status, error_code, text = HTTP_ERRORS.get(code, HTTP_ERRORS[400])
        if status == 405:
            text = f"{self.command}는 받지 않습니다. POST /query 를 쓰세요"
        elif message and status == 400:
            text = f"{text} ({message})"           # 파이썬이 준 원래 설명(영어)을 괄호로 붙임
        self._error(status, error_code, text)

    def _error(self, status, code, message):
        self._send(status, error_body(code, message))

    def _send(self, status, obj):
        out = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if self.request_version == "HTTP/0.9":
            # Python 3.12 이하는 요청 줄이 깨지면 버전을 HTTP/0.9로 둔 채 오류를 보냄 → 상태 줄·머리 없이 본문만 나감
            self.request_version = "HTTP/1.0"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("X-Worker", threading.current_thread().name)   # Phase 3(15단계): 어느 스레드가 처리했는지
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, format, *args):
        # Phase 3(15단계): 로그 앞에 처리한 스레드 이름을 붙임. 여러 스레드가 나눠 처리하는 것을 눈으로 확인
        print(f"[{threading.current_thread().name}] {self.address_string()} - {format % args}")


class PooledHTTPServer(HTTPServer):
    """Phase 3(15단계): 요청을 큐에 넣고, 미리 만든 스레드 N개가 꺼내서 처리하는 서버.

    받는 스레드(serve_forever를 돌리는 스레드)는 연결을 받아 큐에 넣기만 하고 바로 다음 연결을 받는다.
    실제 처리(요청 읽기 → engine.execute → 응답 쓰기)는 일하는 스레드들이 한다.
    """

    request_queue_size = 128                  # 운영체제가 받아 두는 연결 수 (동시 요청이 많을 때 연결이 거절되지 않게)

    def __init__(self, address, handler, engine, workers=4, queue_size=16, request_timeout=5):
        # Phase 3(17단계): 포트가 이미 쓰이면 super().__init__ 안에서 server_close()가 불린다.
        # 그때 server_close가 쓰는 것(jobs, workers)이 없으면 진짜 이유가 AttributeError에 가려지므로 먼저 만든다
        self.engine = engine                  # 모든 스레드가 같은 엔진 하나를 씀 (lock은 엔진 안에)
        self.request_timeout = request_timeout
        self.jobs = queue.Queue(maxsize=queue_size)
        self.workers = []
        self._stats_lock = threading.Lock()   # 아래 숫자 셋만 보호 (엔진 lock과 별개라 SQL 실행을 막지 않음)
        self._busy = 0                        # 지금 요청을 처리 중인 스레드 수
        self._handled = 0                     # 처리를 끝낸 요청 수
        self._rejected = 0                    # 대기열이 꽉 차서 503으로 돌려보낸 수
        handler = type(handler.__name__, (handler,), {"timeout": request_timeout})   # 한 번 받을 때 기다리는 최대 시간
        super().__init__(address, handler)
        self.workers = [
            threading.Thread(target=self._work, name=f"worker-{n}", daemon=True)
            for n in range(1, workers + 1)
        ]
        for worker in self.workers:
            worker.start()

    def process_request(self, request, client_address):
        """받는 스레드가 연결 하나를 받을 때마다 부름. 큐에 넣기만 한다."""
        try:
            self.jobs.put_nowait((request, client_address))   # 기다리지 않음. 꽉 차 있으면 바로 Full
        except queue.Full:
            with self._stats_lock:
                self._rejected += 1
            self._reject_busy(request)
            self.shutdown_request(request)

    def _work(self):
        """일하는 스레드 하나가 하는 일: 큐에서 꺼내 처리하기를 계속 반복한다."""
        while True:
            job = self.jobs.get()                 # 큐가 비어 있으면 일이 들어올 때까지 여기서 기다림
            if job is None:                       # 서버를 끌 때 넣는 "그만" 신호
                return
            request, client_address = job
            with self._stats_lock:
                self._busy += 1
            try:
                self.finish_request(request, client_address)   # Handler를 만들어 do_POST 등을 실행
            except Exception:
                self.handle_error(request, client_address)
            finally:
                self.shutdown_request(request)    # 연결 닫기
                with self._stats_lock:
                    self._busy -= 1
                    self._handled += 1

    def stats(self):
        """GET /stats: Thread Pool의 지금 상태. /stats 요청 자신도 스레드 하나를 쓰므로 busy는 1 이상."""
        with self._stats_lock:
            return {"workers": len(self.workers), "busy": self._busy,
                    "queue": {"waiting": self.jobs.qsize(), "max": self.jobs.maxsize},
                    "handled": self._handled, "rejected_503": self._rejected}

    def _reject_busy(self, request):
        """큐가 꽉 찼을 때: 503 JSON을 보내고, 클라이언트가 읽을 수 있게 닫는다."""
        try:
            request.sendall(BUSY_RESPONSE)
        except OSError:
            return
        linger_close(request)

    def server_close(self):
        super().server_close()
        while True:                               # Phase 3(17단계): 아직 못 꺼낸 연결은 닫고 버려서 "그만" 신호 자리를 만듦
            try:
                job = self.jobs.get_nowait()
            except queue.Empty:
                break
            if job is not None:
                self.shutdown_request(job[0])
        for _ in self.workers:
            try:
                self.jobs.put_nowait(None)        # 스레드마다 "그만" 신호 하나씩
            except queue.Full:
                break
        for worker in self.workers:
            worker.join(timeout=1)


def positive_int(text):
    """Phase 3(17단계): 1 이상의 정수만 받는다. --queue 0이면 Queue(0) = 크기 제한 없음이 되어 503이 사라짐."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {text}")
    return value


def parse_arguments():
    parser = argparse.ArgumentParser(description="미니 DBMS API 서버")
    parser.add_argument("--host", default="localhost", help="받을 주소 (기본 localhost. 배포할 때는 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="받을 포트 (기본 8000)")
    parser.add_argument("--workers", type=positive_int, default=4, help="미리 만들어 둘 스레드 수 (기본 4)")
    parser.add_argument("--queue", type=positive_int, default=16, help="기다릴 수 있는 요청 수 (기본 16)")
    return parser.parse_args()


def main(server_class=PooledHTTPServer, handler_class=Handler):
    args = parse_arguments()
    try:
        engine = Engine("data")
    except OSError as e:                      # Phase 3(17단계): data/ 폴더가 없는 곳에서 켠 경우
        sys.exit(f"데이터 폴더를 열 수 없습니다 (저장소 맨 위 폴더에서 실행하세요): {e}")
    try:
        server = server_class((args.host, args.port), handler_class, engine, args.workers, args.queue)
    except (OSError, OverflowError) as e:     # Phase 3(17단계): 포트가 이미 쓰임, 없는 포트 번호 등
        sys.exit(f"서버를 켤 수 없습니다 (포트 {args.port}): {e}")
    port = server.server_address[1]           # --port 0이면 운영체제가 고른 빈 포트
    print(f"http://{args.host}:{port} 에서 POST /query 를 기다립니다 (스레드 {args.workers}개, 큐 {args.queue}칸)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 끕니다")
    finally:
        server.server_close()


if __name__ == "__main__":
    import server_guard                      # 기본으로 엣지 케이스 방어(server_guard.py)를 켠 서버를 띄움
    server_guard.main()
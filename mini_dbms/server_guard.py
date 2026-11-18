"""Phase 3(17단계) 엣지 케이스 방어: server.py의 Handler와 PooledHTTPServer를 물려받아 몇 함수만 덮어쓴다.

server.py만으로도 과제 기능(Thread Pool, JSON 오류)은 다 됩니다. 이 파일은 "정상 사용에서는 잘 안 생기지만,
생기면 서버가 멈추거나 이상하게 답하는 경우"를 막습니다.

| 막는 것                                   | 막지 않으면                          | 답      |
| 연결만 열고 안 보냄 / 아주 천천히 보냄     | 일하는 스레드가 붙잡혀 서버 전체가 멈춤 | 408     |
| Content-Length 없음·음수·숫자 아님·'3_4'  | 대답 없이 끊기거나 이상한 길이로 읽음   | 400     |
| Content-Length가 1MB 넘음                 | 그만큼 메모리를 잡음                    | 413     |
| 본문을 나눠 보냄(chunked)                 | 본문 없이 처리됨                        | 400     |
| HTTP/0.9 형식의 한 줄 요청(`GET /`)       | 응답에 상태 줄이 없음                   | 400     |
| 답을 보내기 전에 클라이언트가 끊음          | 서버 로그에 트레이스백이 쏟아짐          | (조용히) |

`python3 server.py`로 켜면 이 파일의 서버가 뜹니다. `python3 server_guard.py`로 켜도 같습니다.
"""
import socket
import sys
import threading
import time

import server
from server import Handler, PooledHTTPServer, linger_close

MAX_BODY = 1024 * 1024   # 본문은 최대 1MB. INSERT 약 1.7만 문장. 대량 넣기는 CLI로


class GuardedHandler(Handler):
    def handle_one_request(self):
        """요청 줄·머리·본문을 받는 시간 '전체'에 마감(request_timeout초)을 건다. 넘으면 408 JSON.

        http.server의 원래 handle_one_request는 시간이 넘으면 응답 없이 끊기만 해서, 408을 보낼 자리를 만들려고
        같은 순서(요청 줄 읽기 → parse_request → do_POST 등)를 여기서 직접 한다.
        """
        self.requestline = self.request_version = self.command = ""
        self._timed_out = threading.Event()
        self._token = self.server._watch(self.connection, self._timed_out)   # 감시 스레드에 "마감 = 지금 + 5초" 등록
        try:
            try:
                self.raw_requestline = self.rfile.readline(65537)
            except TimeoutError:
                self._timed_out.set()
                self.raw_requestline = b""
            if self._timed_out.is_set():          # 요청 줄을 다 받기 전에 마감
                self._timeout_error()
                return
            if len(self.raw_requestline) > 65536:
                self.close_connection = True
                self._error(413, "too_large", "요청 줄이 너무 깁니다")
                return
            if not self.raw_requestline:          # 아무것도 안 보내고 닫음
                self.close_connection = True
                return
            if not self.parse_request():          # 요청 줄·머리 읽기. 틀리면 send_error로 이미 답함
                return
            if self._timed_out.is_set():          # 머리를 다 받기 전에 마감
                self._timeout_error()
                return
            method = getattr(self, "do_" + self.command, None)
            if method is None:
                self.send_error(501)              # → 405 JSON (server.py의 send_error)
                return
            method()
            self.wfile.flush()
        except TimeoutError:                      # 감시 스레드보다 소켓 timeout이 먼저 온 경우
            self._timeout_error()
        finally:
            self.server._unwatch(self._token)     # 여러 번 불러도 됨

    def parse_request(self):
        """HTTP/0.9 형식(`GET /`처럼 버전이 없는 한 줄)은 받지 않는다. 받으면 응답에 상태 줄이 빠진다."""
        if not super().parse_request():
            return False
        if self.request_version == "HTTP/0.9":
            self.request_version = "HTTP/1.0"     # 이렇게 바꿔야 상태 줄과 머리가 붙은 응답이 나감
            self.close_connection = True
            self._error(400, "bad_request", "HTTP/1.0 또는 HTTP/1.1 형식으로 보내 주세요")
            return False
        return True

    def _timeout_error(self):
        self.close_connection = True
        self._error(408, "timeout", f"{self.server.request_timeout}초 안에 요청을 다 받지 못했습니다")

    def _read_body(self):
        """server.py의 _read_body에 검사를 더한다: Content-Length는 0~9로만 된 숫자, 1MB까지, 받는 시간 마감."""
        if "Transfer-Encoding" in self.headers:
            self._error(400, "bad_request", "본문을 나눠 보내는 방식(Transfer-Encoding)은 받지 않습니다. Content-Length를 보내 주세요")
            return None
        value = self.headers.get("Content-Length")
        if value is None:
            self._error(400, "bad_request", "Content-Length가 필요합니다")
            return None
        if not (value.isascii() and value.isdigit()):   # -1, abc, 1e3, 3_4(파이썬 int()는 밑줄을 허용) 모두 막음
            self._error(400, "bad_request", f"잘못된 Content-Length입니다: {value}")
            return None
        length = int(value)
        if length > MAX_BODY:
            self.close_connection = True
            self._error(413, "too_large", f"요청 본문이 너무 큽니다 (최대 {MAX_BODY // (1024 * 1024)}MB). 대량 넣기는 CLI를 쓰세요")
            self.wfile.flush()
            linger_close(self.connection)         # 읽지 않은 본문이 남아 있으니 413을 읽을 수 있게 닫음
            return None
        try:
            raw = self.rfile.read(length)         # 감시 스레드가 받기를 닫으면 덜 받은 채로 끝남
        except TimeoutError:
            self._timed_out.set()
            raw = b""
        timed_out = self._timed_out.is_set()
        self.server._unwatch(self._token)         # 다 받았으면 마감 끝. 그 뒤 lock 기다림·실행 시간은 안 셈
        if timed_out:
            self._timeout_error()
            return None
        if len(raw) < length:                     # 클라이언트가 덜 보내고 닫음
            self.close_connection = True
            self._error(400, "bad_request", "본문이 Content-Length보다 짧습니다")
            return None
        return raw


class GuardedServer(PooledHTTPServer):
    """PooledHTTPServer + 감시 스레드 1개. 감시 스레드는 마감이 지난 연결의 '받기'만 닫아서 막힌 읽기를 깨운다."""

    def __init__(self, address, handler, engine, workers=4, queue_size=16, request_timeout=5):
        self._watch_lock = threading.Lock()        # 일하는 스레드들과 감시 스레드가 _watching을 같이 씀
        self._watching = {}                        # 번호 → (마감 시각, 연결, 마감됐다는 표시)
        self._next_token = 0
        self._stop_watch = threading.Event()
        self._watcher = threading.Thread(target=self._watch_loop, name="watcher", daemon=True)
        super().__init__(address, handler, engine, workers, queue_size, request_timeout)
        self.RequestHandlerClass.timeout = request_timeout + 0.5   # 소켓 timeout은 예비. 감시 스레드가 먼저 깨우도록 조금 늦게
        self._watcher.start()

    def _watch(self, sock, event):
        with self._watch_lock:
            self._next_token += 1
            if self._stop_watch.is_set():          # 끄는 중에 큐에서 꺼낸 연결은 바로 깨움
                event.set()
                try:
                    sock.shutdown(socket.SHUT_RD)
                except OSError:
                    pass
            else:
                self._watching[self._next_token] = (time.monotonic() + self.request_timeout, sock, event)
            return self._next_token

    def _unwatch(self, token):
        with self._watch_lock:
            self._watching.pop(token, None)

    def _watch_loop(self):
        """감시 스레드: 0.05초마다 마감이 지난 연결을 찾아 받기 쪽을 닫는다."""
        while not self._stop_watch.is_set():
            now = time.monotonic()
            with self._watch_lock:
                expired = [t for t, (deadline, _, _) in self._watching.items() if now >= deadline]
                expired = [self._watching.pop(t) for t in expired]
            for _, sock, event in expired:
                event.set()
                try:
                    sock.shutdown(socket.SHUT_RD)  # 받기만 닫음. 막혀 있던 읽기가 바로 끝나고, 보내기는 열려 있어 408을 보낼 수 있음
                except OSError:
                    pass
            self._stop_watch.wait(0.05)

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return                                 # 답을 보내기 전에 클라이언트가 먼저 끊음. 서버 잘못이 아니라 조용히
        super().handle_error(request, client_address)

    def server_close(self):
        with self._watch_lock:                     # 끄기 표시와 깨우기를 한 번에 (그 사이에 새로 등록되는 연결이 없게)
            self._stop_watch.set()
            watched = list(self._watching.values())
            self._watching.clear()
        for _, sock, event in watched:             # 받기에서 막혀 있는 일하는 스레드를 깨워야 "그만" 신호를 받음
            event.set()
            try:
                sock.shutdown(socket.SHUT_RD)
            except OSError:
                pass
        super().server_close()
        if self._watcher.is_alive():
            self._watcher.join(timeout=1)


def main():
    server.main(GuardedServer, GuardedHandler)


if __name__ == "__main__":
    main()

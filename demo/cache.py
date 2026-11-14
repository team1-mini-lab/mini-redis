"""데모 API가 쓰는 캐시. 두 가지를 같은 모양(get / set / delete)으로 제공한다.

RedisCache  mini-redis를 HTTP로 부른다. 캐시가 앱 서버 **밖**에 있다.
            데모 API를 몇 대 띄워도 모두 같은 캐시를 본다.

LocalCache  앱 서버 **안**의 dict에 저장한다. 3차 체크인에서 발표한 "로컬 캐시"다.
            서버가 한 대면 RedisCache와 똑같이 동작하지만, 여러 대가 되면
            서버마다 캐시가 따로 생긴다. 비교 시연을 위해 일부러 둔다.

app.py는 둘 중 무엇을 쓰는지 모르고 get / set / delete만 부른다.
그래서 같은 코드에서 캐시만 바꿔 끼워 두 경우를 비교할 수 있다.
"""
import os
import threading
import time

import requests


class RedisCache:
    """mini-redis 클라이언트.

    과제 R8의 "외부에서 사용할 수 있어야 한다"를 보여 주기 위해 import가 아니라
    HTTP로 부른다. 데모 API와 mini-redis는 서로 다른 프로세스이고, 다른 포트에서 돈다.
    이것이 "상태를 서버 밖으로 뺀다"는 말의 실제 모습이다.

    mini-redis가 죽어 있어도 데모 API는 계속 동작해야 한다 (DB로 바로 가면 되므로).
    그래서 통신 실패는 "캐시에 없음"과 같게 다룬다. Cache-Aside라서 가능한 일이다.
    """

    name = "redis"
    TIMEOUT = 1.0   # 캐시 때문에 응답이 느려지면 안 되니 짧게 끊는다

    def __init__(self, base_url=None):
        # 접점 합의: mini-redis 8000, 데모 API 8001
        self.base_url = base_url or os.environ.get("MINI_REDIS_URL", "http://127.0.0.1:8000")
        self._warned = False

    def _warn_once(self, error):
        if not self._warned:
            print(f"[cache] mini-redis에 연결할 수 없습니다 ({error}). DB로 직접 갑니다.")
            self._warned = True

    def get(self, key):
        """캐시에서 값을 가져온다. 없거나(404) 통신에 실패하면 None (캐시 미스)."""
        try:
            response = requests.get(
                f"{self.base_url}/get", params={"key": key}, timeout=self.TIMEOUT
            )
        except requests.RequestException as error:
            self._warn_once(error)
            return None
        if response.status_code != 200:     # 404 = 없는 키 또는 만료된 키
            return None
        return response.json()["value"]

    def set(self, key, value, ttl=None):
        """캐시에 값을 저장한다. 실패해도 조용히 넘어간다.

        캐시 저장에 실패하는 것은 성능 문제일 뿐 기능 문제가 아니다.
        다음 조회가 또 DB로 가기만 할 뿐, 틀린 답을 주지는 않는다.
        """
        body = {"key": key, "value": value}
        if ttl is not None:
            body["ttl"] = ttl
        try:
            requests.post(f"{self.base_url}/set", json=body, timeout=self.TIMEOUT)
        except requests.RequestException as error:
            self._warn_once(error)

    def delete(self, key):
        """캐시에서 키를 지운다 (무효화). 지워졌으면 True.

        원본(DB)을 고친 직후에 부른다. 이 한 번으로 캐시를 보는 모든 앱 서버가
        새 값을 보게 된다.
        """
        try:
            response = requests.delete(
                f"{self.base_url}/delete", params={"key": key}, timeout=self.TIMEOUT
            )
        except requests.RequestException as error:
            self._warn_once(error)
            return False
        if response.status_code != 200:
            return False
        return response.json().get("deleted", False)

    def ping(self):
        """mini-redis가 떠 있는지 확인한다."""
        try:
            return requests.get(f"{self.base_url}/", timeout=self.TIMEOUT).status_code == 200
        except requests.RequestException:
            return False


class LocalCache:
    """앱 서버 프로세스 안의 dict 캐시 (비교용).

    get / set / delete와 TTL은 RedisCache와 똑같이 동작한다. 다른 점은 단 하나,
    이 dict가 **이 프로세스 안에만** 있다는 것이다.

    - 다른 서버에서 delete를 불러도 이 dict는 지워지지 않는다 → 장면 ①
    - 서버를 재시작하면 dict도 함께 사라진다 → 장면 ③
    - 서버마다 같은 값을 따로 DB에서 가져와 따로 저장한다 → 장면 ④
    """

    name = "local"

    def __init__(self):
        self._data = {}                    # key → (value, expire_at)
        self._lock = threading.Lock()      # Flask가 요청을 여러 스레드로 받으므로

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if expire_at is not None and time.monotonic() >= expire_at:
                del self._data[key]        # 지연 삭제
                return None
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            expire_at = None if ttl is None else time.monotonic() + ttl
            self._data[key] = (value, expire_at)

    def delete(self, key):
        with self._lock:
            return self._data.pop(key, None) is not None

    def ping(self):
        return True                        # 자기 메모리라 항상 살아 있음


def make_cache(mode):
    """'redis' 또는 'local'에 맞는 캐시를 만든다."""
    if mode == "redis":
        return RedisCache()
    if mode == "local":
        return LocalCache()
    raise ValueError(f"알 수 없는 캐시 모드입니다: {mode} (redis 또는 local)")

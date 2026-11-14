"""데모 API가 쓰는 캐시 두 가지. 둘 다 get / set / delete / ping을 같은 모양으로 내놓는다.

RedisCache  앱 서버 밖의 mini-redis를 HTTP로 부른다. 앱 서버가 몇 대든 같은 캐시를 본다.
LocalCache  앱 서버 프로세스 안의 dict에 둔다. 서버마다 캐시가 따로 생긴다 (비교용).
"""
import os
import threading
import time

import requests

DEFAULT_MINI_REDIS_URL = "http://127.0.0.1:8000"


def make_cache(mode):
    if mode == "redis":
        return RedisCache()
    if mode == "local":
        return LocalCache()
    raise ValueError(f"알 수 없는 캐시 모드입니다: {mode} (redis 또는 local)")


class RedisCache:
    """mini-redis와 통신이 안 되면 "캐시에 없음"으로 다룬다. 앱은 DB로 가서 계속 동작한다."""

    name = "redis"
    TIMEOUT_SECONDS = 1.0

    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("MINI_REDIS_URL", DEFAULT_MINI_REDIS_URL)
        self._already_warned = False

    def get(self, key):
        response = self._request("GET", "/get", params={"key": key})
        if not _is_ok(response):
            return None
        return response.json()["value"]

    def set(self, key, value, ttl=None):
        body = {"key": key, "value": value}
        if ttl is not None:
            body["ttl"] = ttl
        self._request("POST", "/set", json=body)

    def delete(self, key):
        response = self._request("DELETE", "/delete", params={"key": key})
        if not _is_ok(response):
            return False
        return response.json().get("deleted", False)

    def ping(self):
        return _is_ok(self._request("GET", "/", warn_on_failure=False))

    def _request(self, method, path, warn_on_failure=True, **kwargs):
        """통신에 실패하면 None."""
        try:
            return requests.request(
                method, f"{self.base_url}{path}", timeout=self.TIMEOUT_SECONDS, **kwargs
            )
        except requests.RequestException as error:
            if warn_on_failure:
                self._warn_once(error)
            return None

    def _warn_once(self, error):
        if not self._already_warned:
            print(f"[cache] mini-redis에 연결할 수 없습니다 ({error}). DB로 직접 갑니다.")
            self._already_warned = True


def _is_ok(response):
    return response is not None and response.status_code == 200


class LocalCache:
    name = "local"

    def __init__(self):
        self._entries = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if _is_expired(expire_at):
                del self._entries[key]
                return None
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            expire_at = None if ttl is None else time.monotonic() + ttl
            self._entries[key] = (value, expire_at)

    def delete(self, key):
        with self._lock:
            return self._entries.pop(key, None) is not None

    def ping(self):
        return True


def _is_expired(expire_at):
    return expire_at is not None and time.monotonic() >= expire_at

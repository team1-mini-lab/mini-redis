"""mini-redis를 쓰는 클라이언트.

과제 R8의 "외부에서 사용할 수 있어야 한다"를 보여 주기 위해 import가 아니라
HTTP로 부른다. 데모 API와 mini-redis는 서로 다른 프로세스이고, 다른 포트에서 돈다.
이것이 "상태를 서버 밖으로 뺀다"는 말의 실제 모습이다.

mini-redis가 죽어 있어도 데모 API는 계속 동작해야 한다 (DB로 바로 가면 되므로).
그래서 통신 실패는 "캐시에 없음"과 같게 다룬다. Cache-Aside라서 가능한 일이다.
"""
import os

import requests

# mini-redis 주소. 접점 합의: mini-redis 8000, 데모 API 8001
BASE_URL = os.environ.get("MINI_REDIS_URL", "http://127.0.0.1:8000")

# 캐시 때문에 응답이 느려지면 안 되니 짧게 끊는다.
TIMEOUT = 1.0

# 캐시가 살아 있는지 알려 주는 플래그. 한 번 실패하면 로그에 남긴다.
_warned = False


def _warn_once(error):
    global _warned
    if not _warned:
        print(f"[cache] mini-redis에 연결할 수 없습니다 ({error}). DB로 직접 갑니다.")
        _warned = True


def get(key):
    """캐시에서 값을 가져온다. 없거나(404) 통신에 실패하면 None.

    None은 "캐시 미스"를 뜻한다. 호출하는 쪽은 DB를 조회하면 된다.
    """
    try:
        response = requests.get(f"{BASE_URL}/get", params={"key": key}, timeout=TIMEOUT)
    except requests.RequestException as error:
        _warn_once(error)
        return None
    if response.status_code == 404:        # 없는 키 또는 만료된 키
        return None
    if response.status_code != 200:
        return None
    return response.json()["value"]


def set(key, value, ttl=None):
    """캐시에 값을 저장한다. 실패해도 조용히 넘어간다.

    캐시 저장에 실패하는 것은 성능 문제일 뿐 기능 문제가 아니다.
    다음 조회가 또 DB로 가기만 할 뿐, 틀린 답을 주지는 않는다.
    """
    body = {"key": key, "value": value}
    if ttl is not None:
        body["ttl"] = ttl
    try:
        requests.post(f"{BASE_URL}/set", json=body, timeout=TIMEOUT)
    except requests.RequestException as error:
        _warn_once(error)


def delete(key):
    """캐시에서 키를 지운다 (무효화). 지워졌으면 True.

    원본(DB)을 고친 직후에 부른다. 이 한 번으로 캐시를 보는 모든 앱 서버가
    새 값을 보게 된다 — 로컬 캐시라면 다른 서버의 메모리를 지울 방법이 없었다.
    """
    try:
        response = requests.delete(f"{BASE_URL}/delete", params={"key": key}, timeout=TIMEOUT)
    except requests.RequestException as error:
        _warn_once(error)
        return False
    if response.status_code != 200:
        return False
    return response.json().get("deleted", False)


def ping():
    """mini-redis가 떠 있는지 확인한다. 데모 시작 전 점검용."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        return response.status_code == 200
    except requests.RequestException:
        return False

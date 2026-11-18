"""데이터 유지: 저장소 내용을 스냅샷 파일(JSON)에 적고, 서버를 켤 때 읽어 다시 채운다.

파일 모양: {"version": 1, "items": [{"key": ..., "value": ..., "expire": 벽시계 만료 시각 또는 null}]}
"""
import json
import os
import sys

SNAPSHOT_VERSION = 1
SNAPSHOT_INTERVAL = 30   # 스냅샷 스레드가 쉬는 시간(초). 바뀐 게 없으면 그 차례는 건너뛴다


def save_snapshot(store, path):
    """스냅샷 한 번. lock 안에서 목록만 모으고(빠른 단계), 파일 쓰기는 lock 밖에서 한다(느린 단계).

    같은 폴더의 .tmp에 끝까지 쓴 뒤 os.replace로 바꿔치기한다.
    쓰는 도중 죽어도 path에는 이전 스냅샷이 그대로 남는다.
    """
    items = store.snapshot_items()
    try:
        write_atomically(path, {"version": SNAPSHOT_VERSION, "items": items})
    except Exception:
        store.mark_changed()   # 못 썼으니 다음 차례에 다시 쓴다
        raise
    return len(items)


def write_atomically(path, data):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    os.replace(temporary, path)


def load_snapshot(store, path):
    """서버를 켤 때 요청을 받기 전에 부른다. 넣은 키 수를 돌려준다.

    파일 상태는 세 가지로 나눈다.
    - 없음: 빈 저장소로 시작
    - 정상: 읽어서 채움. 꺼져 있던 동안 만료된 키는 넣지 않음
    - 깨짐: .broken으로 옮기고 경고한 뒤 빈 저장소로 시작 (다음 스냅샷이 증거를 덮어쓰지 않게)
    .tmp 파일은 쓰다 만 것일 수 있으므로 보지 않는다.
    """
    if not os.path.exists(path):
        return 0
    try:
        with open(path, encoding="utf-8") as file:
            items = valid_items(json.load(file))
    except (ValueError, UnicodeDecodeError) as error:
        os.replace(path, path + ".broken")
        print(f"경고: 스냅샷 파일이 깨져 {path}.broken으로 옮기고 빈 저장소로 시작합니다 ({error})", file=sys.stderr)
        return 0
    return store.restore(items)


def valid_items(data):
    """파일 내용이 약속한 모양인지 확인하고 items를 돌려준다. 모양이 다르면 ValueError."""
    if not isinstance(data, dict) or data.get("version") != SNAPSHOT_VERSION:
        raise ValueError("version이 1이 아닙니다")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("items가 목록이 아닙니다")
    for item in items:
        if not is_valid_item(item):
            raise ValueError(f"항목 모양이 다릅니다: {item!r}")
    return items


def is_valid_item(item):
    if not isinstance(item, dict) or set(item) != {"key", "value", "expire"}:
        return False
    key, value, expire = item["key"], item["value"], item["expire"]
    is_number = isinstance(expire, (int, float)) and not isinstance(expire, bool)
    return isinstance(key, str) and key != "" and value is not None and (expire is None or is_number)


def run_snapshots(store, path, stop):
    """stop(threading.Event)이 켜질 때까지 SNAPSHOT_INTERVAL초마다, 바뀐 게 있을 때만 스냅샷을 찍는다.

    백그라운드 스레드에서 돌린다. 저장에 실패해도 스레드는 멈추지 않고 다음 차례에 다시 시도한다.
    """
    while not stop.wait(SNAPSHOT_INTERVAL):
        if not store.has_changes():
            continue
        try:
            save_snapshot(store, path)
        except OSError as error:
            print(f"경고: 스냅샷을 저장하지 못했습니다 ({error})", file=sys.stderr)

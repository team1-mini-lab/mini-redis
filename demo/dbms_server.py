"""미니 DBMS 서버(mini_dbms/server.py)를 미니 증권용 스키마로 켠다.

미니 DBMS는 켠 폴더 아래의 data/schema.json을 읽고, 그 옆에 테이블 파일을 쓴다.
그래서 데이터 폴더(기본 data/mini-dbms)를 만들고 demo/dbms_schema.json을 넣은 뒤,
그 폴더로 옮겨 가서 mini_dbms/server.py를 `python3 server.py`로 켠 것과 똑같이 실행한다.

    python -m demo.dbms_server [--port 8020] [--data-dir data/mini-dbms]
"""
import argparse
import os
import runpy
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINI_DBMS_FOLDER = os.path.join(REPO_ROOT, "mini_dbms")
SCHEMA_FILE = os.path.join(REPO_ROOT, "demo", "dbms_schema.json")
DEFAULT_PORT = int(os.environ.get("DEMO_DBMS_PORT", "8020"))
DEFAULT_DATA_DIR = os.environ.get("DEMO_DBMS_DATA_DIR", os.path.join(REPO_ROOT, "data", "mini-dbms"))


def main():
    args = parse_arguments()
    prepare_data_dir(args.data_dir)
    os.chdir(args.data_dir)
    sys.path.insert(0, MINI_DBMS_FOLDER)   # server.py가 engine, minidb를 찾을 수 있게
    sys.argv = ["server.py", "--host", args.host, "--port", str(args.port)]
    runpy.run_path(os.path.join(MINI_DBMS_FOLDER, "server.py"), run_name="__main__")


def prepare_data_dir(data_dir):
    """data_dir/data/schema.json을 미니 증권 스키마로 맞춘다. 이미 있는 테이블 파일은 건드리지 않는다."""
    engine_data = os.path.join(data_dir, "data")
    os.makedirs(engine_data, exist_ok=True)
    shutil.copyfile(SCHEMA_FILE, os.path.join(engine_data, "schema.json"))


def parse_arguments():
    parser = argparse.ArgumentParser(description="미니 증권용 미니 DBMS 서버")
    parser.add_argument("--host", default="127.0.0.1", help="받을 주소 (기본 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="포트 (기본 8020)")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="데이터 폴더 (기본 data/mini-dbms)")
    args = parser.parse_args()
    args.data_dir = os.path.abspath(args.data_dir)
    return args


if __name__ == "__main__":
    main()

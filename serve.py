"""Serve the dashboard and its local SQLite edits on Windows or another Python host."""

import argparse
import json
import socket
import sqlite3
import sys
import threading
import webbrowser
from contextlib import closing, contextmanager
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


APP_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = APP_ROOT / "data" / "capacity-edits.sqlite3"
DATASET_PATH = APP_ROOT / "data" / "capacities.json"
PUBLIC_ROOT = APP_ROOT / "public"
CAPACITY_PATH = "/api/capacities"
SERVER_ID = "global-oleochemicals"
FIRST_YEAR, LAST_YEAR = 2019, 2030
PRODUCTS = ("acid", "alcohol")
DATA_TAG = b'<script type="application/json" data-capacities>'
DATA_SLOT = DATA_TAG + b'{"records":[]}</script>'
STATIC_FILES = {
    "/": ("dashboard.html", "text/html; charset=utf-8"),
    "/dashboard.html": ("dashboard.html", "text/html; charset=utf-8"),
    "/colours.js": ("colours.js", "text/javascript; charset=utf-8"),
    "/panel-sizes.js": ("panel-sizes.js", "text/javascript; charset=utf-8"),
    "/D3-LICENSE.txt": ("D3-LICENSE.txt", "text/plain; charset=utf-8"),
}


@contextmanager
def connect(database):
    with closing(sqlite3.connect(database, timeout=10)) as connection, connection:
        connection.row_factory = sqlite3.Row
        yield connection


def initialize_database(database):
    database.parent.mkdir(parents=True, exist_ok=True)
    with connect(database) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS capacity_overrides (
                record_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                acid REAL,
                alcohol REAL,
                PRIMARY KEY (record_id, year)
            )
        """)


def is_capacity(value):
    return value is None or (
        type(value) in (int, float) and 0 <= value <= sys.float_info.max
    )


def read_dataset(path):
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"records": []}

    if not isinstance(dataset, dict) or not isinstance(dataset.get("records"), list):
        raise ValueError("data/capacities.json requires a records array.")
    if not isinstance(dataset.get("source", ""), str):
        raise ValueError("The capacity source label must be text.")

    sources = dataset.get("locationSources", [])
    if not isinstance(sources, list) or any(
        not isinstance(source, dict)
        or not isinstance(source.get("label"), str)
        or not isinstance(source.get("url"), str)
        or not source["url"].startswith("https://")
        for source in sources
    ):
        raise ValueError("Location sources require a label and HTTPS URL.")

    record_ids = set()
    fields = ("region", "country", "state", "city", "parent", "company")
    for record in dataset["records"]:
        record_id = record.get("id") if isinstance(record, dict) else None
        if type(record_id) is not int or not 0 < record_id < 2**53 or record_id in record_ids:
            raise ValueError("Capacity records require unique positive integer IDs.")
        record_ids.add(record_id)
        if any(not isinstance(record.get(field), str) for field in fields):
            raise ValueError(f"Record {record_id} requires text for its company and location fields.")

        coords = record.get("coords")
        if coords is not None and (
            not isinstance(coords, list) or len(coords) != 2
            or any(type(value) not in (int, float) or not -limit <= value <= limit
                   for value, limit in zip(coords, (180, 90)))
        ):
            raise ValueError(f"Record {record_id} requires coordinates in longitude, latitude order.")

        for product in PRODUCTS:
            values = record.get(product)
            if (not isinstance(values, list) or len(values) != LAST_YEAR - FIRST_YEAR + 1
                    or any(not is_capacity(value) for value in values)):
                raise ValueError(f"Record {record_id} requires annual {product} capacities for {FIRST_YEAR}–{LAST_YEAR}.")
    return dataset


def edit_values(record, record_ids):
    if not isinstance(record, dict):
        raise ValueError("Expected an annual capacity record")

    record_id = record.get("recordId")
    year = record.get("year")
    if type(record_id) is not int or record_id not in record_ids:
        raise ValueError("Invalid capacity record ID")
    if type(year) is not int or not FIRST_YEAR <= year <= LAST_YEAR:
        raise ValueError("Invalid capacity year")

    for product in PRODUCTS:
        if product not in record:
            raise ValueError("Both product capacities are required")
        if not is_capacity(record[product]):
            raise ValueError("Capacity must be a nonnegative number or null")

    return record_id, year, record["acid"], record["alcohol"]


class DashboardServer(ThreadingHTTPServer):
    allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")

    def __init__(self, port, database, dataset_path=DATASET_PATH):
        self.database = database
        dataset = read_dataset(dataset_path)
        self.record_ids = {record["id"] for record in dataset["records"]}
        serialized = json.dumps(dataset, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        self.dataset_payload = DATA_TAG + serialized.replace("<", "\\u003c").encode("utf-8") + b"</script>"
        super().__init__(("127.0.0.1", port), DashboardHandler)
        bound_port = self.server_address[1]
        self.local_hosts = {f"127.0.0.1:{bound_port}", f"localhost:{bound_port}"}

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DashboardHandler(BaseHTTPRequestHandler):
    def respond(self, status, body=b"", content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        if status != HTTPStatus.NO_CONTENT:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def respond_json(self, data):
        self.respond(HTTPStatus.OK, json.dumps(data).encode("utf-8"), "application/json")

    def is_local_request(self):
        if self.headers.get("Host", "").lower() in self.server.local_hosts:
            return True
        self.respond(HTTPStatus.FORBIDDEN)
        return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.is_local_request():
            return
        path = urlsplit(self.path).path
        if path == "/health":
            self.respond_json({"app": SERVER_ID})
        elif path == CAPACITY_PATH:
            with connect(self.server.database) as connection:
                rows = connection.execute("""
                    SELECT record_id AS recordId, year, acid, alcohol
                    FROM capacity_overrides
                    ORDER BY record_id, year
                """).fetchall()
            self.respond_json([dict(row) for row in rows if row["recordId"] in self.server.record_ids])
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            body = (PUBLIC_ROOT / filename).read_bytes()
            if filename == "dashboard.html":
                body = body.replace(DATA_SLOT, self.server.dataset_payload, 1)
            self.respond(HTTPStatus.OK, body, content_type)
        else:
            self.respond(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        if not self.is_local_request():
            return
        if urlsplit(self.path).path != CAPACITY_PATH:
            self.respond(HTTPStatus.NOT_FOUND)
            return
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers['Host'].lower()}":
            self.respond(HTTPStatus.FORBIDDEN)
            return
        if self.headers.get_content_type() != "application/json":
            self.respond(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid request length")
            values = edit_values(json.loads(self.rfile.read(length)), self.server.record_ids)
        except ValueError:
            self.respond(HTTPStatus.BAD_REQUEST)
            return

        with connect(self.server.database) as connection:
            connection.execute("""
                INSERT INTO capacity_overrides (record_id, year, acid, alcohol)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (record_id, year) DO UPDATE SET
                    acid = excluded.acid,
                    alcohol = excluded.alcohol
            """, values)
        self.respond(HTTPStatus.NO_CONTENT)


def dashboard_running(port):
    with closing(HTTPConnection("127.0.0.1", port, timeout=1)) as connection:
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            return response.status == 200 and json.loads(response.read(4096)).get("app") == SERVER_ID
        except (OSError, ValueError, AttributeError):
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=8767, type=int)
    parser.add_argument("--open", dest="open_browser", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    initialize_database(DATABASE_PATH)
    try:
        server = DashboardServer(args.port, DATABASE_PATH)
    except ValueError as error:
        parser.exit(1, f"Could not load the local capacity data. {error}\n")
    except OSError as error:
        if not dashboard_running(args.port):
            parser.exit(1, f"Could not start the dashboard on port {args.port}. {error}\n")
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Dashboard already running at {url}", flush=True)
        if args.open_browser:
            webbrowser.open(url)
        return

    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Global Oleochemicals running at {url}", flush=True)
    print(f"Annual edits are stored in {DATABASE_PATH}", flush=True)
    if args.open_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

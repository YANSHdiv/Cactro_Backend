import os
import sys
import time
import subprocess
import json
import csv
import httpx
from sqlalchemy import create_engine, text

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://event_admin:event_secure_pass_2026@localhost:5433/event_booking_db"
)


def reset_benchmark(capacity: int, mode: str):
    url = f"{API_BASE_URL}/test/reset-benchmark?capacity={capacity}&concurrency_mode={mode}"
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url)
        resp.raise_for_status()
        return resp.json()


def get_db_stats(event_id: int):
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        event_row = conn.execute(
            text("SELECT capacity, available_tickets FROM events WHERE id = :eid"),
            {"eid": event_id}
        ).fetchone()
        
        booking_row = conn.execute(
            text("SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM bookings WHERE event_id = :eid"),
            {"eid": event_id}
        ).fetchone()
        
    return {
        "capacity": event_row[0] if event_row else 0,
        "available_tickets": event_row[1] if event_row else 0,
        "booking_count": booking_row[0] if booking_row else 0,
        "booked_tickets_sum": booking_row[1] if booking_row else 0,
    }


def run_locust_test(users: int, spawn_rate: int, run_time_sec: int, csv_prefix: str, token: str, event_id: int):
    env = os.environ.copy()
    env["BENCHMARK_TOKEN"] = token
    env["TARGET_EVENT_ID"] = str(event_id)

    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "locustfile.py",
        "--headless",
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        f"{run_time_sec}s",
        "--host",
        API_BASE_URL,
        "--csv",
        csv_prefix,
        "--only-summary",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result


def parse_locust_csv(csv_prefix: str):
    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        return {}

    with open(stats_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name") == "Aggregated":
                return {
                    "total_requests": int(row.get("Request Count", 0)),
                    "failure_count": int(row.get("Failure Count", 0)),
                    "median_response_time": float(row.get("Median Response Time", 0)),
                    "avg_response_time": float(row.get("Average Response Time", 0)),
                    "p95_response_time": float(row.get("95%", 0) if "95%" in row else row.get("95%ile", 0)),
                    "max_response_time": float(row.get("Max Response Time", 0)),
                    "rps": float(row.get("Requests/s", 0)),
                }
    return {}


def run_scenario(mode: str, concurrency_levels=[10, 25, 50, 100, 200], capacity=50, duration=10):
    print(f"\n========================================================")
    print(f" RUNNING BENCHMARK SCENARIO: MODE = {mode.upper()}")
    print(f" Event Capacity: {capacity} tickets | Duration per tier: {duration}s")
    print(f"========================================================\n")

    results = []
    os.makedirs("benchmark_results", exist_ok=True)

    for users in concurrency_levels:
        spawn_rate = max(5, users // 2)
        print(f"--> Benchmarking Concurrency: {users} users (spawn rate: {spawn_rate}/s)...")

        # 1. Reset event
        init_data = reset_benchmark(capacity=capacity, mode=mode)
        event_id = init_data["event_id"]
        token = init_data["customer_token"]

        csv_prefix = f"benchmark_results/{mode}_c{users}"

        # 2. Run Locust
        locust_res = run_locust_test(
            users=users,
            spawn_rate=spawn_rate,
            run_time_sec=duration,
            csv_prefix=csv_prefix,
            token=token,
            event_id=event_id,
        )

        # 3. Read DB Stats
        db_stats = get_db_stats(event_id)

        # 4. Parse Locust Stats
        stats = parse_locust_csv(csv_prefix)

        # 5. Determine oversell count
        oversold = max(0, db_stats["booked_tickets_sum"] - capacity)

        result_row = {
            "mode": mode,
            "concurrency": users,
            "duration_sec": duration,
            "event_capacity": capacity,
            "total_requests": stats.get("total_requests", 0),
            "requests_per_sec": stats.get("rps", 0.0),
            "avg_latency_ms": stats.get("avg_response_time", 0.0),
            "p95_latency_ms": stats.get("p95_response_time", 0.0),
            "max_latency_ms": stats.get("max_response_time", 0.0),
            "locust_failures": stats.get("failure_count", 0),
            "booked_tickets": db_stats["booked_tickets_sum"],
            "remaining_tickets": db_stats["available_tickets"],
            "oversold_tickets": oversold,
            "oversold_detected": oversold > 0 or db_stats["available_tickets"] < 0,
        }
        results.append(result_row)
        print(f"    RPS: {result_row['requests_per_sec']:.1f} | Avg Latency: {result_row['avg_latency_ms']:.1f}ms | p95: {result_row['p95_latency_ms']:.1f}ms")
        print(f"    Total Reqs: {result_row['total_requests']} | Booked: {result_row['booked_tickets']}/{capacity} | Oversold: {result_row['oversold_tickets']} tickets")
        time.sleep(1)

    out_file = f"benchmark_results/{mode}_summary.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "naive"
    concurrency_list = [10, 25, 50, 100, 200]
    run_scenario(mode=mode_arg, concurrency_levels=concurrency_list)

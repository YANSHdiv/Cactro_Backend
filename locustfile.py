import os
from locust import HttpUser, task, between, events


class EventBookingUser(HttpUser):
    wait_time = between(0.01, 0.05)  # rapid requests to simulate contention
    event_id = None
    token = None

    def on_start(self):
        # Retrieve target event_id and token from environment or reset endpoint
        self.event_id = int(os.getenv("TARGET_EVENT_ID", "1"))
        self.token = os.getenv("BENCHMARK_TOKEN", "")

        if not self.token:
            # Login as benchmark customer
            login_resp = self.client.post(
                "/auth/login",
                json={"email": "benchmark_customer@example.com", "password": "customerpass123"},
            )
            if login_resp.status_code == 200:
                self.token = login_resp.json().get("access_token")

        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task
    def book_ticket(self):
        payload = {"quantity": 1}
        with self.client.post(
            f"/events/{self.event_id}/book",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/events/[id]/book",
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 409:
                # Capacity exhausted (expected rejection when sold out)
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

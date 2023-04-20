import os
from datetime import datetime, timedelta, timezone

import pytest
import redis
from freezegun import freeze_time
from redis import Redis
from rq import Queue

from autoscale_queue_rq import latency

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")


@pytest.fixture(scope="module")
def redis_connection():
    return Redis.from_url(REDIS_URL)


@pytest.fixture(scope="function")
def clean_redis(redis_connection):
    redis_connection.flushdb()


def test_latency_no_queues():
    with pytest.raises(ValueError, match="At least one queue name must be provided"):
        latency([], REDIS_URL)


def test_latency_invalid_redis_url(redis_connection, clean_redis):
    with pytest.raises(redis.exceptions.ConnectionError):
        latency(["queue"], "redis://not.a.valid.url")


def test_latency_no_jobs(redis_connection, clean_redis):
    queue_name = Queue(connection=redis_connection).name
    measurement = latency([queue_name], REDIS_URL)
    assert measurement == 0


def test_latency_one_job(redis_connection, clean_redis):
    queue_name = Queue(connection=redis_connection).name

    with freeze_time(datetime.now(timezone.utc) - timedelta(seconds=5)):
        Queue(queue_name, connection=redis_connection).enqueue(lambda: None)

    measurement = latency([queue_name], REDIS_URL)
    assert measurement == pytest.approx(5.0, abs=1.0)


def test_latency_multiple_jobs(redis_connection, clean_redis):
    queue = Queue(connection=redis_connection)

    with freeze_time(datetime.now(timezone.utc) - timedelta(seconds=10)):
        print(queue.enqueue(lambda: None))

    with freeze_time(datetime.now(timezone.utc) - timedelta(seconds=5)):
        queue.enqueue(lambda: None)

    measurement = latency([queue.name], REDIS_URL)
    assert measurement == pytest.approx(10.0, abs=1.0)


def test_latency_custom_queue_names(redis_connection, clean_redis):
    queue_1 = Queue(name="queue_1", connection=redis_connection)
    queue_2 = Queue(name="queue_2", connection=redis_connection)

    with freeze_time(datetime.now(timezone.utc) - timedelta(seconds=5)):
        queue_1.enqueue(lambda: None)

    with freeze_time(datetime.now(timezone.utc) - timedelta(seconds=10)):
        queue_2.enqueue(lambda: None)

    measurement = latency([queue_1.name, queue_2.name], REDIS_URL)
    assert measurement == pytest.approx(10, abs=1)

import os
from datetime import datetime, timezone

import redis
from rq import Queue

__version__ = "0.2.0"
__author__ = "Michael R. van Rooijen"
__contact__ = "support@autoscale.app"
__homepage__ = "https://autoscale.app"
__docformat__ = "restructuredtext"
__keywords__ = "python queue worker autoscale rq"


def job_queue_time(queue_names, redis_url=None):
    """
    Calculate the maximum job queue time in seconds of the given RQ queues.

    This function calculates the job queue time of the provided queues by measuring the time
    elapsed since the oldest job was enqueued in each queue. The maximum job queue time among
    all the queues is returned.

    Args:
        queue_names (list[str]): A list of RQ queue names for which to calculate job queue time.
        redis_url (str, optional): The URL of the Redis server used by RQ. Defaults to None,
            in which case the value will be read from the REDIS_URL environment variable.

    Raises:
        ValueError: If no queue names are provided or if a Redis URL is not provided and
            not found in the environment variables.

        redis.exceptions.ConnectionError: If the provided Redis URL is not valid.

    Returns:
        float: The maximum job queue time in seconds among all the given queues. If a queue has no
            jobs, its job queue time is considered as 0.
    """
    if not queue_names:
        raise ValueError("At least one queue name must be provided")

    if not redis_url:
        redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        raise ValueError("Redis URL must be provided")

    redis_instance = redis.Redis.from_url(redis_url)
    queues = [Queue(qname, connection=redis_instance) for qname in queue_names]

    try:
        latencies = []

        pipeline = redis_instance.pipeline()
        for queue in queues:
            pipeline.lindex(queue.key, 0)
        job_ids_in_bytes = pipeline.execute()

        pipeline = redis_instance.pipeline()
        for job_id_in_bytes in job_ids_in_bytes:
            if not job_id_in_bytes:
                latencies.append(0)
            else:
                job_id = job_id_in_bytes.decode("utf-8")
                pipeline.hget("rq:job:" + job_id, "enqueued_at")
        enqueued_at_timestamps = pipeline.execute()

        now = datetime.now(timezone.utc)

        for enqueued_at_timestamp in enqueued_at_timestamps:
            if enqueued_at_timestamp is None:
                continue
            enqueued_at = datetime.fromisoformat(
                enqueued_at_timestamp.decode("utf-8").replace("Z", "+00:00")
            ).replace(tzinfo=timezone.utc)
            latencies.append((now - enqueued_at).total_seconds())

        return max(latencies)
    finally:
        redis_instance.connection_pool.disconnect()

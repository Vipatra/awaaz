# monitoring/metrics.py

import boto3
import time
import asyncio

from core.logging import log

try:
    import pynvml
except ImportError:
    pynvml = None
    log.error("pynvml not installed. GPU metrics will not be available.")


class CloudWatchMetrics:
    def __init__(self, namespace='AwaazService'):
        self.cloudwatch = boto3.client(
            'cloudwatch',
            region_name='ap-south-1',
        )
        self.namespace = namespace

    def publish_metric(self, metric_name, value, unit='None', dimensions=None):
        dimensions = dimensions or []
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Dimensions': dimensions,
                        'Timestamp': time.time(),
                        'Value': value,
                        'Unit': unit,
                    },
                ]
            )
        except Exception as e:
            log.error(f"Error publishing metric {metric_name}: {e}")

    def get_gpu_utilization(self):
        if pynvml is None:
            return 0
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            # Report used GPU memory in Megabytes
            utilization = mem_info.used / (1024 * 1024)
            pynvml.nvmlShutdown()
            return utilization
        except Exception as e:
            log.error(f"Error getting GPU utilization: {e}")
            return 0


async def publish_metrics_loop(server, interval=60):
    """
    Periodically collects and publishes metrics to CloudWatch.

    - server: instance of the Server class.
    - interval: how often (in seconds) to publish metrics.
    """
    cw = CloudWatchMetrics()
    while True:
        # Get GPU utilization (in MB)
        gpu_usage = cw.get_gpu_utilization()
        # Get active WebSocket connections from the Server instance
        active_connections = len(server.connected_clients)

        # Calculate total audio duration processed (in seconds)
        # (Assumes each client maintains total_samples and sampling_rate)
        total_audio_duration = 0
        for client in server.connected_clients.values():
            total_audio_duration += client.total_samples / client.sampling_rate

        # Publish each metric
        cw.publish_metric("GPUUtilizationMB", gpu_usage, unit="Megabytes")
        cw.publish_metric("ActiveWebSocketConnections", active_connections,
                          unit="Count")
        cw.publish_metric("AudioDurationProcessed", total_audio_duration,
                          unit="Seconds")

        log.info(
            f"Published metrics: GPU {gpu_usage:.2f}MB, "
            f"active connections {active_connections}, "
            f"audio duration {total_audio_duration:.2f} sec"
        )
        await asyncio.sleep(interval)

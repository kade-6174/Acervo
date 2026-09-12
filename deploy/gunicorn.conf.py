import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
accesslog = "-"
errorlog = "-"
capture_output = True
forwarded_allow_ips = "*"
control_socket_disable = True

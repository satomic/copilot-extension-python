from flask import Flask, jsonify, request
from asgiref.wsgi import WsgiToAsgi
from models import Models
import json
import sys, os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


import utils.github_utils as github_utils
from utils.log_utils import *


logger = configure_logger(with_date_folder=False)
logger.info('-----------------Starting-----------------')


flask_app = Flask(__name__)
app = WsgiToAsgi(flask_app)

@flask_app.post("/")
def stream():
    github_handler = github_utils.GitHubHandler(request)
    if not github_handler.verify_github_signature():
        return jsonify({"error": "Request must be from GitHub"}), 403

    user_login = github_handler.get_user_login()
    logger.info(f"User login: {user_login}")

    x_github_token = request.headers["x-github-token"]
    payload = request.get_json()
    # logger.info(json.dumps(payload, indent=4, ensure_ascii=False))

    models = Models(x_github_token, payload)
    
    # Check if the last message indicates a command execution request
    if payload.get("messages") and len(payload["messages"]) > 0:
        last_message = payload["messages"][-1]
        if last_message.get("role") == "user" and last_message.get("content", "").strip().startswith("cmd:"):
            # Remove the "cmd: " prefix from the message
            payload["messages"][-1]["content"] = last_message["content"].replace("cmd:", "", 1).strip()
            logger.info(f"cmd: {payload['messages'][-1]['content']}")
            return models.execute_command(), {"Content-Type": "text/event-stream"}

        if last_message.get("role") == "user" and last_message.get("content", "").strip().startswith("ollama:"):
            # Remove the "ollama: " prefix from the message
            payload["messages"][-1]["content"] = last_message["content"].replace("ollama:", "", 1).strip()
            logger.info(f"ollama: {payload['messages'][-1]['content']}")
            return models.ollama(), {"Content-Type": "text/event-stream"}

        logger.info(f"copilot: {payload['messages'][-1]['content']}")
        return models.copilot(), {"Content-Type": "text/event-stream"}

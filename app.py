from flask import Flask, jsonify, request
from asgiref.wsgi import WsgiToAsgi
from models import Models
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
    models = Models(x_github_token, payload)
    
    if payload.get("messages") and payload["messages"]:
        last_message = payload["messages"][-1]
        content = last_message.get("content", "").strip()
        
        if last_message.get("role") == "user":
            # Map prefixes to model functions
            prefix_map = {
                "cmd:": models.execute_command,
                "ollama:": models.ollama,
                "qwen:": models.qwen
            }
            
            for prefix, handler in prefix_map.items():
                if content.startswith(prefix):
                    payload["messages"][-1]["content"] = content[len(prefix):].strip()
                    model_name = prefix[:-1]
                    logger.info(f"{model_name}: {payload['messages'][-1]['content']}")
                    return handler(), {"Content-Type": "text/event-stream"}
            
            # Default to copilot
            logger.info(f"copilot: {content}")
            return models.copilot(), {"Content-Type": "text/event-stream"}

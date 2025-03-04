import httpx
import json
import subprocess
import config


class Models():

    def __init__(self, x_github_token, payload):
        self.x_github_token = x_github_token
        self.messages = payload["messages"]

    def copilot(self):
        self.messages.insert(
            0,
            {
                "role": "system",
                "content": "你是一个可爱的小猫🐱喜欢卖萌，每次回答都用emoji结为，例如💗",
            },
        )
        headers = {
            "Authorization": f"Bearer {self.x_github_token}",
            "Content-Type": "application/json",
        }
        data = {
            "messages": self.messages, 
            "stream": True
        }
        with httpx.stream(
            "POST",
            "https://api.githubcopilot.com/chat/completions",
            headers=headers,
            json=data,
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    yield f"{chunk}\n\n"

    def ollama(self):
        data = {
            "model": "llama3.2",
            "messages": self.messages, 
            "stream": True
        }
        with httpx.stream(
            "POST",
            "http://localhost:11434/api/chat",
            json=data,
            timeout=120.0,
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    try:
                        # Parse the JSON chunk
                        json_chunk = json.loads(chunk)
                        content = json_chunk.get("message", {}).get("content", "")
                        print(content)
                        done = json_chunk.get("done", False)
                        
                        # Format in OpenAI compatible format with 'choices' field
                        if done:
                            # Final message when stream is complete
                            data_dict = {
                                "choices": [{
                                    "finish_reason": "stop",
                                    "index": 0,
                                    "delta": {}
                                }]
                            }
                        else:
                            # Stream content format
                            data_dict = {
                                "choices": [{
                                    "delta": {"content": content},
                                    "index": 0
                                }]
                            }
                        
                        # Convert to JSON and yield in SSE format
                        yield f"data: {json.dumps(data_dict)}\n\n"
                    except json.JSONDecodeError:
                        # In case of malformed JSON
                        continue

    def execute_command(self):
        # Get the last prompt from messages list
        if not self.messages or len(self.messages) == 0:
            error_msg = "No messages found."
            yield self._format_response(error_msg, is_error=True)
            return
            
        last_message = self.messages[-1]
        if last_message.get("role") != "user":
            error_msg = "Last message is not from user."
            yield self._format_response(error_msg, is_error=True)
            return
        
        # Get the command to execute
        command = last_message.get("content", "").strip()
        
        # Begin response with command echo and opening code block
        yield self._format_response(f"Executing command: {command}\n\n```\n")
        
        try:
            # Execute the command through cmd.exe
            process = subprocess.Popen(
                ["cmd.exe", "/c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream stdout in real-time
            for line in process.stdout:
                yield self._format_response(line)
                
            # Get any remaining stderr
            stderr = process.stderr.read()
            if stderr:
                yield self._format_response(f"\nErrors:\n{stderr}")
                
            # Wait for process to complete
            process.wait()
            
            # Send completion message and close code block
            yield self._format_response(f"\nCommand completed with exit code: {process.returncode}\n")
            
            # Send stop message
            yield self._format_stop_response()
            
        except Exception as e:
            # Close the code block even on error
            error_msg = f"Error executing command: {str(e)}\n```"
            yield self._format_response(error_msg, is_error=True)
            yield self._format_stop_response()
    
    def _format_response(self, content, is_error=False):
        """Format response in the expected structure for Copilot"""
        if is_error:
            content = f"ERROR: {content}"
            
        data_dict = {
            "choices": [{
                "delta": {"content": content},
                "index": 0
            }]
        }
        return f"data: {json.dumps(data_dict)}\n\n"
    
    def _format_stop_response(self):
        """Format the final stop message"""
        data_dict = {
            "choices": [{
                "finish_reason": "stop",
                "index": 0,
                "delta": {}
            }]
        }
        return f"data: {json.dumps(data_dict)}\n\n"

    def qwen(self):
        headers = {
            "Authorization": f"Bearer {config.QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "qwen-plus",
            "messages": self.messages, 
            "stream": True
        }
        with httpx.stream(
            "POST",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers=headers,
            json=data,
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    yield f"{chunk}\n\n"


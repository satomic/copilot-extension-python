import httpx
import json
import subprocess
import config


class Actions():

    def __init__(self, x_github_token):
        self.x_github_token = x_github_token
        self.messages = []

    def copilot(self, messages):
        self.messages = messages
        self.messages.insert(
            0,
            {
                "role": "system",
                "content": config.COPILOT_PERSONALIZATION,
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
            config.COPILOT_API_URL,
            headers=headers,
            json=data,
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    yield f"{chunk}\n\n"

    def ollama(self, messages):
        self.messages = messages
        data = {
            "model": config.OLLAMA_MODEL,
            "messages": self.messages, 
            "stream": True
        }
        with httpx.stream(
            "POST",
            config.OLLAMA_API_URL,
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

    def execute_command(self, messages):
        self.messages = messages
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
                [config.CMD_EXECUTOR, '-c', command] if config.CMD_EXECUTOR != 'cmd.exe' else [config.CMD_EXECUTOR, '/c', command],
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

    # https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api#d059267ec7867
    def qwen(self, messages):
        self.messages = messages
        headers = {
            "Authorization": f"Bearer {config.QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": config.QWEN_MODEL,
            "messages": self.messages, 
            "stream": True
        }
        try:
            with httpx.stream(
                "POST",
                config.QWEN_API_URL,
                headers=headers,
                json=data,
            ) as response:
                if response.status_code == 401:
                    error_msg = "Qwen API request failed: Unauthorized 401, please check whether API_KEY is valid."
                    yield self._format_response(error_msg, is_error=True)
                    yield self._format_stop_response()
                    return

                response.raise_for_status()

                for chunk in response.iter_lines():
                    if chunk:
                        yield f"{chunk}\n\n"

        except httpx.HTTPError as e:
            error_msg = f"Qwen API request exception: {str(e)}"
            yield self._format_response(error_msg, is_error=True)
            yield self._format_stop_response()

    # DeepSeek API implementation
    # https://api-docs.deepseek.com/
    def deepseek(self, messages):
        self.messages = messages
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": config.DEEPSEEK_MODEL,
            "messages": self.messages, 
            "stream": True
        }
        try:
            with httpx.stream(
                "POST",
                config.DEEPSEEK_API_URL,
                headers=headers,
                json=data,
                timeout=120.0,  # Increasing timeout to avoid timeout issues
            ) as response:
                if response.status_code == 401:
                    error_msg = "DeepSeek API request failed: Unauthorized 401, please check whether API_KEY is valid."
                    yield self._format_response(error_msg, is_error=True)
                    yield self._format_stop_response()
                    return

                response.raise_for_status()

                for chunk in response.iter_lines():
                    if chunk:
                        # Process chunk as string (no need to decode)
                        chunk_str = chunk
                        
                        if chunk_str == "data: [DONE]":
                            # End of stream marker, no action needed as we're already yielding stop response
                            continue
                        
                        # Remove the 'data: ' prefix if present
                        if chunk_str.startswith("data: "):
                            chunk_str = chunk_str[6:]
                        
                        try:
                            # Parse the JSON chunk
                            json_chunk = json.loads(chunk_str)
                            
                            # Extract content from the choices array
                            if "choices" in json_chunk and len(json_chunk["choices"]) > 0:
                                choice = json_chunk["choices"][0]
                                
                                # Check for finish reason
                                if choice.get("finish_reason") == "stop":
                                    yield self._format_stop_response()
                                    continue
                                
                                # Extract content from delta
                                if "delta" in choice and "content" in choice["delta"]:
                                    content = choice["delta"]["content"]
                                    
                                    # Format in OpenAI compatible format
                                    data_dict = {
                                        "choices": [{
                                            "delta": {"content": content},
                                            "index": 0
                                        }]
                                    }
                                    
                                    # Convert to JSON and yield in SSE format
                                    yield f"data: {json.dumps(data_dict)}\n\n"
                        except json.JSONDecodeError as e:
                            # In case of malformed JSON
                            print(f"JSON decoding error: {e}, chunk: {chunk_str}")
                            continue

        except httpx.HTTPError as e:
            error_msg = f"DeepSeek API request exception: {str(e)}"
            yield self._format_response(error_msg, is_error=True)
            yield self._format_stop_response()

    def help(self, messages=None):
        """Returns markdown-formatted help information about available commands"""
        help_content = """
# Copilot Extensions All in One - Help Guide

This extension provides enhanced capabilities beyond standard GitHub Copilot. Below are the available commands and their usage:

## Available Commands

| Command Prefix | Description |
|---------------|-------------|
| `(no prefix)` | Default GitHub Copilot interaction |
| `help` | Display this help information |
| `cmd:` | Execute operating system commands |
| `ollama:` | Interact with local Ollama models |
| `qwen:` | Use Alibaba Cloud's Qwen AI model |
| `deepseek:` | Use DeepSeek's AI model |

## Examples

### Default Copilot Mode
```
How can I implement a simple HTTP server in Python?
```

### Command Execution
```
cmd: dir
cmd: python --version
cmd: git status
```

### Ollama Interaction
```
ollama: Please explain the basic principles of quantum computing
```

### Qwen Interaction
```
qwen: Write a poem about artificial intelligence
```

### DeepSeek Interaction
```
deepseek: Create a detailed outline for a research paper on climate change
```

## Additional Features

- **File References**: When you reference files or selected code in your message, this content is included in the request for more targeted responses.
- **Response Streaming**: All models support streaming responses, showing AI-generated content in real-time.

For more information, please refer to the [README.md](https://github.com/satomic/copilot-extension-all-in-one?tab=readme-ov-file#table-of-contents) file.
"""
        
        # Format the help content for streaming
        yield self._format_response(help_content)
        yield self._format_stop_response()


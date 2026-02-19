import json
import os
from pathlib import Path


def main():
    # Define the target config file path
    config_path = Path(
        os.path.expanduser("~/Library/Application Support/OpenAI/ChatGPT/mcp.json")
    )

    # Define the new server config
    new_server_config = {
        "command": "/opt/homebrew/bin/uv",
        "args": [
            "--directory",
            "/Users/adpena/PycharmProjects/teadata-mcp",
            "run",
            "teadata-mcp",
        ],
    }

    # Initialize data structure
    data = {"mcpServers": {}}

    # Load existing config if it exists
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    # Ensure mcpServers key exists
                    if "mcpServers" not in data:
                        data["mcpServers"] = {}
        except json.JSONDecodeError:
            print(
                f"Warning: {config_path} contained invalid JSON. Overwriting with new config."
            )
        except Exception as e:
            print(f"Error reading existing file: {e}")
            return

    # Add or update the teadata-mcp configuration
    data["mcpServers"]["teadata-mcp"] = new_server_config

    # Ensure the directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the updated config back to file
    try:
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Successfully updated configuration at: {config_path}")
        print("Configuration added:")
        print(json.dumps(new_server_config, indent=2))
    except Exception as e:
        print(f"Error writing to file: {e}")


if __name__ == "__main__":
    main()

import json
import sys
from pathlib import Path

def main():
    # 1. Locate the ChatGPT config file
    config_dir = Path.home() / "Library" / "Application Support" / "com.openai.chat"
    config_path = config_dir / "config.json"
    
    if not config_dir.exists():
        print(f"❌ Configuration directory not found: {config_dir}")
        print("   Please ensure the ChatGPT macOS application is installed and has been run at least once.")
        sys.exit(1)

    # 2. Load existing config or initialize new
    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print("⚠️  Warning: Existing config.json was malformed. Starting with a fresh configuration.")
            backup_path = config_path.with_suffix(".json.bak")
            config_path.rename(backup_path)
            print(f"   Backed up malformed config to: {backup_path}")

    # 3. Prepare the server configuration
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Get the absolute path to the Python interpreter (should be the one in .venv)
    python_path = sys.executable
    
    # Sanity check: Ensure we aren't using the system python by mistake
    if "teadata-mcp" not in python_path and ".venv" not in python_path:
        print("⚠️  Warning: It looks like you might not be running this with the project's virtual environment.")
        print(f"   Current Python: {python_path}")
        print("   Recommended: Run this script using `uv run python setup_chatgpt.py`")
        confirm = input("   Continue anyway? [y/N] ")
        if confirm.lower() not in ("y", "yes"):
            sys.exit(1)

    print(f"ℹ️  Configuring 'teadata' MCP server...")
    print(f"   Interpreter: {python_path}")
    
    # We intentionally do NOT set TEADATA_SNAPSHOT env var here, 
    # relying on the server's built-in search functionality as requested.
    server_config = {
        "command": python_path,
        "args": ["-m", "teadata_mcp"],
        "env": {}
    }

    # 4. Write changes
    config["mcpServers"]["teadata"] = server_config

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"✅ Successfully updated: {config_path}")
        print("\n👉 Next Step: Restart the ChatGPT app for the changes to take effect.")
    except PermissionError:
        print(f"❌ Error: Permission denied writing to {config_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()

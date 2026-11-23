"""Configure and launch agent to AgentCore Runtime."""
import subprocess
import sys

AC = r"C:\Users\RavindraYadav\AppData\Roaming\Python\Python311\Scripts\agentcore.exe"

# Check bedrock_agentcore is importable
try:
    from bedrock_agentcore import BedrockAgentCoreApp
    print("bedrock_agentcore: OK")
except ImportError:
    print("bedrock_agentcore: NOT FOUND — installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "bedrock-agentcore"], check=True)

# Verify main.py has the app
try:
    from main import agentcore_app
    if agentcore_app is not None:
        print(f"main.py agentcore_app: OK ({type(agentcore_app).__name__})")
    else:
        print("main.py agentcore_app: None (bedrock_agentcore import failed in main.py)")
except Exception as e:
    print(f"main.py import error: {e}")

# Configure
print("\n--- Configure ---")
result = subprocess.run([AC, "configure", "--entrypoint", "main.py", "--non-interactive"], capture_output=True, text=True)
print(f"stdout: {result.stdout[:300]}")
print(f"stderr: {result.stderr[:300]}")
print(f"returncode: {result.returncode}")

# Launch
print("\n--- Launch ---")
result = subprocess.run([AC, "launch"], capture_output=True, text=True)
print(f"stdout: {result.stdout[:500]}")
print(f"stderr: {result.stderr[:500]}")
print(f"returncode: {result.returncode}")

# Status
print("\n--- Status ---")
result = subprocess.run([AC, "status"], capture_output=True, text=True)
print(f"stdout: {result.stdout[:500]}")
print(f"stderr: {result.stderr[:500]}")
print(f"returncode: {result.returncode}")

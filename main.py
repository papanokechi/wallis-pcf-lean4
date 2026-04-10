"""SIARC v5 local entrypoint.

Run:
    c:/Users/shkub/OneDrive/Documents/archive/admin/VSCode/claude-chat/.venv/Scripts/python.exe main.py

This starts the local Flask backend and serves:
    http://127.0.0.1:5050/mission-control-v5
"""

from siarc_engine import _build_app, PAPER_REGISTRY, HAS_MPMATH, HAS_API

app = _build_app()

if __name__ == "__main__":
    if app is None:
        raise SystemExit("Flask dependencies are required. Install flask and flask-cors in the project environment.")

    print("SIARC v5 entrypoint starting on http://127.0.0.1:5050/mission-control-v5")
    print(f"  Papers loaded: {len(PAPER_REGISTRY)}")
    print(f"  mpmath: {HAS_MPMATH}   Anthropic API: {HAS_API}")
    app.run(host="0.0.0.0", port=5050, debug=False)

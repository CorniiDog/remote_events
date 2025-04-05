"""
Main Example Script for RemoteFunctions

This script demonstrates remote function execution over HTTP using the RemoteFunctions class.
It operates in two modes:
    1. Server mode: Registers functions and starts a Flask server to handle remote calls.
    2. Client mode: Connects to the server, retrieves available functions, and invokes them remotely.

All communications are serialized with pickle for reliable data exchange.

Usage:
    To run as a server:
        python main.py server
    To run as a client:
        python main.py client

Note: Ensure the server is running before starting the client.
"""

from remote_functions import RemoteFunctions
import sys
from typing import Any

# Initialize RemoteFunctions with password authentication.
rf = RemoteFunctions(password="Whoop!-")

@rf.as_remote()
def a(b: Any) -> Any:
    """Return the input value."""
    return b

@rf.as_remote()
def add(x: float | int, y: float | int) -> float | int:
    """Return the sum of x and y."""
    return x + y

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        # Start the server (blocking call) on 0.0.0.0:5000.
        rf.start_server(host="0.0.0.0", port=5000)

    elif len(sys.argv) > 1 and sys.argv[1] == "client":
        # Connect to the server running on localhost:5000.
        rf.connect_to_server("localhost", 5000)

        print("Invoking function 'a' with argument 'Hello World!'")
        result = a("Hello World!")
        print("Result:", result)

        print("Invoking function 'add' with arguments 1 and 3")
        result = add(1, 3)
        print("Result:", result)
    else:
        print("Usage: python main.py [server|client]")

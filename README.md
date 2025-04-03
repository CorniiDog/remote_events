# Connor's Remote Events (RE)

Connor's Remote Events (RE) is a simple library that allows the end-user to call python
functions from another server. This is highly powerful if you are coding an application
that offloads processes to another server.

## Example main.py

In two terminals:
1. First terminal, run the server with `python main.py server`

2. Second terminal, run the client with `python main.py client`

```py
####################################################################################
#
# About: A top-down view of what is going on
#
####################################################################################
"""
This example script demonstrates how to use the RemoteFunctions class to perform remote function
execution over HTTP. It operates in two modes:
    1. Server mode: Registers functions and starts a Flask server that listens for remote calls.
    2. Client mode: Connects to the remote server, retrieves the available function names, and
       invokes remote functions by sending their arguments as pickled data.
All data exchanges between the client and server are serialized using pickle to ensure reliable communication.
"""

####################################################################################
#
# How To Run
#
####################################################################################
"""
To run the script as a server:
    python main.py server
This command starts the Flask server on 0.0.0.0:5000 and registers example functions for remote invocation.

To run the script as a client:
    python main.py client
Make sure the server is running before executing the client. The client connects to the server (assumed
to be running on localhost:5000), retrieves the list of available functions, and then calls some of them,
printing the results.
"""

from remote_functions import RemoteFunctions
import sys

if __name__ == "__main__":

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        rf = RemoteFunctions()

        # Example functions to be registered on the server.
        def a(b):
            """Return the input value."""
            return b

        def add(x, y):
            """Return the sum of x and y."""
            return x + y

        # Add functions to the registry.
        rf.add_function(a)
        rf.add_function(add)

        # Start the server (blocking call).
        rf.start_server(host="0.0.0.0", port=5000)

    elif len(sys.argv) > 1 and sys.argv[1] == "client":
        rf = RemoteFunctions()

        # Run as client. Assumes server is running on localhost:5000.
        rf.connect_to_server("localhost", 5000)
        try:
            funcs = rf.get_functions()
            print("Remote functions available:", funcs)
            result_add = rf.call_remote_function("add", 10, 20)
            print("Result of add(10, 20):", result_add)
            result_a = rf.call_remote_function("a", "Hello, Remote!")
            print("Result of a('Hello, Remote!'):", result_a)
        except Exception as e:
            print("An error occurred:", e)
    else:
        print("Usage: python main.py [server|client]")
```


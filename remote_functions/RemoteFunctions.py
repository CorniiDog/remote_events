"""
RemoteFunctions Module

This module defines the RemoteFunctions class which facilitates remote function execution over HTTP.
It allows registration of functions on a server and remote invocation from a client using a Flask-based
API for serving and the requests module for client operations. All communications between client and server
are serialized using pickle, rather than JSON, to ensure greater reliability.

Class:
    RemoteFunctions:
        A class to register, list, and remotely execute functions.

Usage Example:
    # As a server:
    rf = RemoteFunctions()
    rf.add_function(my_function)
    rf.start_server(host="0.0.0.0", port=5000)

    # As a client:
    rf = RemoteFunctions()
    rf.connect_to_server("localhost", 5000)
    functions = rf.get_functions()
    result = rf.call_remote_function("my_function", arg1, arg2)
"""

import pickle
from flask import Flask, request, Response
import requests
from typing import List, Callable, Any
import hashlib
import inspect

def _generate_hash_from_data(data: Any) -> str:
    pickled_data = pickle.dumps(data)
    return hashlib.sha256(pickled_data).hexdigest()

def pack_message(data) -> bytes:
    """
    Package a payload with its hash.
    
    The message is a dictionary containing:
      - 'payload': the actual data.
      - 'hash': the SHA-256 hash computed from the pickled payload.
    """
    message = {
        "payload": data,
        "hash": _generate_hash_from_data(data)
    }
    return pickle.dumps(message)

def unpack_message(message_bytes: bytes):
    """
    Unpack a message and verify its hash.
    
    Raises a ValueError if the structure is invalid or the hash does not match.
    """
    try:
        message = pickle.loads(message_bytes)
        if not isinstance(message, dict) or "payload" not in message or "hash" not in message:
            raise ValueError("Invalid message structure: missing payload or hash")
        payload = message["payload"]
        received_hash = message["hash"]
        if _generate_hash_from_data(payload) != received_hash:
            raise ValueError("Hash verification failed")
        return payload
    except Exception as e:
        raise ValueError(f"Invalid message: {str(e)}")

class RemoteFunctions:
    """
    A class to facilitate remote function registration, listing, and invocation via HTTP.

    This class can be used as both a server and a client. On the server side, functions are registered
    and exposed through HTTP endpoints. On the client side, the class connects to a remote server, lists
    available functions, and calls remote functions with the provided arguments. All data exchanged between
    the client and server is serialized using pickle.

    Attributes:
        functions (dict): Stores registered functions with their __name__ as the key.
        server_url (str): URL of the remote server (used on the client side).
        app (Flask): Flask application instance for serving remote function calls.
    """

    def __init__(self):
        """
        Initialize a RemoteFunctions instance.

        Attributes initialized:
            functions (dict): Empty dictionary to store registered functions.
            server_url (str): None, to be set when connecting as a client.
            app (Flask): None, will be initialized when starting the server.
        """
        self.functions = {}
        self.server_url = None
        self.app = None

    def add_function(self, func: Callable):
        """
        Add a function to the local function registry using its __name__.

        Parameters:
            func (Callable): The function to register for remote invocation.

        Returns:
            None
        """
        self.functions[func.__name__] = func

    def add_functions(self, funcs: List[Callable]):
        """
        Add a list of functions to the local function registry using its __name__.

        Parameters:
            func (List[Callable]): The function to register for remote invocation.

        Returns:
            None
        """
        for func in funcs:
            self.add_function(func)

    def start_server(self, host="0.0.0.0", port=5000):
        """
        Start the Flask server to serve registered functions.

        This method initializes a Flask application with endpoints:
            - GET /functions: Returns a pickled list of registered function names.
            - POST /call: Executes a function call based on a pickled payload and returns a pickled result.

        Parameters:
            host (str): The hostname or IP address for the server to bind to. Defaults to "0.0.0.0".
            port (int): The port number for the server to listen on. Defaults to 5000.

        Returns:
            None
        """
        self.app = Flask(__name__)
        rf = self  # capture self in the route closures

        @self.app.route("/ping", methods=["GET"])
        def ping_route():
            # Simple ping endpoint to verify server availability.
            return Response(pack_message("pong"), mimetype='application/octet-stream')

        @self.app.route("/functions", methods=["GET"])
        def list_functions():
            """
            Retrieve the list of registered function names.

            Returns:
                A pickled response containing a list of function names.
            """
            try:
                function_list = []
                for key in rf.functions.keys():
                    func_data = [key]
                    sig = inspect.signature(rf.functions[key])
                    for param_name, param in sig.parameters.items():
                        combined_details = f"{param_name}: {param.annotation} = {param.default}"
                        func_data.append(combined_details)
                    function_list.append(func_data)


                payload = function_list
                response_message = pack_message(payload)
                return Response(response_message, mimetype='application/octet-stream')
            except Exception as e:
                error_resp = pack_message({"error": "Server error: " + str(e)})
                return Response(error_resp, status=500, mimetype='application/octet-stream')

        @self.app.route("/call", methods=["POST"])
        def call_function():
            """
            Execute a registered function based on the provided pickled payload.

            Expects a pickled payload with:
                - function (str): Name of the function to call.
                - args (list): Positional arguments for the function.
                - kwargs (dict): Keyword arguments for the function.

            Returns:
                A binary response with the pickled result of the function call, or a pickled error message.
            """
            # Unpack and verify the incoming message.
            try:
                data = unpack_message(request.data)
            except Exception as e:
                error_resp = pack_message({"error": "Server error: " + str(e)})
                return Response(error_resp, status=400, mimetype='application/octet-stream')

            func_name = data.get("function")
            args = data.get("args", [])
            kwargs = data.get("kwargs", {})

            if func_name not in rf.functions:
                error_resp = pack_message({"error": f"Function '{func_name}' not found"})
                return Response(error_resp, status=404, mimetype='application/octet-stream')

            try:
                result = rf.functions[func_name](*args, **kwargs)
            except Exception as e:
                error_resp = pack_message({"error": "Server error: " + str(e)})
                return Response(error_resp, status=500, mimetype='application/octet-stream')

            response_message = pack_message(result)
            return Response(response_message, mimetype='application/octet-stream')

        print(f"Starting server at http://{host}:{port} ...")
        self.app.run(host=host, port=port, threaded=True)

    def connect_to_server(self, address, port) -> bool:
        """
        Set the remote server address for client operations.

        Parameters:
            address (str): The IP address or hostname of the remote server.
            port (int): The port number on which the remote server is listening.

        Returns:
            None
        """
        self.server_url = f"http://{address}:{port}"

        # Ping the server with default timeout to ensure it is reachable.
        self.ping()

    def ping(self, timeout_seconds: float = 5.0):
        """
        Ping the remote server to check connectivity.

        Parameters:
            timeout_seconds (float): The timeout for the ping request in seconds.

        Returns:
            True if the server responds with "pong", raises an Exception otherwise.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
        try:
            response = requests.get(f"{self.server_url}/ping", timeout=timeout_seconds)
            if response.status_code == 200:
                payload = unpack_message(response.content)
                if payload == "pong":
                    return True
                else:
                    raise Exception("Unexpected ping response")
            else:
                raise Exception(f"Ping failed: status {response.status_code}")
        except requests.Timeout:
            raise Exception("Ping timed out")
        except Exception as e:
            raise Exception("Ping error: " + str(e))

    def get_functions(self):
        """
        Retrieve a list of available remote function names from the server.

        Sends a GET request to the remote server's /functions endpoint.

        Returns:
            list: A list of function names registered on the remote server.

        Raises:
            ValueError: If the server URL has not been set.
            Exception: If the HTTP request fails.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
        response = requests.get(f"{self.server_url}/functions")
        if response.status_code == 200:
            try:
                return unpack_message(response.content)
            except Exception as e:
                raise Exception("Client error: " + str(e))
        else:
            raise Exception(f"Error retrieving functions: {response.status_code}, {response.text}")

    def call_remote_function(self, func_name, *args, **kwargs):
        """
        Call a remote function on the server and return its unpickled result.

        Sends a POST request to the remote server's /call endpoint with a pickled payload
        specifying the function name, positional arguments, and keyword arguments.

        Parameters:
            func_name (str): The name of the remote function to call.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The result of the remote function call (after unpickling the response).

        Raises:
            ValueError: If the server URL has not been set.
            Exception: If the HTTP request fails.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
        payload = {
            "function": func_name,
            "args": args,
            "kwargs": kwargs
        }
        packaged_payload = pack_message(payload)
        headers = {'Content-Type': 'application/octet-stream'}
        response = requests.post(f"{self.server_url}/call", data=packaged_payload, headers=headers)
        if response.status_code == 200:
            try:
                return unpack_message(response.content)
            except Exception as e:
                raise Exception("Client error: " + str(e))
        else:
            raise Exception(f"Error calling remote function: {response.status_code}, {response.text}")

"""
RemoteFunctions Module
----------------------

This module implements a framework for executing functions remotely over HTTP. It leverages a Flask-based
server to register and expose functions, while clients use the requests library to invoke these functions
remotely. All data exchanged between client and server is serialized with pickle, ensuring robust and
reliable communication.

Key Features:
    • Function Registration: Easily register functions to be invoked remotely.
    • Remote Invocation: Call functions on a remote server using positional and keyword arguments.
    • Data Integrity: Each message is packed with a SHA-256 hash to verify its integrity.
    • Optional Password Authentication:
          - Supply a password during initialization, which is hashed using SHA-256.
          - The hashed password is automatically included in every remote call.
          - The server validates the provided hashed password before processing requests.

Usage Example:
    # Server Mode:
    from remote_functions import RemoteFunctions

    rf = RemoteFunctions(password="my_secret")
    
    @rf.as_remote()
    def my_function(x, y):
        return x + y

    # Start the Flask server to listen on all interfaces at port 5000.
    rf.start_server(host="0.0.0.0", port=5000)


    # Client Mode:
    from remote_functions import RemoteFunctions

    rf = RemoteFunctions(password="my_secret")
    rf.connect_to_server("localhost", 5000)

    # Option 1: Direct remote invocation.
    result = rf.call_remote_function("my_function", 10, 20)
    print(result)

    # Option 2: Using the remote decorator.
    @rf.as_remote()
    def my_function(x, y):
        pass  # Function body is not executed on the client.
    result = my_function(10, 20)
    print(result)

All communication between client and server includes a hashed verification of the payload to prevent
tampering, ensuring secure and reliable remote function execution.
"""
import pickle
from flask import Flask, request, Response
import requests
from typing import List, Callable, Any, Union
import hashlib
import inspect
import functools
from process_managerial import QueueSystemLite
from process_managerial import QueueStatus

def _generate_hash_from_data(data: Any) -> str:
    """
    Generate a SHA-256 hash from pickled data.

    Parameters:
        data (Any): Data to hash.
    
    Returns:
        str: The hexadecimal SHA-256 hash of the pickled data.
    """
    pickled_data = pickle.dumps(data, protocol=4)
    return hashlib.sha256(pickled_data).hexdigest()

def pack_message(data) -> bytes:
    """
    Package a payload with its hash.

    The message is a dictionary containing:
      - 'payload': the actual data.
      - 'hash': the SHA-256 hash computed from the pickled payload.

    Parameters:
        data (Any): The data to be packaged.

    Returns:
        bytes: The pickled message.
    """
    message = {
        "payload": data,
        "hash": _generate_hash_from_data(data)
    }
    return pickle.dumps(message)

def unpack_message(message_bytes: bytes):
    """
    Unpack a message and verify its hash.

    Parameters:
        message_bytes (bytes): The pickled message to be unpacked.

    Returns:
        Any: The payload if the hash is verified.

    Raises:
        ValueError: If the message structure is invalid or the hash does not match.
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
    client and server is serialized using pickle.

    Optional password support:
      - If a password is provided at initialization, it is hashed and stored.
      - For every remote call, the hashed password is included in the request.
      - The server validates the provided hashed password against its stored hash.
    """

    def __init__(self, password: str = None, is_queue:bool = False):
        """
        Initialize a RemoteFunctions instance.

        Optional Parameters:
            password (str): Optional password for authentication. If provided, it will be hashed and used for all remote communications.
        
        Attributes:
            functions (dict): Empty dictionary to store registered functions.
            server_url (str): None, to be set when connecting as a client.
            app (Flask): None, will be initialized when starting the server.
            _password_hash (str): The SHA-256 hash of the password, if provided.
        """
        self.functions = {}
        self.server_url = None
        self.app = None
        self.is_server = True
        self.is_client = False
        self.server_started = False
        self._password_hash = self.set_password(password=password)

        self.is_queue = is_queue
        self.qs = QueueSystemLite()

    def set_password(self, password) -> str:
        self._password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
        return self._password_hash


    def _queue_function_with_wait(self, func, *args, **kwargs):
        queue_hex = self.qs.queue_function(func, *args, **kwargs)
        self.qs.wait_until_hex_finished(queue_hex)
        result_properties = self.qs.get_properties(queue_hex)
        if not result_properties:
            return f"Function lost... ? Unique Hex: {queue_hex}"
        if result_properties.status == QueueStatus.RETURNED_CLEAN:
            return result_properties.result
        else:
            return f"Error: {result_properties.status} - {result_properties.output}"

    def as_remote(self):
        def decorator(func):
            if func.__name__ not in self.functions:
                self.add_function(func)
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if self.is_server:
                    if self.is_server and (not self.is_queue or not self.server_started):                        
                        return func(*args, **kwargs)
                    else:
                        return self._queue_function_with_wait(func, *args, **kwargs)
                else:
                    return self.call_remote_function(func.__name__, *args, **kwargs)

            return wrapper
        return decorator

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
        Add a list of functions to the local function registry.

        Parameters:
            funcs (List[Callable]): A list of functions to register for remote invocation.

        Returns:
            None
        """
        for func in funcs:
            self.add_function(func)

    def _validate_request(self, provided_password: str):
        """
        Validate the provided password against the stored hashed password.

        Parameters:
            provided_password (str): The hashed password provided in the request.

        Raises:
            ValueError: If authentication fails.
        """
        if self._password_hash:
            if not provided_password or provided_password != self._password_hash:
                raise ValueError("Authentication failed: Invalid password")

    def start_server(self, host="0.0.0.0", port=5000):
        """
        Start the Flask server to serve registered functions.

        Initializes a Flask application with endpoints:
            - GET /ping: Returns a pickled "pong" message to verify server availability.
            - GET /functions: Returns a pickled list of registered function names and signatures.
            - POST /call: Executes a function call based on a pickled payload and returns a pickled result.

        Parameters:
            host (str): The hostname or IP address for the server to bind to. Defaults to "0.0.0.0".
            port (int): The port number for the server to listen on. Defaults to 5000.

        Returns:
            None
        """
        self.app = Flask(__name__)
        rf = self  # capture self in the route closures

        self.is_server = True
        self.is_client = False
        self.server_started = True

        @self.app.route("/ping", methods=["GET"])
        def ping_route():
            # If a password is set, validate the password provided as a query parameter.
            if rf._password_hash:
                provided = request.args.get("password")
                try:
                    rf._validate_request(provided)
                except Exception as e:
                    error_resp = pack_message({"error": str(e)})
                    return Response(error_resp, status=401, mimetype='application/octet-stream')
            # Return a simple "pong" response to indicate server availability.
            return Response(pack_message("pong"), mimetype='application/octet-stream')

        @self.app.route("/functions", methods=["GET"])
        def list_functions():
            # Validate the password if required.
            if rf._password_hash:
                provided = request.args.get("password")
                try:
                    rf._validate_request(provided)
                except Exception as e:
                    error_resp = pack_message({"error": str(e)})
                    return Response(error_resp, status=401, mimetype='application/octet-stream')
            try:
                # Build a list of registered functions with their names and parameter details.
                function_list = []
                for key in rf.functions.keys():
                    func_data = [key]
                    sig = inspect.signature(rf.functions[key])

                    for param_name, param in sig.parameters.items():
                        combined_details = f"{param_name}: {param.annotation} = {param.default}"
                        func_data.append(combined_details)

                    docstring = inspect.getdoc(rf.functions[key])
                    func_data.append(docstring)
                    
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
                - password (str, optional): Hashed password for authentication.
            """
            # Unpack and verify the incoming message.
            try:
                data = unpack_message(request.data)
            except Exception as e:
                error_resp = pack_message({"error": "Server error: " + str(e)})
                return Response(error_resp, status=400, mimetype='application/octet-stream')
            
            # Validate the password if required.
            if rf._password_hash:
                provided = data.get("password")
                try:
                    rf._validate_request(provided)
                except Exception as e:
                    error_resp = pack_message({"error": str(e)})
                    return Response(error_resp, status=401, mimetype='application/octet-stream')
                # Remove the password from the payload to prevent interference with function parameters.
                data.pop("password", None)

            func_name = data.get("function")
            args = data.get("args", [])
            kwargs = data.get("kwargs", {})

            # Check if the function exists in the registry.
            if func_name not in rf.functions:
                error_resp = pack_message({"error": f"Function '{func_name}' not found"})
                return Response(error_resp, status=404, mimetype='application/octet-stream')

            try:
                # Execute the function with the provided arguments.
                if self.is_server and (not self.is_queue or not self.server_started):
                    result = rf.functions[func_name](*args, **kwargs)
                else:
                    result = self._queue_function_with_wait(rf.functions[func_name], *args, **kwargs)
            except Exception as e:
                error_resp = pack_message({"error": "Server error: " + str(e)})
                return Response(error_resp, status=500, mimetype='application/octet-stream')

            response_message = pack_message(result)
            return Response(response_message, mimetype='application/octet-stream')

        print(f"Starting server at http://{host}:{port} ...")
        if self.is_queue and not self.qs.is_running:
            self.qs.start_queuesystem() # Starts queue system in separate thread

        self.app.run(host=host, port=port, threaded=True)
        self.server_started = False # After if not working
        return True

    def connect_to_server(self, address, port) -> bool:
        """
        Set the remote server address for client operations.

        Parameters:
            address (str): The IP address or hostname of the remote server.
            port (int): The port number on which the remote server is listening.

        Returns:
            bool: True if the server responds successfully to the ping, otherwise raises an exception.
        """
        self.is_server = False
        self.is_client = True
        self.server_url = f"http://{address}:{port}"
        return self.ping()

    def ping(self, timeout_seconds: float = 5.0):
        """
        Ping the remote server to check connectivity.

        Parameters:
            timeout_seconds (float): The timeout for the ping request in seconds.

        Returns:
            True if the server responds with "pong", otherwise raises an Exception.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
        params = {}
        # Include the hashed password as a query parameter if it exists.
        if self._password_hash:
            params["password"] = self._password_hash
        try:
            response = requests.get(f"{self.server_url}/ping", params=params, timeout=timeout_seconds)
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
            list: A list of function names and their parameter details registered on the remote server.

        Raises:
            ValueError: If the server URL has not been set.
            Exception: If the HTTP request fails.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
        params = {}
        if self._password_hash:
            params["password"] = self._password_hash
        response = requests.get(f"{self.server_url}/functions", params=params)
        if response.status_code == 200:
            try:
                return unpack_message(response.content)
            except Exception as e:
                raise Exception("Client error: " + str(e))
        else:
            raise Exception(f"Error retrieving functions: {response.status_code}, {response.text}")

    def call_remote_function(self, func_name: Union[str, Callable], *args, **kwargs):
        """
        Call a remote function on the server and return its unpickled result.

        Sends a POST request to the remote server's /call endpoint with a pickled payload specifying:
            - func_name (str): The name of the remote function to call.
            - args (list): Positional arguments for the function.
            - kwargs (dict): Keyword arguments for the function.
            - password (str, optional): Hashed password for authentication.

        Parameters:
            func_name (str | Callable): The name of the remote function to call, or the function itself
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the remote function call (after unpickling the response).

        Raises:
            ValueError: If the server URL has not been set.
            Exception: If the HTTP request fails.
        """
        if not self.server_url:
            raise ValueError("Server URL not set. Use connect_to_server() first.")
            
        # Verify connectivity with a ping.
        self.ping()

        if callable(func_name):
            func_name: Callable = func_name
            func_name = func_name.__name__

        payload = {
            "function": func_name,
            "args": args,
            "kwargs": kwargs,
        }
        # Include the hashed password if set.
        if self._password_hash:
            payload["password"] = self._password_hash
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

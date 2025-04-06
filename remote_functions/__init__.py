"""
RemoteFunctions Package

This package provides the RemoteFunctions class for remote function registration,
listing, and invocation over HTTP. For full documentation and implementation details,
refer to the RemoteFunctions.py module.
"""

from .RemoteFunctions import RemoteFunctions
from .RemoteFunctions import run_self_with_output_filename

__all__ = [
  "RemoteFunctions",
  "run_self_with_output_filename"
]

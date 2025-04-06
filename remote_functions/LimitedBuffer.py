"""
This module provides a custom file-like class, LimitedBuffer, that intercepts writes to an output stream,
buffers the output, and restricts the stored content to the last `max_lines` lines. The buffered content is
continuously written to a specified file, ensuring controlled output size.
"""

import io

class LimitedBuffer(io.TextIOBase):
    """
    A file-like object that intercepts writes, maintains an internal buffer of text lines,
    and limits the content to a specified maximum number of lines.

    The buffered output is continuously written to a designated file, ensuring that only the last
    `max_lines` lines are preserved. This is particularly useful for redirecting streams like stdout
    while keeping the output file size in check.
    """

    def __init__(self, target, output_file, max_lines=200):
        """
        Initialize a new LimitedBuffer instance.

        Parameters:
            target (io.TextIOBase): The underlying stream (e.g., sys.__stdout__) that receives the original output.
            output_file (str): The file path where the buffered output will be written.
            max_lines (int, optional): The maximum number of lines to retain in the buffer. Defaults to 200.
        """
        super().__init__()
        self.target = target
        self.output_file = output_file
        self.max_lines = max_lines
        self.buffer = []

    def write(self, message):
        """
        Write a message to the underlying stream, update the internal buffer, and write the last max_lines to the file.

        This method intercepts the output, splits it into lines while preserving newline characters,
        and appends these lines to an internal buffer. If the buffer exceeds the maximum allowed lines,
        it trims the excess from the beginning. Finally, the current content of the buffer is written
        to the specified output file.

        Parameters:
            message (str): The text message to be written.
        """
        # Write directly to the original stream and flush
        self.target.write(message)
        self.target.flush()

        # Append new lines to the buffer, preserving newline characters
        self.buffer.extend(message.splitlines(keepends=True))
        
        # Trim the buffer if it exceeds the maximum allowed lines
        if len(self.buffer) > self.max_lines:
            self.buffer = self.buffer[-self.max_lines:]
        
        # Write the current buffer content to the output file
        with open(self.output_file, "w") as f:
            f.writelines(self.buffer)

    def flush(self):
        """
        Flush the underlying stream to ensure all data is written out.
        """
        self.target.flush()

    def writable(self):
        """
        Indicate that this stream supports writing.

        Returns:
            bool: True, since this stream is writable.
        """
        return True

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from ssl import SSLContext
from types import TracebackType
from typing import Any

from typing_extensions import Self

from aiovantage._logger import logger
from aiovantage.errors import CommandError, raise_command_error

from .connection import CommandConnection
from .converter import Converter


@dataclass
class CommandResponse:
    """Wrapper for command responses.

    Almost all commands will respond with a single "response" line, which contains the
    command name and any arguments that were returned.

    Some command, such as the "HELP" command, return multiple lines of text before the
    response line.
    """

    command: str
    """The command that was executed."""

    args: list[str]
    """The arguments that were returned on the response line."""

    data: list[str]
    """Any additional lines of text returned before the response line."""


class CommandClient:
    """Client for sending commands to the Vantage Host Command (HC) service.

    Connections are created lazily when needed, and closed when the client is closed,
    and will automatically reconnect if the connection is lost.

    Args:
        host: The hostname or IP address of the Vantage controller.
        username: The username to use for authentication.
        password: The password to use for authentication.
        ssl: The SSL context to use. True will use a default context, False will disable SSL.
        ssl_context_factory: A factory function to use when creating default SSL contexts.
        port: The port to connect to.
        conn_timeout: The connection timeout in seconds.
        read_timeout: The read timeout in seconds.
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        *,
        ssl: SSLContext | bool = True,
        ssl_context_factory: Callable[[], SSLContext] | None = None,
        port: int | None = None,
        conn_timeout: float = 30,
        read_timeout: float = 60,
    ) -> None:
        """Initialize the client."""
        self._connection = CommandConnection(
            host,
            port=port,
            ssl=ssl,
            ssl_context_factory=ssl_context_factory,
            conn_timeout=conn_timeout,
        )

        self._username = username
        self._password = password
        self._read_timeout = read_timeout
        self._connection_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        """Return context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        self.close()
        if exc_val:
            raise exc_val

    def close(self) -> None:
        """Close the connection to the Host Command service."""
        self._connection.close()

    async def command(self, command: str, *params: Any) -> CommandResponse:
        """Send a command to the Host Command service and wait for a response.

        Args:
            command: The command to send, should be a single word string.
            params: The parameters to send with the command.

        Returns:
            A CommandResponse instance.
        """
        # Build the request
        request = command
        if params:
            request += " " + " ".join(Converter.serialize(p) for p in params)

        # Send the request
        *data, return_line = await self.raw_request(request)

        # Break the response into tokens
        command, *args = Converter.tokenize(return_line)

        # Parse the response
        return CommandResponse(command[2:], args, data)

    async def raw_request(self, request: str, *, expect_vid: str | None = None) -> list[str]:
        """Send a raw command to the Host Command service and return all response lines.

        Handles authentication if required, and raises an exception if the response line
        contains R:ERROR.

        Args:
            request: The request to send.
            expect_vid: If given, the vid (2nd token) that the terminal "R:" response
                line must carry. The Host Command protocol has no request/response
                correlation id, so this client normally just trusts that the next
                "R:" line it reads is the answer to what it just sent. That trust
                breaks if a *previous* command on this connection timed out or
                errored out mid-read: its connection is left open, so that
                abandoned command's real (but late) response can still arrive and
                would otherwise be handed to whatever request reads next. When
                expect_vid is set, any "R:" line for a different vid is treated
                like an interleaved event message: logged and skipped, so we keep
                waiting for the response that actually answers this request.

        Returns:
            The response lines received from the server.
        """
        conn = await self._get_connection()

        # Send the command
        async with self._command_lock:
            logger.debug("Sending command: %s", request)
            await conn.write(f"{request}\n")

            # Read all lines of the response
            response_lines: list[str] = []
            while True:
                try:
                    response_line = await conn.readuntil(b"\r\n", self._read_timeout)
                except BaseException as exc:
                    # We're abandoning this read before reaching our own
                    # terminating response line (timeout, cancellation, or a
                    # connection error). The controller may still send - or may
                    # have already sent - that response. Leaving the connection
                    # open would let those leftover bytes silently become the
                    # "answer" to whatever command reads next; unlike a mismatched
                    # vid on a normal response, an R:ERROR line carries no vid at
                    # all, so a stale error can't be caught by expect_vid either.
                    # Close so the next command starts on a clean connection.
                    logger.warning(
                        "Abandoning read for %r (%s: %s); closing connection so "
                        "its eventual response isn't misread as the answer to a "
                        "later command",
                        request,
                        type(exc).__name__,
                        exc,
                    )
                    conn.close()
                    raise

                response_line = response_line.rstrip()

                # Handle command errors
                if response_line.startswith("R:ERROR"):
                    # Log the raw line at receipt time, same as a normal response
                    # would be (below) - raise_command_error() below unwinds the
                    # stack before that log line runs, so without this an error
                    # response's arrival time is otherwise lost. R:ERROR carries
                    # no vid, so we can't attribute it to a request directly, but
                    # its timestamp can still be matched against an "Abandoning
                    # read" warning from a different in-flight command to confirm
                    # or rule out a stale/misattributed response.
                    logger.debug("Received response: %s", response_line)

                    # Parse a command error from a message.
                    match = re.match(r"R:ERROR:(\d+) (.+)", response_line)
                    if not match:
                        raise CommandError(response_line)

                    # Convert the error code to a specific exception, if possible
                    raise_command_error(int(match.group(1)), match.group(2))

                # Ignore potentially interleaved "event" messages
                if response_line.startswith(("S:", "L:", "EL:")):
                    logger.debug("Ignoring event message: %s", response_line)
                    continue

                # Discard a stale response left over from an earlier, abandoned
                # request instead of misattributing it to this one.
                if response_line.startswith("R:") and expect_vid is not None:
                    tokens = Converter.tokenize(response_line)
                    if len(tokens) >= 2 and tokens[1] != expect_vid:
                        logger.warning(
                            "Discarding stale response for vid %s while waiting "
                            "for vid %s: %s",
                            tokens[1],
                            expect_vid,
                            response_line,
                        )
                        continue

                # Return the response once we see the response line
                response_lines.append(response_line)
                if response_line.startswith("R:"):
                    break

        logger.debug("Received response: %s", "\n".join(response_lines))

        return response_lines

    async def _get_connection(self) -> CommandConnection:
        """Get a connection to the Host Command service."""
        async with self._connection_lock:
            if self._connection.closed:
                # Open a new connection
                await self._connection.open()

                # Authenticate the new connection if we have credentials
                if self._username and self._password:
                    await self._connection.authenticate(self._username, self._password)

                logger.info(
                    "Connected to command client at %s:%d",
                    self._connection.host,
                    self._connection.port,
                )

            return self._connection

"""
D-Bus NetworkManager client with GLib MainLoop for async operations.

This module provides a wrapper around NetworkManager's D-Bus API using PyGObject.
It manages the GLib MainLoop in a separate thread and provides thread-safe async
operations for connection management.

Adapted from ProtonVPN's python-proton-vpn-network-manager implementation.

Copyright (c) 2023 Proton AG
Adapted for PIA NetworkManager Integration

This file is part of PIA NetworkManager Integration.

PIA NetworkManager Integration is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PIA NetworkManager Integration is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PIA NetworkManager Integration.  If not, see <https://www.gnu.org/licenses/>.
"""

import logging
from concurrent.futures import Future
from threading import Thread, Lock
from typing import Callable, Optional, List, Dict, Any, Tuple

import gi

gi.require_version("NM", "1.0")  # noqa: required before importing NM module
# pylint: disable=wrong-import-position
from gi.repository import NM, GLib

logger = logging.getLogger(__name__)


class NMClient:
    """
    Wrapper over the NetworkManager D-Bus client.

    Manages a singleton NM.Client instance with a GLib MainLoop running in a
    separate daemon thread. All D-Bus operations are executed on the MainLoop
    thread to ensure thread safety.

    This class provides async/await support by bridging GLib callbacks to
    Python Futures.
    """

    # Class-level singleton state
    _lock = Lock()
    _main_context: Optional[GLib.MainContext] = None
    _main_loop: Optional[GLib.MainLoop] = None
    _nm_client: Optional[NM.Client] = None
    _main_loop_thread: Optional[Thread] = None

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize the NM client singleton with GLib MainLoop.

        If the singleton was already initialized, this method does nothing.
        Uses double-checked locking to avoid race conditions when multiple
        threads try to initialize simultaneously.
        """
        if cls._nm_client:
            return

        with cls._lock:
            if not cls._nm_client:
                cls._initialize_singleton()

    @classmethod
    def _initialize_singleton(cls) -> None:
        """Internal method to initialize the singleton."""
        logger.debug("Initializing NM client singleton")

        # Create a new GLib MainContext for this thread
        cls._main_context = GLib.MainContext()

        # Create an uninitialized NM client
        cls._nm_client = NM.Client()

        # Start the GLib MainLoop in a daemon thread
        # Daemon=True means the thread exits when the main process exits
        cls._main_loop_thread = Thread(target=cls._run_main_loop, daemon=True)
        cls._main_loop_thread.start()

        # Initialize the NM client asynchronously on the MainLoop thread
        callback, future = cls.create_callback(finish_method_name="new_finish")

        def new_async():
            cls._assert_running_on_main_loop_thread()
            cls._nm_client.new_async(cancellable=None, callback=callback, user_data=None)

        cls._run_on_main_loop(new_async)

        # Wait for initialization to complete and replace with initialized client
        cls._nm_client = future.result()

        logger.info("NM client singleton initialized with GLib MainLoop")

    @classmethod
    def _run_main_loop(cls) -> None:
        """
        Run the GLib MainLoop in a daemon thread.

        This method is executed in a separate thread and runs the GLib event loop.
        It processes all D-Bus events and callbacks.
        """
        logger.debug("Starting GLib MainLoop in daemon thread")

        # Create the main loop first
        cls._main_loop = GLib.MainLoop(cls._main_context)

        # Then push the main context as the default for this thread
        cls._main_context.push_thread_default()

        # Run the main loop
        cls._main_loop.run()

        logger.debug("GLib MainLoop stopped")

    @classmethod
    def _assert_running_on_main_loop_thread(cls) -> None:
        """
        Assert that the current thread is the one running the GLib MainLoop.

        This is useful for debugging to catch threading issues early.
        Raises AssertionError if called from a different thread.
        """
        if not cls._main_context.is_owner():
            raise AssertionError("This method must be called from the GLib MainLoop thread")

    @classmethod
    def _run_on_main_loop(cls, function: Callable) -> None:
        """
        Execute a function on the GLib MainLoop thread.

        This method is thread-safe and can be called from any thread.
        The function will be executed on the MainLoop thread.

        Args:
            function: Callable to execute on the MainLoop thread
        """
        cls._main_context.invoke_full(priority=GLib.PRIORITY_DEFAULT, function=function)

    @classmethod
    def create_callback(cls, finish_method_name: str) -> Tuple[Callable, Future]:
        """
        Create a GLib callback and corresponding Future for async operations.

        This bridges GLib's callback-based async API to Python's Future-based
        async/await pattern.

        Args:
            finish_method_name: Name of the finish method to call on the source object
                               (e.g., "add_connection_finish", "activate_connection_finish")

        Returns:
            Tuple of (callback_function, Future)
            - callback_function: GLib callback to pass to async methods
            - Future: Will be resolved when the callback is called
        """
        future: Future = Future()
        future.set_running_or_notify_cancel()

        def callback(source_object, res, userdata):  # pylint: disable=unused-argument
            """GLib callback that bridges to Future."""
            try:
                cls._assert_running_on_main_loop_thread()

                # Handle error cases where source_object or res is None
                if not source_object or not res:
                    raise RuntimeError(
                        f"D-Bus operation failed: source_object={source_object}, res={res}"
                    )

                # Call the finish method to get the result
                result = getattr(source_object, finish_method_name)(res)

                # Note: Some finish methods (like update2_finish, delete_finish) return None
                # on success. Real D-Bus errors are caught as GLib.Error below, so we don't
                # need to check for None here.

                # Set the result on the Future
                future.set_result(result)

            except GLib.Error as exc:
                # GLib.Error from D-Bus operations - extract meaningful error info
                error_msg = f"{exc.message} ({exc.domain}: {exc.code})"
                logger.error("D-Bus operation failed: %s", error_msg)
                future.set_exception(RuntimeError(error_msg))
            except BaseException as exc:  # pylint: disable=broad-except
                # Set any exception on the Future
                future.set_exception(exc)

        return callback, future

    def __init__(self):
        """Initialize the NM client wrapper."""
        self.initialize()

    def add_connection_async(self, connection: NM.Connection) -> Future:
        """
        Add a new connection to NetworkManager asynchronously.

        Args:
            connection: NM.Connection object to add

        Returns:
            Future that resolves to NM.RemoteConnection when complete
        """
        callback, future = self.create_callback(finish_method_name="add_connection_finish")

        def add_connection_async_impl():
            self._assert_running_on_main_loop_thread()
            self._nm_client.add_connection_async(
                connection=connection,
                save_to_disk=True,  # Persist to disk for proper routing
                cancellable=None,
                callback=callback,
                user_data=None,
            )

        self._run_on_main_loop(add_connection_async_impl)
        return future

    def activate_connection_async(
        self,
        connection: NM.RemoteConnection,
        device: Optional[NM.Device] = None,
        specific_object: Optional[str] = None,
    ) -> Future:
        """
        Activate a connection asynchronously.

        Args:
            connection: NM.RemoteConnection to activate
            device: Optional NM.Device to activate on (None = auto-select)
            specific_object: Optional specific object path

        Returns:
            Future that resolves to NM.ActiveConnection when complete
        """
        callback, future = self.create_callback(finish_method_name="activate_connection_finish")

        def activate_connection_async_impl():
            self._assert_running_on_main_loop_thread()
            self._nm_client.activate_connection_async(
                connection,
                device,
                specific_object,
                None,  # cancellable
                callback,
                None,  # user_data
            )

        self._run_on_main_loop(activate_connection_async_impl)
        return future

    def remove_connection_async(self, connection: NM.RemoteConnection) -> Future:
        """
        Remove a connection from NetworkManager asynchronously.

        Args:
            connection: NM.RemoteConnection to remove

        Returns:
            Future that resolves when the connection is removed
        """
        callback, future = self.create_callback(finish_method_name="delete_finish")

        def delete_async_impl():
            self._assert_running_on_main_loop_thread()
            connection.delete_async(None, callback, None)  # cancellable  # user_data

        self._run_on_main_loop(delete_async_impl)
        return future

    def get_connection_by_uuid(self, uuid: str) -> Optional[NM.RemoteConnection]:
        """
        Get a connection by its UUID.

        Args:
            uuid: UUID of the connection to retrieve

        Returns:
            NM.RemoteConnection if found, None otherwise
        """
        return self._nm_client.get_connection_by_uuid(uuid)

    def get_connection_by_id(self, conn_id: str) -> Optional[NM.RemoteConnection]:
        """
        Get a connection by its ID (name).

        Args:
            conn_id: ID/name of the connection to retrieve

        Returns:
            NM.RemoteConnection if found, None otherwise
        """
        return self._nm_client.get_connection_by_id(conn_id)

    def list_connections(self) -> List[NM.RemoteConnection]:
        """
        List all connections in NetworkManager.

        Returns:
            List of NM.RemoteConnection objects
        """
        return self._nm_client.get_connections()

    def get_active_connection(self, conn_id: str) -> Optional[NM.ActiveConnection]:
        """
        Get an active connection by its ID.

        Args:
            conn_id: ID/name of the connection

        Returns:
            NM.ActiveConnection if the connection is active, None otherwise
        """
        active_connections = self._nm_client.get_active_connections()

        for active_conn in active_connections:
            # Get the remote connection associated with this active connection
            remote_conn = active_conn.get_connection()
            if remote_conn and remote_conn.get_id() == conn_id:
                return active_conn

        return None

    def get_device_for_connection(self, connection: NM.RemoteConnection) -> Optional[NM.Device]:
        """
        Get the device associated with an active connection.

        Args:
            connection: NM.RemoteConnection to find device for

        Returns:
            NM.Device if found, None otherwise
        """
        active_conn = self.get_active_connection(connection.get_id())
        if not active_conn:
            return None

        devices = active_conn.get_devices()
        return devices[0] if devices else None

    def reapply_connection(
        self, device: NM.Device, settings: Dict[str, Any], version_id: int
    ) -> bool:
        """
        Reapply connection settings without disconnecting.

        This is used for live token refresh - updating the connection settings
        while it remains active.

        Args:
            device: NM.Device to reapply settings on
            settings: Dictionary of settings to apply
            version_id: Version ID from GetAppliedConnection

        Returns:
            True if successful, False otherwise
        """
        try:

            def reapply_impl():
                self._assert_running_on_main_loop_thread()
                # Call the Reapply method on the device
                device.reapply(settings, version_id, 0)

            self._run_on_main_loop(reapply_impl)
            return True

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to reapply connection: %s", exc)
            return False

    def get_applied_connection(self, device: NM.Device) -> Optional[Tuple[Dict[str, Any], int]]:
        """
        Get the currently applied connection settings for a device.

        Used before calling reapply_connection to get the current settings
        and version_id.

        Args:
            device: NM.Device to get applied connection for

        Returns:
            Tuple of (settings_dict, version_id) if successful, None otherwise
        """
        try:

            def get_applied_impl():
                self._assert_running_on_main_loop_thread()
                # Call GetAppliedConnection on the device
                return device.get_applied_connection(0)

            # This is a synchronous call, so we need to run it on the main loop
            # and wait for the result
            result_container = []

            def wrapper():
                try:
                    result = get_applied_impl()
                    result_container.append(result)
                except Exception as exc:  # pylint: disable=broad-except
                    result_container.append(exc)

            self._run_on_main_loop(wrapper)

            if result_container and isinstance(result_container[0], Exception):
                raise result_container[0]

            return result_container[0] if result_container else None

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to get applied connection: %s", exc)
            return None

    def update_connection_async(self, connection: NM.RemoteConnection, settings: Any) -> Future:
        """
        Update a connection's settings asynchronously.

        This updates the saved connection profile. For active connections,
        the changes will take effect on next activation unless reapply is used.

        Args:
            connection: NM.RemoteConnection to update
            settings: GLib.Variant of new settings (from to_dbus())

        Returns:
            Future that resolves when the update is complete
        """
        from gi.repository import GLib

        callback, future = self.create_callback(finish_method_name="update2_finish")

        def update_async_impl():
            self._assert_running_on_main_loop_thread()
            # update2 signature: (settings, flags, args, cancellable, callback, user_data)
            # settings: GLib.Variant of type a{sa{sv}}
            # flags: NM.SettingsUpdate2Flags (use NONE for standard update)
            # args: GLib.Variant of type a{sv} (empty dict for no additional arguments)
            connection.update2(
                settings,  # GLib.Variant
                NM.SettingsUpdate2Flags.NONE,  # flags
                GLib.Variant("a{sv}", {}),  # args (empty dict as Variant)
                None,  # cancellable
                callback,
                None,  # user_data
            )

        self._run_on_main_loop(update_async_impl)
        return future

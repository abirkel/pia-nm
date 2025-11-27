"""Unit tests for D-Bus NetworkManager client module.

Tests cover:
- NM client singleton initialization
- GLib MainLoop thread management
- Callback-to-Future bridge
- D-Bus async operations
- Thread safety
"""

import sys
import threading
from concurrent.futures import Future
from unittest.mock import Mock, MagicMock, patch

import pytest

# Mock PyGObject modules before importing dbus_client
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
sys.modules["gi.repository.NM"] = MagicMock()
sys.modules["gi.repository.GLib"] = MagicMock()

from pia_nm.dbus_client import NMClient


class TestNMClientSingleton:
    """Test NM client singleton initialization."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None
        NMClient._lock = threading.Lock()

    def test_initialize_creates_singleton(self):
        """Test that initialize creates a singleton instance."""
        with patch.object(NMClient, "_initialize_singleton"):
            NMClient.initialize()
            NMClient._initialize_singleton.assert_called_once()

    def test_initialize_idempotent(self):
        """Test that initialize is idempotent."""
        # Set _nm_client to a non-None value to simulate already initialized
        NMClient._nm_client = Mock()
        
        with patch.object(NMClient, "_initialize_singleton") as mock_init:
            # First call
            NMClient.initialize()
            assert mock_init.call_count == 0

            # Second call should also not call _initialize_singleton
            NMClient.initialize()
            assert mock_init.call_count == 0

    def test_initialize_thread_safe(self):
        """Test that initialize is thread-safe."""
        call_count = [0]

        def counting_init():
            call_count[0] += 1
            # Simulate some work
            import time
            time.sleep(0.01)
            NMClient._nm_client = Mock()

        with patch.object(NMClient, "_initialize_singleton", side_effect=counting_init):
            threads = []
            for _ in range(5):
                t = threading.Thread(target=NMClient.initialize)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Should only be called once despite multiple threads
            assert call_count[0] == 1

    def test_nm_client_instance_creation(self):
        """Test that NMClient instance can be created."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            NMClient.initialize.assert_called_once()


class TestCallbackBridge:
    """Test callback-to-Future bridge."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_create_callback_returns_tuple(self):
        """Test that create_callback returns (callback, Future)."""
        with patch.object(NMClient, "initialize"):
            callback, future = NMClient.create_callback("test_finish")

            assert callable(callback)
            assert isinstance(future, Future)

    def test_create_callback_future_is_running(self):
        """Test that returned Future is in running state."""
        with patch.object(NMClient, "initialize"):
            callback, future = NMClient.create_callback("test_finish")

            assert future.running()

    def test_callback_sets_result_on_success(self):
        """Test that callback sets result on Future when successful."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_assert_running_on_main_loop_thread"):
                callback, future = NMClient.create_callback("test_finish")

                # Create mock source object with finish method
                source_obj = Mock()
                source_obj.test_finish = Mock(return_value="test_result")

                # Call callback
                callback(source_obj, Mock(), None)

                # Future should have the result
                assert future.result() == "test_result"

    def test_callback_sets_exception_on_error(self):
        """Test that callback sets exception on Future when error occurs."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_assert_running_on_main_loop_thread"):
                callback, future = NMClient.create_callback("test_finish")

                # Call callback with None source_object to trigger error
                callback(None, Mock(), None)

                # Future should have an exception
                with pytest.raises(RuntimeError):
                    future.result()

    def test_callback_handles_finish_method_returning_none(self):
        """Test that callback handles finish method returning None."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_assert_running_on_main_loop_thread"):
                callback, future = NMClient.create_callback("test_finish")

                # Create mock source object with finish method that returns None
                source_obj = Mock()
                source_obj.test_finish = Mock(return_value=None)

                # Call callback
                callback(source_obj, Mock(), None)

                # Future should have an exception
                with pytest.raises(RuntimeError):
                    future.result()

    def test_callback_handles_exception_in_finish_method(self):
        """Test that callback handles exceptions from finish method."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_assert_running_on_main_loop_thread"):
                callback, future = NMClient.create_callback("test_finish")

                # Create mock source object with finish method that raises
                source_obj = Mock()
                source_obj.test_finish = Mock(side_effect=ValueError("Test error"))

                # Call callback
                callback(source_obj, Mock(), None)

                # Future should have the exception
                with pytest.raises(ValueError, match="Test error"):
                    future.result()


class TestAsyncOperations:
    """Test async D-Bus operations."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_add_connection_async_returns_future(self):
        """Test that add_connection_async returns a Future."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop"):
                client = NMClient()
                connection = Mock()

                future = client.add_connection_async(connection)

                assert isinstance(future, Future)

    def test_add_connection_async_calls_run_on_main_loop(self):
        """Test that add_connection_async calls _run_on_main_loop."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop") as mock_run:
                client = NMClient()
                connection = Mock()

                client.add_connection_async(connection)

                mock_run.assert_called_once()

    def test_activate_connection_async_returns_future(self):
        """Test that activate_connection_async returns a Future."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop"):
                client = NMClient()
                connection = Mock()

                future = client.activate_connection_async(connection)

                assert isinstance(future, Future)

    def test_remove_connection_async_returns_future(self):
        """Test that remove_connection_async returns a Future."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop"):
                client = NMClient()
                connection = Mock()

                future = client.remove_connection_async(connection)

                assert isinstance(future, Future)


class TestConnectionQueries:
    """Test connection query methods."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_get_connection_by_uuid(self):
        """Test getting connection by UUID."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            mock_connection = Mock()
            NMClient._nm_client = Mock()
            NMClient._nm_client.get_connection_by_uuid = Mock(return_value=mock_connection)

            result = client.get_connection_by_uuid("test-uuid")

            assert result == mock_connection
            NMClient._nm_client.get_connection_by_uuid.assert_called_once_with("test-uuid")

    def test_get_connection_by_uuid_not_found(self):
        """Test getting connection by UUID when not found."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            NMClient._nm_client = Mock()
            NMClient._nm_client.get_connection_by_uuid = Mock(return_value=None)

            result = client.get_connection_by_uuid("nonexistent-uuid")

            assert result is None

    def test_get_connection_by_id(self):
        """Test getting connection by ID."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            mock_connection = Mock()
            NMClient._nm_client = Mock()
            NMClient._nm_client.get_connection_by_id = Mock(return_value=mock_connection)

            result = client.get_connection_by_id("PIA-US-East")

            assert result == mock_connection
            NMClient._nm_client.get_connection_by_id.assert_called_once_with("PIA-US-East")

    def test_list_connections(self):
        """Test listing all connections."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            mock_connections = [Mock(), Mock(), Mock()]
            NMClient._nm_client = Mock()
            NMClient._nm_client.get_connections = Mock(return_value=mock_connections)

            result = client.list_connections()

            assert result == mock_connections
            assert len(result) == 3

    def test_list_connections_empty(self):
        """Test listing connections when none exist."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()
            NMClient._nm_client = Mock()
            NMClient._nm_client.get_connections = Mock(return_value=[])

            result = client.list_connections()

            assert result == []


class TestActiveConnectionQueries:
    """Test active connection query methods."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_get_active_connection_found(self):
        """Test getting active connection when it exists."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            # Create mock active connection
            mock_active_conn = Mock()
            mock_remote_conn = Mock()
            mock_remote_conn.get_id = Mock(return_value="PIA-US-East")
            mock_active_conn.get_connection = Mock(return_value=mock_remote_conn)

            NMClient._nm_client = Mock()
            NMClient._nm_client.get_active_connections = Mock(
                return_value=[mock_active_conn]
            )

            result = client.get_active_connection("PIA-US-East")

            assert result == mock_active_conn

    def test_get_active_connection_not_found(self):
        """Test getting active connection when it doesn't exist."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            # Create mock active connection with different ID
            mock_active_conn = Mock()
            mock_remote_conn = Mock()
            mock_remote_conn.get_id = Mock(return_value="PIA-UK-London")
            mock_active_conn.get_connection = Mock(return_value=mock_remote_conn)

            NMClient._nm_client = Mock()
            NMClient._nm_client.get_active_connections = Mock(
                return_value=[mock_active_conn]
            )

            result = client.get_active_connection("PIA-US-East")

            assert result is None

    def test_get_active_connection_multiple_connections(self):
        """Test getting active connection from multiple active connections."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            # Create multiple mock active connections
            mock_active_conn1 = Mock()
            mock_remote_conn1 = Mock()
            mock_remote_conn1.get_id = Mock(return_value="PIA-UK-London")
            mock_active_conn1.get_connection = Mock(return_value=mock_remote_conn1)

            mock_active_conn2 = Mock()
            mock_remote_conn2 = Mock()
            mock_remote_conn2.get_id = Mock(return_value="PIA-US-East")
            mock_active_conn2.get_connection = Mock(return_value=mock_remote_conn2)

            NMClient._nm_client = Mock()
            NMClient._nm_client.get_active_connections = Mock(
                return_value=[mock_active_conn1, mock_active_conn2]
            )

            result = client.get_active_connection("PIA-US-East")

            assert result == mock_active_conn2

    def test_get_device_for_connection_found(self):
        """Test getting device for active connection."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            # Create mock device
            mock_device = Mock()

            # Create mock active connection
            mock_active_conn = Mock()
            mock_active_conn.get_devices = Mock(return_value=[mock_device])

            # Create mock remote connection
            mock_remote_conn = Mock()
            mock_remote_conn.get_id = Mock(return_value="PIA-US-East")

            # Mock get_active_connection to return our mock
            with patch.object(client, "get_active_connection", return_value=mock_active_conn):
                result = client.get_device_for_connection(mock_remote_conn)

                assert result == mock_device

    def test_get_device_for_connection_not_active(self):
        """Test getting device when connection is not active."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            mock_remote_conn = Mock()
            mock_remote_conn.get_id = Mock(return_value="PIA-US-East")

            # Mock get_active_connection to return None
            with patch.object(client, "get_active_connection", return_value=None):
                result = client.get_device_for_connection(mock_remote_conn)

                assert result is None

    def test_get_device_for_connection_no_devices(self):
        """Test getting device when active connection has no devices."""
        with patch.object(NMClient, "initialize"):
            client = NMClient()

            # Create mock active connection with no devices
            mock_active_conn = Mock()
            mock_active_conn.get_devices = Mock(return_value=[])

            mock_remote_conn = Mock()
            mock_remote_conn.get_id = Mock(return_value="PIA-US-East")

            # Mock get_active_connection to return our mock
            with patch.object(client, "get_active_connection", return_value=mock_active_conn):
                result = client.get_device_for_connection(mock_remote_conn)

                assert result is None


class TestReapplyConnection:
    """Test connection reapply for live token refresh."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_reapply_connection_success(self):
        """Test successful connection reapply."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop"):
                client = NMClient()
                mock_device = Mock()
                settings = {"wireguard": {"private-key": "new_key"}}

                result = client.reapply_connection(mock_device, settings, 1)

                assert result is True

    def test_reapply_connection_failure(self):
        """Test failed connection reapply."""
        with patch.object(NMClient, "initialize"):
            with patch.object(NMClient, "_run_on_main_loop", side_effect=Exception("Test error")):
                client = NMClient()
                mock_device = Mock()
                settings = {"wireguard": {"private-key": "new_key"}}

                result = client.reapply_connection(mock_device, settings, 1)

                assert result is False


class TestThreadSafety:
    """Test thread safety of operations."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    def test_assert_running_on_main_loop_thread_success(self):
        """Test assertion passes when on main loop thread."""
        with patch.object(NMClient, "initialize"):
            NMClient._main_context = Mock()
            NMClient._main_context.is_owner = Mock(return_value=True)

            # Should not raise
            NMClient._assert_running_on_main_loop_thread()

    def test_assert_running_on_main_loop_thread_failure(self):
        """Test assertion fails when not on main loop thread."""
        with patch.object(NMClient, "initialize"):
            NMClient._main_context = Mock()
            NMClient._main_context.is_owner = Mock(return_value=False)

            with pytest.raises(AssertionError):
                NMClient._assert_running_on_main_loop_thread()

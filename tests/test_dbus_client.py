"""Unit tests for D-Bus NetworkManager client module.

Tests cover:
- NM.Client singleton initialization
- GLib MainLoop thread management
- Thread safety of D-Bus operations
- Callback-to-Future bridge
- Connection management operations
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from concurrent.futures import Future
from threading import Thread
import time

# Mock gi.repository before importing dbus_client
import sys
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()

# Create mock NM and GLib modules
mock_nm = MagicMock()
mock_glib = MagicMock()
sys.modules['gi.repository.NM'] = mock_nm
sys.modules['gi.repository.GLib'] = mock_glib

from pia_nm.dbus_client import NMClient


class TestNMClientInitialization:
    """Test NMClient singleton initialization."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_initialize_creates_singleton(self, mock_thread, mock_context, mock_nm_client):
        """Test that initialize creates singleton NM client."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        # Verify singleton was created
        assert NMClient._nm_client is not None
        assert NMClient._main_context is not None
        assert NMClient._main_loop_thread is not None

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_initialize_only_once(self, mock_thread, mock_context, mock_nm_client):
        """Test that initialize only creates singleton once."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Call initialize multiple times
        NMClient.initialize()
        first_client = NMClient._nm_client
        
        NMClient.initialize()
        second_client = NMClient._nm_client

        # Should be the same instance
        assert first_client is second_client
        
        # Thread should only be started once
        assert mock_thread_instance.start.call_count == 1

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_init_calls_initialize(self, mock_thread, mock_context, mock_nm_client):
        """Test that __init__ calls initialize."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        # Verify singleton was initialized
        assert NMClient._nm_client is not None


class TestThreadSafety:
    """Test thread safety of D-Bus operations."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_run_on_main_loop_uses_invoke_full(self, mock_thread, mock_context, mock_nm_client):
        """Test that _run_on_main_loop uses GLib.MainContext.invoke_full."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        # Create a test function
        test_func = MagicMock()

        # Call _run_on_main_loop
        NMClient._run_on_main_loop(test_func)

        # Verify invoke_full was called
        mock_context_instance.invoke_full.assert_called_once()
        call_args = mock_context_instance.invoke_full.call_args
        assert call_args[1]['function'] == test_func

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_assert_running_on_main_loop_thread_raises_when_not_owner(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that _assert_running_on_main_loop_thread raises when not on MainLoop thread."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = False
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        with pytest.raises(AssertionError, match="must be called from the GLib MainLoop thread"):
            NMClient._assert_running_on_main_loop_thread()

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_assert_running_on_main_loop_thread_passes_when_owner(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that _assert_running_on_main_loop_thread passes when on MainLoop thread."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = True
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        # Should not raise
        NMClient._assert_running_on_main_loop_thread()


class TestCallbackToFutureBridge:
    """Test callback-to-Future bridge functionality."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_create_callback_returns_callback_and_future(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that create_callback returns a callback function and Future."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = True
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        callback, future = NMClient.create_callback("test_finish")

        assert callable(callback)
        assert isinstance(future, Future)

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_callback_sets_future_result_on_success(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that callback sets Future result on successful operation."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = True
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        callback, future = NMClient.create_callback("test_finish")

        # Create mock source object with finish method
        mock_source = MagicMock()
        mock_result = MagicMock()
        mock_source.test_finish.return_value = mock_result

        # Call the callback
        callback(mock_source, MagicMock(), None)

        # Verify Future was resolved
        assert future.done()
        assert future.result() == mock_result

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_callback_sets_future_exception_on_error(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that callback sets Future exception on error."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = True
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        callback, future = NMClient.create_callback("test_finish")

        # Create mock source object that raises exception
        mock_source = MagicMock()
        test_exception = RuntimeError("Test error")
        mock_source.test_finish.side_effect = test_exception

        # Call the callback
        callback(mock_source, MagicMock(), None)

        # Verify Future has exception
        assert future.done()
        with pytest.raises(RuntimeError, match="Test error"):
            future.result()

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_callback_handles_none_source_object(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that callback handles None source_object gracefully."""
        mock_context_instance = MagicMock()
        mock_context_instance.is_owner.return_value = True
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        NMClient.initialize()

        callback, future = NMClient.create_callback("test_finish")

        # Call callback with None source_object
        callback(None, MagicMock(), None)

        # Verify Future has exception
        assert future.done()
        with pytest.raises(RuntimeError, match="D-Bus operation failed"):
            future.result()


class TestConnectionManagement:
    """Test connection management operations."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_add_connection_async_returns_future(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that add_connection_async returns a Future."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        mock_connection = MagicMock()
        future = client.add_connection_async(mock_connection)

        assert isinstance(future, Future)

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_activate_connection_async_returns_future(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that activate_connection_async returns a Future."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        mock_connection = MagicMock()
        future = client.activate_connection_async(mock_connection)

        assert isinstance(future, Future)

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_remove_connection_async_returns_future(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test that remove_connection_async returns a Future."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        mock_connection = MagicMock()
        future = client.remove_connection_async(mock_connection)

        assert isinstance(future, Future)

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_get_connection_by_uuid(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test get_connection_by_uuid delegates to NM.Client."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_connection = MagicMock()
        mock_nm_instance.get_connection_by_uuid.return_value = mock_connection
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        result = client.get_connection_by_uuid("test-uuid")

        assert result == mock_connection
        mock_nm_instance.get_connection_by_uuid.assert_called_once_with("test-uuid")

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_get_connection_by_id(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test get_connection_by_id delegates to NM.Client."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_connection = MagicMock()
        mock_nm_instance.get_connection_by_id.return_value = mock_connection
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        result = client.get_connection_by_id("test-id")

        assert result == mock_connection
        mock_nm_instance.get_connection_by_id.assert_called_once_with("test-id")

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_list_connections(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test list_connections delegates to NM.Client."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_connections = [MagicMock(), MagicMock()]
        mock_nm_instance.get_connections.return_value = mock_connections
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        result = client.list_connections()

        assert result == mock_connections
        mock_nm_instance.get_connections.assert_called_once()

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_get_active_connection_found(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test get_active_connection returns active connection when found."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        
        # Create mock active connection
        mock_active_conn = MagicMock()
        mock_remote_conn = MagicMock()
        mock_remote_conn.get_id.return_value = "test-id"
        mock_active_conn.get_connection.return_value = mock_remote_conn
        
        mock_nm_instance.get_active_connections.return_value = [mock_active_conn]
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        result = client.get_active_connection("test-id")

        assert result == mock_active_conn

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_get_active_connection_not_found(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test get_active_connection returns None when not found."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_instance.get_active_connections.return_value = []
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        result = client.get_active_connection("test-id")

        assert result is None


class TestReapplyConnection:
    """Test connection reapply functionality."""

    def setup_method(self):
        """Reset singleton state before each test."""
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_reapply_connection_success(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test successful connection reapply."""
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        mock_device = MagicMock()
        settings = {"wireguard": {"private-key": "new_key"}}
        version_id = 1

        result = client.reapply_connection(mock_device, settings, version_id)

        assert result is True

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    def test_reapply_connection_failure(
        self, mock_thread, mock_context, mock_nm_client
    ):
        """Test connection reapply handles errors."""
        mock_context_instance = MagicMock()
        mock_context_instance.invoke_full.side_effect = RuntimeError("Reapply failed")
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        client = NMClient()

        mock_device = MagicMock()
        settings = {"wireguard": {"private-key": "new_key"}}
        version_id = 1

        result = client.reapply_connection(mock_device, settings, version_id)

        assert result is False

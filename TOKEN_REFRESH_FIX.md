# Token Refresh Fix - UUID Tracking Issue

## Problem Identified

The token refresh was failing with error "0" when trying to update inactive connections. The logs showed:

```
2026-01-18 00:24:18,536 - pia_nm.token_refresh - ERROR - Error updating inactive connection PIA-JP STREAMING OPTIMIZED: 0
```

## Root Cause

The `refresh_inactive_connection()` function in `token_refresh.py` was calling `connection.update2()` directly without proper async handling. NetworkManager's `update2()` is an asynchronous GLib method that requires:

1. Proper callback handling
2. Execution on the GLib MainLoop thread
3. Correct parameter signature

The direct call was failing silently, returning 0 (failure code) instead of raising an exception.

## Solution

### 1. Added `update_connection_async()` method to `NMClient` (dbus_client.py)

```python
def update_connection_async(
    self, connection: NM.RemoteConnection, settings: Dict[str, Any]
) -> Future:
    """Update a connection's settings asynchronously."""
    callback, future = self.create_callback(finish_method_name="update2_finish")

    def update_async_impl():
        self._assert_running_on_main_loop_thread()
        connection.update2(
            settings,
            0,  # flags (0 = no special flags)
            None,  # args
            None,  # cancellable
            callback,
            None,  # user_data
        )

    self._run_on_main_loop(update_async_impl)
    return future
```

This method:
- Follows the same async pattern as other NMClient methods
- Executes on the GLib MainLoop thread
- Returns a Future that can be awaited
- Properly handles callbacks and errors

### 2. Updated `refresh_inactive_connection()` (token_refresh.py)

Changed from:
```python
connection.update2(updated_settings, NM.SettingSecretFlags.NONE, None)
```

To:
```python
future = nm_client.update_connection_async(connection, updated_settings)
future.result()  # Wait for the async operation to complete
```

## UUID Tracking Status

✅ **Token refresh is correctly using UUID-based connection tracking:**

1. Connections are looked up by UUID: `nm_client.get_connection_by_uuid(region_uuid)`
2. The correct connection object is passed to refresh functions
3. Internal use of `connection.get_id()` for logging is appropriate

The issue was NOT with UUID tracking, but with the async D-Bus call handling.

## Testing

After this fix, the token refresh should:
- Successfully update inactive connection profiles
- Properly handle async D-Bus operations
- Provide meaningful error messages if failures occur
- Work correctly with renamed connections (since UUID remains constant)

## Files Modified

1. `pia_nm/dbus_client.py` - Added `update_connection_async()` method
2. `pia_nm/token_refresh.py` - Updated `refresh_inactive_connection()` to use async method

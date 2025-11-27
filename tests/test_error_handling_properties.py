"""Property-based tests for error handling module.

This module tests correctness properties for error handling:
- Property 18: Typed Exception Handling
- Property 31: No Sensitive Data in Logs
- Property 33: No Sensitive Data in Exceptions
"""

import pytest
from hypothesis import given, strategies as st
from pia_nm.error_handling import (
    DBusError,
    ConnectionCreationError,
    ConnectionActivationError,
    ConnectionUpdateError,
    PeerConfigurationError,
    GLibError,
    filter_sensitive_data,
    handle_error,
)
import logging
from io import StringIO


# Property 18: Typed Exception Handling
# Feature: dbus-refactor, Property 18: Typed Exception Handling
# Validates: Requirements 5.1, 5.2
@given(error_message=st.text(min_size=1, max_size=100))
def test_property_typed_exception_handling(error_message):
    """
    Property 18: Typed Exception Handling

    For any error message, when a D-Bus exception is raised, it should be
    an instance of the appropriate exception type and inherit from DBusError.

    Validates: Requirements 5.1, 5.2
    """
    # Test ConnectionCreationError
    exc = ConnectionCreationError(error_message)
    assert isinstance(exc, DBusError)
    assert isinstance(exc, ConnectionCreationError)
    assert str(exc) == error_message

    # Test ConnectionActivationError
    exc = ConnectionActivationError(error_message)
    assert isinstance(exc, DBusError)
    assert isinstance(exc, ConnectionActivationError)
    assert str(exc) == error_message

    # Test ConnectionUpdateError
    exc = ConnectionUpdateError(error_message)
    assert isinstance(exc, DBusError)
    assert isinstance(exc, ConnectionUpdateError)
    assert str(exc) == error_message

    # Test PeerConfigurationError
    exc = PeerConfigurationError(error_message)
    assert isinstance(exc, DBusError)
    assert isinstance(exc, PeerConfigurationError)
    assert str(exc) == error_message

    # Test GLibError
    exc = GLibError(error_message)
    assert isinstance(exc, DBusError)
    assert isinstance(exc, GLibError)
    assert str(exc) == error_message


# Property 31 & 33: No Sensitive Data in Logs/Exceptions
# Feature: dbus-refactor, Property 31: No Sensitive Data in Logs
# Feature: dbus-refactor, Property 33: No Sensitive Data in Exceptions
# Validates: Requirements 13.2, 13.4
@given(
    prefix=st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_characters="\n\r")),
    suffix=st.text(min_size=0, max_size=20, alphabet=st.characters(blacklist_characters="\n\r")),
)
def test_property_no_sensitive_data_in_filtered_text(prefix, suffix):
    """
    Property 31 & 33: No Sensitive Data in Logs/Exceptions

    For any text containing sensitive data patterns (private keys, passwords, tokens),
    the filter_sensitive_data function should replace them with [REDACTED_*] markers.

    Validates: Requirements 13.2, 13.4
    """
    # Test WireGuard private key filtering (base64, 44 chars)
    private_key = "YOkj7VHgPmjKL0IzJ8hWLB+123456789abcdefg="
    text_with_key = f"{prefix}private-key: {private_key}{suffix}"
    filtered = filter_sensitive_data(text_with_key)
    assert private_key not in filtered
    assert "[REDACTED" in filtered

    # Test JWT token filtering
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    text_with_token = f"{prefix}token: {jwt_token}{suffix}"
    filtered = filter_sensitive_data(text_with_token)
    assert jwt_token not in filtered
    assert "[REDACTED" in filtered

    # Test password filtering
    password = "mySecretPassword123"
    text_with_password = f"{prefix}password: {password}{suffix}"
    filtered = filter_sensitive_data(text_with_password)
    assert password not in filtered
    assert "[REDACTED" in filtered

    # Test Authorization header filtering
    auth_header = "Authorization: Bearer abc123def456"
    filtered = filter_sensitive_data(auth_header)
    assert "abc123def456" not in filtered
    assert "[REDACTED" in filtered


@given(
    key_data=st.text(
        min_size=40,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="+/="),
    )
)
def test_property_base64_keys_always_filtered(key_data):
    """
    Property: Base64 keys are always filtered

    For any base64-like string (40+ chars with base64 alphabet),
    it should be filtered out as a potential key.

    Validates: Requirements 13.2, 13.4
    """
    # Ensure it looks like base64
    if len(key_data) >= 40 and any(
        c in key_data for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    ):
        text = f"private-key: {key_data}"
        filtered = filter_sensitive_data(text)
        # The key data should be redacted
        assert key_data not in filtered or "[REDACTED" in filtered


def test_filter_sensitive_data_empty_string():
    """Test that empty strings are handled correctly."""
    assert filter_sensitive_data("") == ""
    assert filter_sensitive_data(None) == None


def test_filter_sensitive_data_no_sensitive_content():
    """Test that non-sensitive text passes through unchanged."""
    safe_text = "This is a safe message with no secrets"
    assert filter_sensitive_data(safe_text) == safe_text


def test_filter_sensitive_data_multiple_patterns():
    """Test filtering multiple sensitive patterns in one string."""
    text = """
    private-key: YOkj7VHgPmjKL0IzJ8hWLB+123456789abcdefg=
    password: myPassword123
    token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U
    """
    filtered = filter_sensitive_data(text)

    # None of the sensitive data should remain
    assert "YOkj7VHgPmjKL0IzJ8hWLB+123456789abcdefg=" not in filtered
    assert "myPassword123" not in filtered
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in filtered

    # Should contain redaction markers
    assert "[REDACTED" in filtered


def test_exception_hierarchy():
    """Test that all D-Bus exceptions inherit from DBusError."""
    exceptions = [
        ConnectionCreationError,
        ConnectionActivationError,
        ConnectionUpdateError,
        PeerConfigurationError,
        GLibError,
    ]

    for exc_class in exceptions:
        exc = exc_class("test message")
        assert isinstance(exc, DBusError)
        assert isinstance(exc, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])

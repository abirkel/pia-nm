"""Unit tests for PIA API client module.

Tests cover:
- HTTP request handling and response validation
- Authentication with Basic Auth
- Region query and parsing
- WireGuard key registration
- Error handling and retry logic
"""

import base64
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

from pia_nm.api_client import (
    APIError,
    AuthenticationError,
    NetworkError,
    PIAClient,
)


class TestPIAClientInitialization:
    """Test PIAClient initialization."""

    def test_init_with_default_url(self):
        """Test initialization with default base URL."""
        client = PIAClient()
        assert client.base_url == "https://www.privateinternetaccess.com"

    def test_init_with_custom_url(self):
        """Test initialization with custom base URL."""
        custom_url = "https://custom.example.com"
        client = PIAClient(base_url=custom_url)
        assert client.base_url == custom_url

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL."""
        client = PIAClient(base_url="https://example.com/")
        assert client.base_url == "https://example.com"

    def test_session_created(self):
        """Test that requests session is created."""
        client = PIAClient()
        assert client.session is not None
        assert isinstance(client.session, requests.Session)


class TestResponseValidation:
    """Test response structure validation."""

    def test_validate_response_structure_valid(self):
        """Test validation passes for valid response."""
        client = PIAClient()
        response = {"token": "test_token", "expires_at": "2025-11-14T10:30:00Z"}

        # Should not raise
        client._validate_response_structure(response, ["token", "expires_at"])

    def test_validate_response_structure_missing_key(self):
        """Test validation fails when required key is missing."""
        client = PIAClient()
        response = {"token": "test_token"}

        with pytest.raises(APIError, match="Response missing required keys"):
            client._validate_response_structure(response, ["token", "expires_at"])

    def test_validate_response_structure_not_dict(self):
        """Test validation fails when response is not a dict."""
        client = PIAClient()
        response = ["not", "a", "dict"]

        with pytest.raises(APIError, match="Expected dict response"):
            client._validate_response_structure(response, ["token"])

    def test_validate_response_structure_multiple_missing_keys(self):
        """Test validation reports all missing keys."""
        client = PIAClient()
        response = {"token": "test"}

        with pytest.raises(APIError, match="Response missing required keys"):
            client._validate_response_structure(
                response, ["token", "expires_at", "other_key"]
            )


class TestAuthentication:
    """Test authentication method."""

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_authenticate_success(self, mock_request):
        """Test successful authentication."""
        mock_request.return_value = {"token": "test_token_123"}

        client = PIAClient()
        token = client.authenticate("testuser", "testpass")

        assert token == "test_token_123"

        # Verify request was made correctly
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/api/client/v2/token"

        # Verify Basic Auth header
        headers = call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

        # Verify credentials are base64 encoded
        auth_header = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(auth_header).decode("ascii")
        assert decoded == "testuser:testpass"

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_authenticate_no_token_in_response(self, mock_request):
        """Test authentication fails when token missing from response."""
        mock_request.return_value = {"expires_at": "2025-11-14T10:30:00Z"}

        client = PIAClient()

        with pytest.raises(AuthenticationError, match="Authentication failed"):
            client.authenticate("user", "pass")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_authenticate_network_error(self, mock_request):
        """Test authentication handles network errors."""
        mock_request.side_effect = NetworkError("Connection failed")

        client = PIAClient()

        with pytest.raises(NetworkError):
            client.authenticate("user", "pass")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_authenticate_api_error(self, mock_request):
        """Test authentication handles API errors."""
        mock_request.side_effect = AuthenticationError("Invalid credentials")

        client = PIAClient()

        with pytest.raises(AuthenticationError):
            client.authenticate("user", "pass")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_authenticate_unexpected_error(self, mock_request):
        """Test authentication handles unexpected errors."""
        mock_request.side_effect = ValueError("Unexpected error")

        client = PIAClient()

        with pytest.raises(AuthenticationError, match="Authentication failed"):
            client.authenticate("user", "pass")


class TestGetRegions:
    """Test region query method."""

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_success(self, mock_request):
        """Test successful region query."""
        mock_regions = [
            {
                "id": "us-east",
                "name": "US East",
                "country": "US",
                "dns": "10.0.0.242",
                "port_forward": False,
                "servers": {"wg": [{"ip": "192.0.2.1", "cn": "us-east", "port": 1337}]},
            },
            {
                "id": "uk-london",
                "name": "UK London",
                "country": "GB",
                "dns": "10.0.0.243",
                "port_forward": True,
                "servers": {"wg": [{"ip": "192.0.2.2", "cn": "uk-london", "port": 1337}]},
            },
        ]
        mock_request.return_value = {"regions": mock_regions}

        client = PIAClient()
        regions = client.get_regions()

        assert len(regions) == 2
        assert regions[0]["id"] == "us-east"
        assert regions[1]["id"] == "uk-london"

        # Verify request
        mock_request.assert_called_once_with("GET", "/api/client/v2/regions")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_empty_list(self, mock_request):
        """Test region query with empty region list."""
        mock_request.return_value = {"regions": []}

        client = PIAClient()
        regions = client.get_regions()

        assert regions == []

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_missing_regions_key(self, mock_request):
        """Test region query fails when regions key missing."""
        mock_request.return_value = {"data": []}

        client = PIAClient()

        with pytest.raises(APIError, match="Response missing required keys"):
            client.get_regions()

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_regions_not_list(self, mock_request):
        """Test region query fails when regions is not a list."""
        mock_request.return_value = {"regions": "not-a-list"}

        client = PIAClient()

        with pytest.raises(APIError, match="'regions' field is not a list"):
            client.get_regions()

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_network_error(self, mock_request):
        """Test region query handles network errors."""
        mock_request.side_effect = NetworkError("Connection failed")

        client = PIAClient()

        with pytest.raises(NetworkError):
            client.get_regions()

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_get_regions_unexpected_error(self, mock_request):
        """Test region query handles unexpected errors."""
        mock_request.side_effect = ValueError("Unexpected error")

        client = PIAClient()

        with pytest.raises(APIError, match="Failed to query regions"):
            client.get_regions()


class TestRegisterKey:
    """Test WireGuard key registration method."""

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_success(self, mock_request):
        """Test successful key registration."""
        mock_response = {
            "status": "OK",
            "server_key": "server_public_key_base64",
            "server_ip": "10.10.10.1",
            "server_port": 1337,
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242", "10.0.0.243"],
        }
        mock_request.return_value = mock_response

        client = PIAClient()
        result = client.register_key("test_token", "client_pubkey", "us-east")

        assert result == mock_response
        assert result["status"] == "OK"
        assert result["peer_ip"] == "10.20.30.40"

        # Verify request
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/client/v2/ephemeral/wireguard/register"

        # Verify headers
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Token test_token"
        assert headers["Content-Type"] == "application/json"

        # Verify JSON data
        json_data = call_args[1]["json_data"]
        assert json_data["pubkey"] == "client_pubkey"
        assert json_data["region_id"] == "us-east"

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_missing_required_fields(self, mock_request):
        """Test key registration fails when response missing required fields."""
        mock_request.return_value = {
            "status": "OK",
            "server_key": "key",
            # Missing other required fields
        }

        client = PIAClient()

        with pytest.raises(APIError, match="Response missing required keys"):
            client.register_key("token", "pubkey", "us-east")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_status_not_ok(self, mock_request):
        """Test key registration fails when status is not OK."""
        mock_request.return_value = {
            "status": "ERROR",
            "server_key": "key",
            "server_ip": "10.10.10.1",
            "server_port": 1337,
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }

        client = PIAClient()

        with pytest.raises(APIError, match="Key registration failed"):
            client.register_key("token", "pubkey", "us-east")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_authentication_error(self, mock_request):
        """Test key registration handles authentication errors."""
        mock_request.side_effect = AuthenticationError("Invalid token")

        client = PIAClient()

        with pytest.raises(AuthenticationError):
            client.register_key("bad_token", "pubkey", "us-east")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_network_error(self, mock_request):
        """Test key registration handles network errors."""
        mock_request.side_effect = NetworkError("Connection failed")

        client = PIAClient()

        with pytest.raises(NetworkError):
            client.register_key("token", "pubkey", "us-east")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_register_key_unexpected_error(self, mock_request):
        """Test key registration handles unexpected errors."""
        mock_request.side_effect = ValueError("Unexpected error")

        client = PIAClient()

        with pytest.raises(APIError, match="Failed to register key"):
            client.register_key("token", "pubkey", "us-east")


class TestMakeRequest:
    """Test internal request handling."""

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_get_success(self, mock_get):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PIAClient()
        result = client._make_request("GET", "/test/endpoint")

        assert result == {"result": "success"}
        mock_get.assert_called_once()

    @patch("pia_nm.api_client.requests.Session.post")
    def test_make_request_post_success(self, mock_post):
        """Test successful POST request."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": "created"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = PIAClient()
        result = client._make_request(
            "POST", "/test/endpoint", json_data={"key": "value"}
        )

        assert result == {"result": "created"}
        mock_post.assert_called_once()

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_timeout_retries(self, mock_get):
        """Test that timeout triggers retry."""
        mock_get.side_effect = [Timeout("Request timed out"), Mock(
            json=Mock(return_value={"result": "success"}),
            raise_for_status=Mock()
        )]

        client = PIAClient()
        result = client._make_request("GET", "/test/endpoint")

        assert result == {"result": "success"}
        assert mock_get.call_count == 2

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_connection_error_retries(self, mock_get):
        """Test that connection error triggers retry."""
        mock_get.side_effect = [ConnectionError("Connection failed"), Mock(
            json=Mock(return_value={"result": "success"}),
            raise_for_status=Mock()
        )]

        client = PIAClient()
        result = client._make_request("GET", "/test/endpoint")

        assert result == {"result": "success"}
        assert mock_get.call_count == 2

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_timeout_max_retries_exceeded(self, mock_get):
        """Test that timeout after max retries raises NetworkError."""
        mock_get.side_effect = Timeout("Request timed out")

        client = PIAClient()

        with pytest.raises(NetworkError, match="Failed to reach PIA API"):
            client._make_request("GET", "/test/endpoint")

        # Should have tried initial + 1 retry
        assert mock_get.call_count == 2

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_http_401_raises_authentication_error(self, mock_get):
        """Test that HTTP 401 raises AuthenticationError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        client = PIAClient()

        with pytest.raises(AuthenticationError):
            client._make_request("GET", "/test/endpoint")

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_http_500_raises_api_error(self, mock_get):
        """Test that HTTP 500 raises APIError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        client = PIAClient()

        with pytest.raises(APIError, match="PIA API error"):
            client._make_request("GET", "/test/endpoint")

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_invalid_json_response(self, mock_get):
        """Test that invalid JSON response raises APIError."""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PIAClient()

        with pytest.raises(APIError, match="Invalid JSON in response"):
            client._make_request("GET", "/test/endpoint")

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_unsupported_method(self, mock_get):
        """Test that unsupported HTTP method raises ValueError."""
        client = PIAClient()

        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            client._make_request("DELETE", "/test/endpoint")

    @patch("pia_nm.api_client.requests.Session.get")
    def test_make_request_includes_timeout(self, mock_get):
        """Test that requests include timeout parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PIAClient()
        client._make_request("GET", "/test/endpoint")

        # Verify timeout was passed
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 10


class TestErrorHandling:
    """Test error handling and exception hierarchy."""

    def test_authentication_error_is_api_error(self):
        """Test that AuthenticationError is subclass of PIAAPIError."""
        assert issubclass(AuthenticationError, Exception)

    def test_network_error_is_api_error(self):
        """Test that NetworkError is subclass of PIAAPIError."""
        assert issubclass(NetworkError, Exception)

    def test_api_error_is_api_error(self):
        """Test that APIError is subclass of PIAAPIError."""
        assert issubclass(APIError, Exception)

    def test_exception_messages_preserved(self):
        """Test that exception messages are preserved."""
        msg = "Test error message"
        exc = AuthenticationError(msg)
        assert str(exc) == msg

        exc = NetworkError(msg)
        assert str(exc) == msg

        exc = APIError(msg)
        assert str(exc) == msg


class TestIntegration:
    """Integration tests for API client."""

    @patch("pia_nm.api_client.requests.Session.get")
    @patch("pia_nm.api_client.requests.Session.post")
    def test_full_authentication_and_key_registration_flow(self, mock_post, mock_get):
        """Test complete flow: authenticate, get regions, register key."""
        # Mock authentication
        auth_response = Mock()
        auth_response.json.return_value = {"token": "test_token_123"}
        auth_response.raise_for_status = Mock()

        # Mock regions query
        regions_response = Mock()
        regions_response.json.return_value = {
            "regions": [
                {
                    "id": "us-east",
                    "name": "US East",
                    "country": "US",
                    "dns": "10.0.0.242",
                    "port_forward": False,
                    "servers": {"wg": [{"ip": "192.0.2.1", "cn": "us-east", "port": 1337}]},
                }
            ]
        }
        regions_response.raise_for_status = Mock()

        # Mock key registration
        register_response = Mock()
        register_response.json.return_value = {
            "status": "OK",
            "server_key": "server_key_123",
            "server_ip": "10.10.10.1",
            "server_port": 1337,
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }
        register_response.raise_for_status = Mock()

        # Set up mock responses
        mock_get.side_effect = [auth_response, regions_response]
        mock_post.return_value = register_response

        client = PIAClient()

        # Authenticate
        token = client.authenticate("user", "pass")
        assert token == "test_token_123"

        # Get regions
        regions = client.get_regions()
        assert len(regions) == 1
        assert regions[0]["id"] == "us-east"

        # Register key
        result = client.register_key(token, "client_pubkey", "us-east")
        assert result["status"] == "OK"
        assert result["peer_ip"] == "10.20.30.40"

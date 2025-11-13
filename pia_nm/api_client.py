"""PIA API client for authentication and server management.

This module handles all communication with PIA's API endpoints:
- Authentication with username/password
- Querying available regions and servers
- Registering WireGuard public keys
"""

import base64
import logging
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)

# API configuration
DEFAULT_BASE_URL = "https://www.privateinternetaccess.com"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 1  # Single immediate retry on network failures


class PIAAPIError(Exception):
    """Base exception for PIA API errors."""

    pass


class AuthenticationError(PIAAPIError):
    """Authentication with PIA failed."""

    pass


class NetworkError(PIAAPIError):
    """Network communication with PIA failed."""

    pass


class APIError(PIAAPIError):
    """PIA API returned an error response."""

    pass


class PIAClient:
    """Client for interacting with PIA API endpoints."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        """Initialize PIA API client.

        Args:
            base_url: Base URL for PIA API. Defaults to production endpoint.
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        logger.debug(f"Initialized PIAClient with base_url: {self.base_url}")

    def _validate_response_structure(
        self, response_data: Any, required_keys: List[str]
    ) -> None:
        """Validate that response contains required keys.

        Args:
            response_data: Response data to validate
            required_keys: List of required keys

        Raises:
            APIError: If required keys are missing
        """
        if not isinstance(response_data, dict):
            raise APIError(f"Expected dict response, got {type(response_data)}")

        missing_keys = [key for key in required_keys if key not in response_data]
        if missing_keys:
            raise APIError(f"Response missing required keys: {missing_keys}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """Make HTTP request to PIA API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without base URL)
            headers: Optional request headers
            json_data: Optional JSON body for POST requests
            retry_count: Internal retry counter

        Returns:
            Parsed JSON response

        Raises:
            NetworkError: If network communication fails
            APIError: If API returns error response
        """
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, headers=headers, timeout=REQUEST_TIMEOUT
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            try:
                return response.json()
            except ValueError as e:
                raise APIError(f"Invalid JSON in response: {e}")

        except (Timeout, ConnectionError) as e:
            # Retry once on network failures
            if retry_count < MAX_RETRIES:
                logger.warning(
                    f"Network error on {method} {endpoint}, retrying... ({retry_count + 1}/{MAX_RETRIES})"
                )
                return self._make_request(
                    method, endpoint, headers, json_data, retry_count + 1
                )
            else:
                logger.error(f"Network error after retries: {e}")
                raise NetworkError(f"Failed to reach PIA API: {e}")

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP {status_code} error from PIA API: {e}")

            if status_code == 401:
                raise AuthenticationError("Invalid credentials or expired token")
            else:
                raise APIError(f"PIA API error ({status_code}): {e}")

        except RequestException as e:
            logger.error(f"Request error: {e}")
            raise NetworkError(f"Request failed: {e}")

    def authenticate(self, username: str, password: str) -> str:
        """Authenticate with PIA and return auth token.

        Args:
            username: PIA account username
            password: PIA account password

        Returns:
            Authentication token for use in subsequent requests

        Raises:
            AuthenticationError: If authentication fails
            NetworkError: If network communication fails
        """
        logger.info("Authenticating with PIA API")

        # Create Basic Auth header
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode("ascii")

        headers = {"Authorization": f"Basic {encoded}"}

        try:
            response = self._make_request(
                "GET", "/api/client/v2/token", headers=headers
            )

            self._validate_response_structure(response, ["token"])

            token = response.get("token")
            if not token:
                raise AuthenticationError("No token in response")

            logger.info("Authentication successful")
            return token

        except (AuthenticationError, NetworkError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

    def get_regions(self) -> List[Dict[str, Any]]:
        """Query PIA API for available regions and servers.

        Returns:
            List of region dictionaries with details

        Raises:
            NetworkError: If network communication fails
            APIError: If API returns error response
        """
        logger.info("Querying available regions from PIA API")

        try:
            response = self._make_request("GET", "/api/client/v2/regions")

            self._validate_response_structure(response, ["regions"])

            regions = response.get("regions", [])

            if not isinstance(regions, list):
                raise APIError("'regions' field is not a list")

            logger.info(f"Retrieved {len(regions)} regions from PIA API")
            return regions

        except (NetworkError, APIError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying regions: {e}")
            raise APIError(f"Failed to query regions: {e}")

    def register_key(
        self, token: str, pubkey: str, region_id: str
    ) -> Dict[str, Any]:
        """Register WireGuard public key with PIA servers.

        Args:
            token: Authentication token from authenticate()
            pubkey: WireGuard public key (base64-encoded)
            region_id: Region identifier (e.g., 'us-east')

        Returns:
            Dictionary with connection details:
                - server_key: Server's WireGuard public key
                - server_ip: VPN server IP address
                - server_port: VPN server port
                - peer_ip: Assigned client IP address
                - dns_servers: List of DNS server IPs

        Raises:
            AuthenticationError: If token is invalid
            NetworkError: If network communication fails
            APIError: If API returns error response
        """
        logger.info(f"Registering WireGuard key for region: {region_id}")

        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }

        json_data = {"pubkey": pubkey, "region_id": region_id}

        try:
            response = self._make_request(
                "POST",
                "/api/client/v2/ephemeral/wireguard/register",
                headers=headers,
                json_data=json_data,
            )

            self._validate_response_structure(
                response,
                ["status", "server_key", "server_ip", "server_port", "peer_ip", "dns_servers"],
            )

            status = response.get("status")
            if status != "OK":
                raise APIError(f"Key registration failed with status: {status}")

            logger.info(f"Successfully registered key for region: {region_id}")
            return response

        except AuthenticationError:
            raise
        except (NetworkError, APIError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error registering key: {e}")
            raise APIError(f"Failed to register key: {e}")

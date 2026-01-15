"""
PIA API client for authentication and server management.

This module handles all communication with PIA's API endpoints:
- Authentication with username/password
- Querying available regions and servers
- Registering WireGuard public keys

Copyright (C) 2025 PIA-NM Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import base64
import json
import logging
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError as RequestsConnectionError,
)

logger = logging.getLogger(__name__)

# API configuration
DEFAULT_BASE_URL = "https://www.privateinternetaccess.com"
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 1  # Single immediate retry on network failures
PIA_CERT_URL = "https://www.privateinternetaccess.com/openvpn/ca.rsa.4096.crt"
PIA_CERT_PATH = Path.home() / ".config/pia-nm/ca.rsa.4096.crt"


class PIAAPIError(Exception):
    """Base exception for PIA API errors."""


class AuthenticationError(PIAAPIError):
    """Authentication with PIA failed."""


class NetworkError(PIAAPIError):
    """Network communication with PIA failed."""


class APIError(PIAAPIError):
    """PIA API returned an error response."""


class PIAClient:
    """Client for interacting with PIA API endpoints."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        """Initialize PIA API client.

        Args:
            base_url: Base URL for PIA API. Defaults to production endpoint.
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._ensure_ca_cert()
        logger.debug("Initialized PIAClient with base_url: %s", self.base_url)

    def _ensure_ca_cert(self) -> None:
        """Ensure PIA CA certificate is available locally.

        Downloads and caches PIA's CA certificate for SSL verification.
        """
        if PIA_CERT_PATH.exists():
            logger.debug("Using cached PIA CA certificate")
            return

        logger.info("Downloading PIA CA certificate")
        try:
            response = requests.get(PIA_CERT_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Ensure directory exists
            PIA_CERT_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Write certificate
            PIA_CERT_PATH.write_text(response.text)
            PIA_CERT_PATH.chmod(0o644)

            logger.info("PIA CA certificate cached at %s", PIA_CERT_PATH)

        except Exception as e:
            logger.warning("Failed to download PIA CA certificate: %s", e)
            logger.warning("SSL verification will be disabled for key registration")

    def _validate_response_structure(self, response_data: Any, required_keys: List[str]) -> None:
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
                response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            elif method.upper() == "POST":
                response = self.session.post(
                    url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise APIError("Response is not a JSON object")
                return data
            except ValueError as e:
                raise APIError(f"Invalid JSON in response: {e}") from e

        except (Timeout, RequestsConnectionError) as e:
            # Retry once on network failures
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Network error on %s %s, retrying... (%d/%d)",
                    method,
                    endpoint,
                    retry_count + 1,
                    MAX_RETRIES,
                )
                return self._make_request(method, endpoint, headers, json_data, retry_count + 1)
            else:
                logger.error("Network error after retries: %s", e)
                raise NetworkError(f"Failed to reach PIA API: {e}") from e

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error("HTTP %d error from PIA API: %s", status_code, e)

            if status_code == 401:
                raise AuthenticationError("Invalid credentials or expired token") from e
            else:
                raise APIError(f"PIA API error ({status_code}): {e}") from e

        except RequestException as e:
            logger.error("Request error: %s", e)
            raise NetworkError(f"Request failed: {e}") from e

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

        # Use form data for authentication (POST with form fields)
        form_data = {"username": username, "password": password}

        try:
            url = f"{self.base_url}/api/client/v2/token"
            response = self.session.post(url, data=form_data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise APIError("Response is not a JSON object")
            except ValueError as e:
                raise APIError(f"Invalid JSON in response: {e}") from e

            self._validate_response_structure(data, ["token"])

            token = data.get("token")
            if not isinstance(token, str) or not token:
                raise AuthenticationError("No token in response")

            logger.info("Authentication successful")
            return token

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error("HTTP %d error from PIA API: %s", status_code, e)

            if status_code == 401:
                raise AuthenticationError("Invalid credentials or expired token") from e
            else:
                raise APIError(f"PIA API error ({status_code}): {e}") from e

        except (Timeout, RequestsConnectionError) as e:
            logger.error("Network error: %s", e)
            raise NetworkError(f"Failed to reach PIA API: {e}") from e

        except RequestException as e:
            logger.error("Request error: %s", e)
            raise NetworkError(f"Request failed: {e}") from e

        except (AuthenticationError, NetworkError):
            raise
        except Exception as e:
            logger.error("Unexpected error during authentication: %s", e)
            raise AuthenticationError(f"Authentication failed: {e}") from e

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
            url = "https://serverlist.piaservers.net/vpninfo/servers/v6"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            try:
                # The endpoint returns multiple JSON objects, get only the first line
                first_line = response.text.split("\n")[0]
                data = json.loads(first_line)
                if not isinstance(data, dict):
                    raise APIError("Response is not a JSON object")
            except ValueError as e:
                raise APIError(f"Invalid JSON in response: {e}") from e

            self._validate_response_structure(data, ["regions"])

            regions = data.get("regions", [])

            if not isinstance(regions, list):
                raise APIError("'regions' field is not a list")

            logger.info("Retrieved %d regions from PIA API", len(regions))
            return regions

        except requests.exceptions.HTTPError as e:
            logger.error("HTTP error querying regions: %s", e)
            raise APIError(f"Failed to query regions: {e}") from e

        except (Timeout, RequestsConnectionError) as e:
            logger.error("Network error querying regions: %s", e)
            raise NetworkError(f"Failed to reach region server: {e}") from e

        except RequestException as e:
            logger.error("Request error: %s", e)
            raise NetworkError(f"Request failed: {e}") from e

        except (NetworkError, APIError):
            raise
        except Exception as e:
            logger.error("Unexpected error querying regions: %s", e)
            raise APIError(f"Failed to query regions: {e}") from e

    def register_key(
        self, token: str, pubkey: str, server_hostname: str, server_ip: str
    ) -> Dict[str, Any]:
        """Register WireGuard public key with PIA server.

        Args:
            token: Authentication token from authenticate()
            pubkey: WireGuard public key (base64-encoded)
            server_hostname: Server hostname (CN from certificate, e.g., 'tokyo401')
            server_ip: Server IP address

        Returns:
            Dictionary with connection details:
                - status: Should be "OK"
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
        logger.info("Registering WireGuard key with server: %s (%s)", server_hostname, server_ip)

        try:
            # GET request to server's /addKey endpoint with query parameters
            # Use hostname in URL for proper SNI, but override DNS resolution to use server_ip
            # This mimics curl's --connect-to behavior
            url = f"https://{server_hostname}:1337/addKey"
            params = {"pt": token, "pubkey": pubkey}

            # Use PIA's CA certificate for verification if available
            verify = str(PIA_CERT_PATH) if PIA_CERT_PATH.exists() else True

            # Create a custom session with DNS override for this specific request
            # We need to resolve server_hostname to server_ip
            from requests.adapters import HTTPAdapter
            from urllib3.util.connection import create_connection
            import socket

            # Store original getaddrinfo
            original_getaddrinfo = socket.getaddrinfo

            def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
                # Override DNS resolution for our specific hostname
                if host == server_hostname:
                    # Return the server_ip instead of doing DNS lookup
                    return original_getaddrinfo(server_ip, port, family, type, proto, flags)
                return original_getaddrinfo(host, port, family, type, proto, flags)

            # Temporarily replace getaddrinfo
            socket.getaddrinfo = custom_getaddrinfo

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    verify=verify,
                )
            finally:
                # Restore original getaddrinfo
                socket.getaddrinfo = original_getaddrinfo
            response.raise_for_status()

            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise APIError("Response is not a JSON object")
            except ValueError as e:
                raise APIError(f"Invalid JSON in response: {e}") from e

            self._validate_response_structure(
                data, ["status", "server_key", "server_ip", "server_port", "peer_ip"]
            )

            status = data.get("status")
            if status != "OK":
                raise APIError(f"Key registration failed with status: {status}")

            logger.info("Successfully registered key with server: %s", server_hostname)
            return data

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error("HTTP %d error registering key: %s", status_code, e)

            if status_code == 401:
                raise AuthenticationError("Invalid token") from e
            else:
                raise APIError(f"Key registration failed ({status_code}): {e}") from e

        except (Timeout, RequestsConnectionError) as e:
            logger.error("Network error registering key: %s", e)
            raise NetworkError(f"Failed to reach server: {e}") from e

        except RequestException as e:
            logger.error("Request error: %s", e)
            raise NetworkError(f"Request failed: {e}") from e

        except (AuthenticationError, NetworkError, APIError):
            raise
        except Exception as e:
            logger.error("Unexpected error registering key: %s", e)
            raise APIError(f"Failed to register key: {e}") from e

# Contributing to pia-nm

Thank you for your interest in contributing to pia-nm! This document provides guidelines for development, testing, and submitting contributions.

## Getting Started

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/your-username/pia-nm.git
cd pia-nm

# Add upstream remote
git remote add upstream https://github.com/original-owner/pia-nm.git
```

### Setup Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### Verify Setup

```bash
# Check installation
pia-nm --help

# Run tests
pytest

# Check code quality
black --check pia_nm/
mypy pia_nm/
pylint pia_nm/
```

## Development Workflow

### Create a Feature Branch

```bash
# Update main branch
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
```

### Code Style

**Follow PEP 8:**
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use meaningful variable names

**Type Hints:**
- Add type hints to all functions
- Use Python 3.9+ typing syntax
- Example:
  ```python
  def authenticate(username: str, password: str) -> str:
      """Authenticate with PIA and return token."""
      pass
  ```

**Docstrings:**
- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Example:
  ```python
  def refresh_region(region_id: str) -> bool:
      """Refresh token for a specific region.
      
      Args:
          region_id: The region identifier (e.g., 'us-east')
          
      Returns:
          True if refresh successful, False otherwise
          
      Raises:
          ValueError: If region_id is invalid
          AuthenticationError: If PIA authentication fails
      """
      pass
  ```

### Error Handling

- Use specific exception types
- Log errors with context
- Never log credentials or tokens
- Provide helpful error messages

Example:
```python
try:
    result = api_client.authenticate(username, password)
except AuthenticationError as e:
    logger.error(f"Authentication failed: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Logging

- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- Never log sensitive data (passwords, tokens, keys)
- Include context in log messages

Example:
```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Refreshing token for region: {region_id}")
logger.debug(f"Using endpoint: {endpoint}")
logger.warning(f"Token refresh delayed: {reason}")
logger.error(f"Failed to update profile: {error}")
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api_client.py

# Run specific test
pytest tests/test_api_client.py::test_authenticate_success

# Run with coverage
pytest --cov=pia_nm

# Run with verbose output
pytest -v
```

### Writing Tests

- Write tests for new functionality
- Focus on core logic, not edge cases
- Use mocks for external dependencies
- Keep tests minimal and focused

Example:
```python
import pytest
from unittest.mock import Mock, patch
from pia_nm.api_client import PIAClient

@patch('requests.get')
def test_authenticate_success(mock_get):
    """Test successful authentication."""
    mock_response = Mock()
    mock_response.json.return_value = {"token": "test_token"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    client = PIAClient()
    token = client.authenticate("user", "pass")
    
    assert token == "test_token"
    mock_get.assert_called_once()
```

### Test Coverage

Aim for good coverage of core functionality:
- API client methods
- Configuration management
- NetworkManager operations
- Error handling

Don't over-test:
- Edge cases
- Third-party library behavior
- Simple getters/setters

## Code Quality

### Format Code

```bash
# Format with Black
black pia_nm/

# Check formatting without changes
black --check pia_nm/
```

### Type Checking

```bash
# Run mypy
mypy pia_nm/

# Check specific file
mypy pia_nm/api_client.py
```

### Linting

```bash
# Run pylint
pylint pia_nm/

# Check specific file
pylint pia_nm/api_client.py
```

### Before Submitting

Run the complete quality check:

```bash
# Format
black pia_nm/

# Type check
mypy pia_nm/

# Lint
pylint pia_nm/

# Test
pytest

# All together
black pia_nm/ && mypy pia_nm/ && pylint pia_nm/ && pytest
```

## Commit Messages

Write clear, descriptive commit messages:

```
Short summary (50 chars or less)

Longer explanation if needed. Wrap at 72 characters.
Explain what and why, not how.

Fixes #123
```

Examples:
```
Add support for port forwarding regions

Implement filtering in list-regions command to show only
regions with port forwarding support. Adds --port-forwarding
flag to pia-nm list-regions.

Fixes #45
```

```
Fix token refresh not updating active connections

Use nmcli connection modify instead of delete/recreate to
preserve active connections during token refresh.

Fixes #67
```

## Pull Request Process

1. **Update your branch:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create Pull Request:**
   - Go to GitHub and create a PR
   - Write a clear description of changes
   - Reference any related issues
   - Include before/after examples if applicable

4. **PR Description Template:**
   ```markdown
   ## Description
   Brief description of what this PR does.

   ## Changes
   - Change 1
   - Change 2
   - Change 3

   ## Testing
   How to test these changes.

   ## Checklist
   - [ ] Code formatted with Black
   - [ ] Type hints added
   - [ ] Tests written and passing
   - [ ] No sensitive data in logs
   - [ ] Documentation updated

   Fixes #123
   ```

5. **Address Feedback:**
   - Make requested changes
   - Push updates to your branch
   - Respond to comments

## Code Review Checklist

Before submitting, verify:

- [ ] **Type Hints**: All functions have type hints
- [ ] **Docstrings**: All public functions have docstrings
- [ ] **Error Handling**: Specific exception types, proper logging
- [ ] **Logging**: No credentials/tokens/keys logged
- [ ] **File Permissions**: Sensitive files have 0600 permissions
- [ ] **Subprocess**: All subprocess calls use `check=True`
- [ ] **Input Validation**: User input is validated
- [ ] **Tests**: New functionality has tests
- [ ] **Code Quality**: Passes Black, mypy, pylint
- [ ] **No Hardcoding**: No hardcoded paths or credentials
- [ ] **Security**: No security issues introduced
- [ ] **Documentation**: README/docs updated if needed

## Common Contribution Types

### Bug Fixes

1. Create issue describing the bug
2. Create branch: `git checkout -b fix/bug-description`
3. Fix the bug
4. Add test that reproduces the bug
5. Verify test passes with fix
6. Submit PR with "Fixes #123" in description

### New Features

1. Discuss feature in an issue first
2. Create branch: `git checkout -b feature/feature-name`
3. Implement feature
4. Add tests for new functionality
5. Update documentation
6. Submit PR with description of feature

### Documentation

1. Create branch: `git checkout -b docs/improvement`
2. Update documentation
3. Submit PR with description of changes

### Code Quality

1. Create branch: `git checkout -b refactor/improvement`
2. Refactor code
3. Ensure tests still pass
4. Submit PR with description of improvements

## Project Structure

```
pia-nm/
├── pia_nm/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── cli.py               # CLI interface
│   ├── config.py            # Configuration management
│   ├── api_client.py        # PIA API client
│   ├── wireguard.py         # WireGuard key management
│   ├── network_manager.py   # NetworkManager interface
│   └── systemd_manager.py   # Systemd integration
├── tests/
│   ├── test_api_client.py
│   ├── test_config.py
│   ├── test_network_manager.py
│   └── test_wireguard.py
├── systemd/
│   ├── pia-nm-refresh.service
│   └── pia-nm-refresh.timer
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── LICENSE
└── .gitignore
```

## Key Modules

### api_client.py
- PIA API interactions
- Authentication
- Region queries
- Key registration

### config.py
- Configuration file management
- Keyring integration
- Credential storage

### wireguard.py
- WireGuard key generation
- Key storage and loading
- Key rotation logic

### network_manager.py
- NetworkManager profile creation
- Profile updates
- Connection status checking

### systemd_manager.py
- Systemd unit installation
- Timer management
- Service configuration

## Security Considerations

When contributing, keep security in mind:

- **Never log credentials**: Passwords, tokens, keys should never be logged
- **Use HTTPS**: All API communication must use HTTPS
- **Validate input**: Validate all user input
- **File permissions**: Sensitive files should have 0600 permissions
- **Error messages**: Don't leak sensitive information in error messages
- **Dependencies**: Be cautious when adding new dependencies

## Questions?

- Check existing issues and PRs
- Read the code and comments
- Ask in a new issue
- Check [FAQ.md](FAQ.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## License

By contributing to pia-nm, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Report issues professionally

Thank you for contributing to pia-nm!

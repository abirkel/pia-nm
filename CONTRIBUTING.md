# Contributing to pia-nm

Thanks for your interest in contributing! This guide covers development setup, code standards, and the contribution process.

## Development Setup

```bash
# Fork and clone
git clone https://github.com/your-username/pia-nm.git
cd pia-nm

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Verify setup
pia-nm --help
pytest
```

## Code Standards

### Style Guidelines

- Follow PEP 8 (4 spaces, 100 char lines)
- Add type hints to all functions
- Use Google-style docstrings
- Never log credentials, tokens, or keys

Example:
```python
def refresh_region(region_id: str) -> bool:
    """Refresh token for a specific region.
    
    Args:
        region_id: Region identifier (e.g., 'us-east')
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Refreshing token for region: {region_id}")
    # Implementation
```

### Error Handling

Use specific exceptions and provide helpful messages:

```python
try:
    result = api_client.authenticate(username, password)
except AuthenticationError as e:
    logger.error(f"Authentication failed: {e}")
    raise
```

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=pia_nm

# Specific test
pytest tests/test_api_client.py::test_authenticate_success
```

Write tests for new functionality using mocks for external dependencies:

```python
@patch('requests.get')
def test_authenticate_success(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"token": "test_token"}
    mock_get.return_value = mock_response
    
    client = PIAClient()
    token = client.authenticate("user", "pass")
    
    assert token == "test_token"
```

## Code Quality

Before submitting, run:

```bash
black pia_nm/        # Format
mypy pia_nm/         # Type check
pylint pia_nm/       # Lint
pytest               # Test
```

## Submitting Changes

Write clear commit messages:

```
Short summary (50 chars or less)

Longer explanation if needed. Explain what and why.

Fixes #123
```

Create a pull request with:
- Clear description of changes
- Reference to related issues
- Test results

PR checklist:
- [ ] Code formatted with Black
- [ ] Type hints added
- [ ] Tests passing
- [ ] No sensitive data in logs
- [ ] Documentation updated

## Security Considerations

- Never log credentials, tokens, or keys
- Use HTTPS for all API communication
- Validate all user input
- Set restrictive file permissions (0600 for sensitive files)
- Don't leak sensitive information in error messages

## Questions?

Open an issue on GitHub or check existing issues and documentation.

## License

By contributing, you agree that your contributions will be licensed under GPLv3+.

Thanks for contributing to pia-nm!

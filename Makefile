.PHONY: help pex install-pex clean test lint format

help:
	@echo "Available targets:"
	@echo "  pex          - Build PEX executable (for development)"
	@echo "  install-pex  - Build and install PEX to ~/.local/bin"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code with black"
	@echo "  clean        - Remove build artifacts"
	@echo ""
	@echo "Note: Regular users should download pre-built PEX from GitHub releases"

pex:
	@echo "Building PEX executable..."
	@echo "Note: PyGObject is excluded - it will use the system version"
	@pex . \
		-r <(echo "requests>=2.31.0" && echo "keyring>=24.0.0" && echo "PyYAML>=6.0") \
		-c pia-nm \
		-o pia-nm.pex \
		--python-shebang "/usr/bin/env python3" \
		--inherit-path
	@chmod +x pia-nm.pex
	@echo "✓ Built: pia-nm.pex"

install-pex: pex
	@echo "Installing to ~/.local/bin/pia-nm..."
	@mkdir -p ~/.local/bin
	@cp pia-nm.pex ~/.local/bin/pia-nm
	@echo "✓ Installed to ~/.local/bin/pia-nm"
	@echo ""
	@echo "Make sure ~/.local/bin is in your PATH"

clean:
	rm -rf build/ dist/ *.egg-info pia-nm.pex
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	python3 -m pytest tests/

lint:
	python3 -m pylint pia_nm/
	python3 -m mypy pia_nm/

format:
	python3 -m black pia_nm/ tests/

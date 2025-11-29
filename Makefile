.PHONY: help rpm srpm clean test lint format

help:
	@echo "Available targets:"
	@echo "  rpm          - Build RPM package (requires rpmbuild)"
	@echo "  srpm         - Build source RPM"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code with black"
	@echo "  clean        - Remove build artifacts"
	@echo ""
	@echo "Note: Regular users should download pre-built RPMs from GitHub releases"

rpm: srpm
	@echo "Building RPM package..."
	@rpmbuild --rebuild pia-nm-*.src.rpm
	@echo "✓ RPM built in ~/rpmbuild/RPMS/noarch/"

srpm:
	@echo "Building source RPM..."
	@mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	@VERSION=$$(grep '^version = ' pyproject.toml | cut -d'"' -f2); \
	mkdir -p pia-nm-$$VERSION; \
	cp -r pia_nm/ pyproject.toml README.md LICENSE INSTALL.md COMMANDS.md TROUBLESHOOTING.md pia-nm-$$VERSION/; \
	tar czf ~/rpmbuild/SOURCES/pia-nm-$$VERSION.tar.gz pia-nm-$$VERSION/; \
	rm -rf pia-nm-$$VERSION; \
	cp pia-nm.spec ~/rpmbuild/SPECS/; \
	rpmbuild -bs ~/rpmbuild/SPECS/pia-nm.spec
	@echo "✓ Source RPM built in ~/rpmbuild/SRPMS/"

clean:
	rm -rf build/ dist/ *.egg-info *.tar.gz pia-nm-*/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	python3 -m pytest tests/

lint:
	python3 -m pylint pia_nm/
	python3 -m mypy pia_nm/

format:
	python3 -m black pia_nm/ tests/



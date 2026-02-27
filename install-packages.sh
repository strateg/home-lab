#!/bin/bash
# Install Missing Packages for Tool Version Management
# Run this in your Python environment (.venv)

echo "Installing missing Python packages..."
echo "======================================"

# Install pydantic
echo ""
echo "[1/4] Installing pydantic..."
pip install pydantic

# Install pyyaml (if not already installed)
echo ""
echo "[2/4] Checking pyyaml..."
pip install pyyaml

# Install packaging (required by version validator)
echo ""
echo "[3/4] Installing packaging..."
pip install packaging

# Verify installations
echo ""
echo "[4/4] Verifying installations..."
python -c "import pydantic; print(f'✓ pydantic {pydantic.__version__}')"
python -c "import yaml; print(f'✓ pyyaml installed')"
python -c "import packaging; print(f'✓ packaging installed')"

echo ""
echo "======================================"
echo "✓ All packages installed successfully!"
echo ""
echo "Next step: Run version validator"
echo "  python topology-tools/validators/version_validator.py --check-all"

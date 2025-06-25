d#!/bin/bash
# Claude Code Memory Solution - Global Installer
# Creates a global wrapper script for the indexer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the absolute path to the memory project directory
MEMORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDEXER_PATH="$MEMORY_DIR/indexer.py"
VENV_PATH="$MEMORY_DIR/.venv"
WRAPPER_PATH="/usr/local/bin/claude-indexer"

echo -e "${BLUE}Claude Code Memory Solution - Global Installer${NC}"
echo "========================================"

# Check if indexer.py exists
if [[ ! -f "$INDEXER_PATH" ]]; then
    echo -e "${RED}Error: indexer.py not found at $INDEXER_PATH${NC}"
    exit 1
fi

# Check if virtual environment exists
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Please run: python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

# Check if /usr/local/bin exists
if [[ ! -d "/usr/local/bin" ]]; then
    echo -e "${YELLOW}Creating /usr/local/bin directory...${NC}"
    sudo mkdir -p /usr/local/bin
fi

# Create the wrapper script
echo -e "${BLUE}Creating global wrapper script at $WRAPPER_PATH${NC}"

sudo tee "$WRAPPER_PATH" > /dev/null << EOF
#!/bin/bash
# Claude Code Memory Solution - Global Wrapper
# Auto-activates virtual environment and runs indexer

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MEMORY_DIR="$MEMORY_DIR"
INDEXER_PATH="$INDEXER_PATH"
VENV_PATH="$VENV_PATH"

# Check if files still exist
if [[ ! -f "\$INDEXER_PATH" ]]; then
    echo -e "\${RED}Error: indexer.py not found at \$INDEXER_PATH${NC}"
    echo -e "\${YELLOW}The memory project may have been moved or deleted.${NC}"
    exit 1
fi

if [[ ! -d "\$VENV_PATH" ]]; then
    echo -e "\${RED}Error: Virtual environment not found at \$VENV_PATH${NC}"
    exit 1
fi

# Activate virtual environment and run indexer
source "\$VENV_PATH/bin/activate"

# Check if we're in a Python project (has .py files)
if [[ "\$1" == "--project" && "\$2" == "." ]]; then
    if [[ ! -f "*.py" ]] && [[ ! \$(find . -name "*.py" -type f 2>/dev/null | head -1) ]]; then
        echo -e "\${YELLOW}Warning: No Python files found in current directory${NC}"
        echo -e "\${YELLOW}Make sure you're in a Python project directory${NC}"
    fi
fi

# Run the indexer with all passed arguments
exec python "\$INDEXER_PATH" "\$@"
EOF

# Make the wrapper executable
sudo chmod +x "$WRAPPER_PATH"

# Verify installation
if [[ -x "$WRAPPER_PATH" ]]; then
    echo -e "${GREEN}✅ Installation successful!${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  claude-indexer --project /path/to/project --collection project-name"
    echo "  claude-indexer --project . --collection current-project"
    echo "  claude-indexer --help"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  # Index current directory"
    echo "  claude-indexer --project . --collection my-project"
    echo ""
    echo "  # Index specific project with incremental updates"
    echo "  claude-indexer --project /path/to/project --collection name --incremental"
    echo ""
    echo "  # Generate commands for debugging"
    echo "  claude-indexer --project . --collection test --generate-commands"
    echo ""
    echo -e "${GREEN}You can now use 'claude-indexer' from any directory!${NC}"
else
    echo -e "${RED}❌ Installation failed${NC}"
    exit 1
fi
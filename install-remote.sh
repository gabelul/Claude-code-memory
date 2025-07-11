#!/bin/bash
# Claude Code Memory Solution - Remote Installer
# Automatically clones from GitHub and sets up everything

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/gabelul/mcp-qdrant-memory.git"
INSTALL_DIR="$HOME/mcp-qdrant-memory"
PYTHON_VERSION="python3.12"

echo -e "${BLUE}Claude Code Memory Solution - Remote Installer${NC}"
echo "=============================================="

# Check if Python 3.12 is available
if ! command -v $PYTHON_VERSION &> /dev/null; then
    echo -e "${RED}Error: $PYTHON_VERSION is not installed${NC}"
    echo -e "${YELLOW}Please install Python 3.12 first${NC}"
    exit 1
fi

# Check if git is available
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed${NC}"
    echo -e "${YELLOW}Please install git first${NC}"
    exit 1
fi

# Clone or update repository
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${YELLOW}Directory $INSTALL_DIR already exists${NC}"
    echo -e "${BLUE}Updating existing repository...${NC}"
    cd "$INSTALL_DIR"
    git pull origin master
else
    echo -e "${BLUE}Cloning repository to $INSTALL_DIR...${NC}"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Set up virtual environment
VENV_PATH="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    $PYTHON_VERSION -m venv "$VENV_PATH"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r requirements.txt

# Install claude_indexer package in editable mode
echo -e "${BLUE}Installing claude_indexer package...${NC}"
"$VENV_PATH/bin/pip" install -e .

# Verify installation
if ! "$VENV_PATH/bin/python" -c "import claude_indexer" 2>/dev/null; then
    echo -e "${RED}Error: Failed to install claude_indexer package${NC}"
    exit 1
fi
echo -e "${GREEN}✅ claude_indexer package installed successfully${NC}"

# Create global wrapper
WRAPPER_PATH="/usr/local/bin/claude-indexer"
PACKAGE_PATH="$INSTALL_DIR/claude_indexer"

# Check if /usr/local/bin exists
if [[ ! -d "/usr/local/bin" ]]; then
    echo -e "${YELLOW}Creating /usr/local/bin directory...${NC}"
    if ! mkdir -p /usr/local/bin 2>/dev/null; then
        echo -e "${YELLOW}Need sudo permissions to create /usr/local/bin${NC}"
        sudo mkdir -p /usr/local/bin
    fi
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

MEMORY_DIR="$INSTALL_DIR"
PACKAGE_PATH="$PACKAGE_PATH"
VENV_PATH="$VENV_PATH"

# Check if files still exist
if [[ ! -d "\$PACKAGE_PATH" ]]; then
    echo -e "\${RED}Error: claude_indexer package not found at \$PACKAGE_PATH\${NC}"
    echo -e "\${YELLOW}The memory project may have been moved or deleted.\${NC}"
    exit 1
fi

if [[ ! -d "\$VENV_PATH" ]]; then
    echo -e "\${RED}Error: Virtual environment not found at \$VENV_PATH\${NC}"
    exit 1
fi

# Use absolute python path instead of activating venv to avoid PATH conflicts
PYTHON_BIN="\$VENV_PATH/bin/python"

# Check if we're in a Python project (has .py files)
if [[ "\$1" == "--project" && "\$2" == "." ]]; then
    if [[ ! \$(find . -name "*.py" -type f 2>/dev/null | head -1) ]]; then
        echo -e "\${YELLOW}Warning: No Python files found in current directory${NC}"
        echo -e "\${YELLOW}Make sure you're in a Python project directory${NC}"
    fi
fi

# Run the indexer with all passed arguments
# Smart command detection and routing
if [[ "\$1" =~ ^(hooks|watch|service|search|file|add-mcp|chat|init)$ ]]; then
    # Advanced commands - pass through directly
    exec "\$PYTHON_BIN" -m claude_indexer "\$@"
elif [[ "\$1" == "index" ]]; then
    # Explicit index command - pass through
    exec "\$PYTHON_BIN" -m claude_indexer "\$@"
elif [[ "\$1" =~ ^--(help|version)$ ]]; then
    # Help and version commands
    exec "\$PYTHON_BIN" -m claude_indexer "\$@"
elif [[ "\$1" == "--help" || "\$1" == "-h" || "\$1" == "help" ]]; then
    # Help command variations
    exec "\$PYTHON_BIN" -m claude_indexer --help
elif [[ \$# -eq 0 ]]; then
    # No arguments - show help
    exec "\$PYTHON_BIN" -m claude_indexer --help
else
    # Basic indexing - use default index command for backward compatibility
    exec "\$PYTHON_BIN" -m claude_indexer index "\$@"
fi
EOF

# Make the wrapper executable
sudo chmod +x "$WRAPPER_PATH"

# Remove problematic venv binary that conflicts with global wrapper
VENV_CLAUDE_INDEXER="$VENV_PATH/bin/claude-indexer"
if [[ -f "$VENV_CLAUDE_INDEXER" ]]; then
    echo -e "${BLUE}Removing conflicting venv binary...${NC}"
    rm "$VENV_CLAUDE_INDEXER"
fi

# Verify installation
if [[ -x "$WRAPPER_PATH" ]]; then
    echo -e "${GREEN}✅ Installation successful!${NC}"
    echo ""
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  Repository: $INSTALL_DIR"
    echo "  Virtual env: $VENV_PATH"
    echo "  Global command: $WRAPPER_PATH"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  claude-indexer --project /path/to/project --collection project-name"
    echo "  claude-indexer --project . --collection current-project"
    echo "  claude-indexer --help"
    echo ""
    echo -e "${BLUE}Basic Examples:${NC}"
    echo "  # Index current directory"
    echo "  claude-indexer --project . --collection my-project"
    echo ""
    echo "  # Index with incremental updates"
    echo "  claude-indexer --project /path/to/project --collection name --incremental"
    echo ""
    echo "  # Generate commands for debugging"
    echo "  claude-indexer --project . --collection test --generate-commands"
    echo ""
    echo -e "${BLUE}Advanced Commands:${NC}"
    echo "  # File watching"
    echo "  claude-indexer watch start --project . --collection my-project"
    echo ""
    echo "  # Git hooks"
    echo "  claude-indexer hooks install --project . --collection my-project"
    echo ""
    echo "  # Search collections"
    echo "  claude-indexer search \"query\" --project . --collection my-project"
    echo ""
    echo "  # Add MCP server"
    echo "  claude-indexer add-mcp my-project"
    echo ""
    echo "  # Chat processing"
    echo "  claude-indexer chat index --project . --collection my-project"
    echo ""
    echo -e "${GREEN}You can now use 'claude-indexer' from any directory!${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Start Qdrant database: docker run -p 6333:6333 -v \$(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant"
    echo "2. Configure API keys in $INSTALL_DIR/settings.txt"
    echo "3. Test with: claude-indexer --project . --collection test"
else
    echo -e "${RED}❌ Installation failed${NC}"
    exit 1
fi
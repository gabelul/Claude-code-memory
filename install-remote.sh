#!/bin/bash
# Claude Code Memory Solution - Hybrid Remote Installer
# Automatically clones from GitHub and sets up both Python indexer and Node.js MCP server

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
MCP_SERVER_DIR="$INSTALL_DIR/mcp-qdrant-memory"

echo -e "${BLUE}Claude Code Memory Solution - Hybrid Remote Installer${NC}"
echo "=========================================================="

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check if Python 3.12 is available
if ! command -v $PYTHON_VERSION &> /dev/null; then
    echo -e "${RED}Error: $PYTHON_VERSION is not installed${NC}"
    echo -e "${YELLOW}Please install Python 3.12 first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3.12 found${NC}"

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo -e "${YELLOW}Please install Node.js first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js found ($(node --version))${NC}"

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed${NC}"
    echo -e "${YELLOW}Please install npm first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ npm found ($(npm --version))${NC}"

# Check if git is available
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed${NC}"
    echo -e "${YELLOW}Please install git first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ git found${NC}"

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

# ============================================
# PYTHON INDEXER SETUP
# ============================================
echo -e "${BLUE}Setting up Python indexer...${NC}"

# Set up virtual environment
VENV_PATH="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${BLUE}Creating Python virtual environment...${NC}"
    $PYTHON_VERSION -m venv "$VENV_PATH"
else
    echo -e "${GREEN}✅ Python virtual environment already exists${NC}"
fi

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r requirements.txt

# Install claude_indexer package in editable mode
echo -e "${BLUE}Installing claude_indexer package...${NC}"
"$VENV_PATH/bin/pip" install -e .

# Verify Python installation
if ! "$VENV_PATH/bin/python" -c "import claude_indexer" 2>/dev/null; then
    echo -e "${RED}Error: Failed to install claude_indexer package${NC}"
    exit 1
fi
echo -e "${GREEN}✅ claude_indexer package installed successfully${NC}"

# ============================================
# NODE.JS MCP SERVER SETUP
# ============================================
echo -e "${BLUE}Setting up Node.js MCP server...${NC}"

# Install Node.js dependencies
echo -e "${BLUE}Installing Node.js dependencies...${NC}"
cd "$MCP_SERVER_DIR"
npm install

# Build TypeScript
echo -e "${BLUE}Building TypeScript...${NC}"
npm run build

# Verify build
if [[ ! -f "$MCP_SERVER_DIR/dist/index.js" ]]; then
    echo -e "${RED}Error: TypeScript build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MCP server built successfully${NC}"

# Return to root directory
cd "$INSTALL_DIR"

# ============================================
# GLOBAL COMMAND WRAPPERS
# ============================================
echo -e "${BLUE}Setting up global command wrappers...${NC}"

# Create global wrapper for Python indexer
WRAPPER_PATH="/usr/local/bin/claude-indexer"
PACKAGE_PATH="$INSTALL_DIR/claude_indexer"
MCP_WRAPPER_PATH="/usr/local/bin/mcp-qdrant-memory"

# Check if /usr/local/bin exists
if [[ ! -d "/usr/local/bin" ]]; then
    echo -e "${YELLOW}Creating /usr/local/bin directory...${NC}"
    if ! mkdir -p /usr/local/bin 2>/dev/null; then
        echo -e "${YELLOW}Need sudo permissions to create /usr/local/bin${NC}"
        sudo mkdir -p /usr/local/bin
    fi
fi

# Create the Python indexer wrapper script
echo -e "${BLUE}Creating Python indexer wrapper at $WRAPPER_PATH${NC}"

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

# Make the Python indexer wrapper executable
sudo chmod +x "$WRAPPER_PATH"
echo -e "${GREEN}✅ Python indexer wrapper created${NC}"

# Create MCP server wrapper
echo -e "${BLUE}Creating MCP server wrapper at $MCP_WRAPPER_PATH${NC}"

sudo tee "$MCP_WRAPPER_PATH" > /dev/null << EOF
#!/bin/bash
# Claude Code Memory Solution - MCP Server Wrapper

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MCP_SERVER_DIR="$MCP_SERVER_DIR"

# Check if files still exist
if [[ ! -f "\$MCP_SERVER_DIR/dist/index.js" ]]; then
    echo -e "\${RED}Error: MCP server not found at \$MCP_SERVER_DIR/dist/index.js\${NC}"
    echo -e "\${YELLOW}The MCP server may have been moved or not built.\${NC}"
    exit 1
fi

# Run the MCP server with all passed arguments
exec node "\$MCP_SERVER_DIR/dist/index.js" "\$@"
EOF

# Make the MCP server wrapper executable
sudo chmod +x "$MCP_WRAPPER_PATH"
echo -e "${GREEN}✅ MCP server wrapper created${NC}"

# Remove problematic venv binary that conflicts with global wrapper
VENV_CLAUDE_INDEXER="$VENV_PATH/bin/claude-indexer"
if [[ -f "$VENV_CLAUDE_INDEXER" ]]; then
    echo -e "${BLUE}Removing conflicting venv binary...${NC}"
    rm "$VENV_CLAUDE_INDEXER"
fi

# ============================================
# ENVIRONMENT SETUP
# ============================================
echo -e "${BLUE}Setting up environment configuration...${NC}"

# Create settings file from template if it doesn't exist
SETTINGS_FILE="$INSTALL_DIR/settings.txt"
TEMPLATE_FILE="$INSTALL_DIR/settings.template.txt"

if [[ ! -f "$SETTINGS_FILE" && -f "$TEMPLATE_FILE" ]]; then
    echo -e "${BLUE}Creating settings.txt from template...${NC}"
    cp "$TEMPLATE_FILE" "$SETTINGS_FILE"
    echo -e "${YELLOW}Please configure your API keys in $SETTINGS_FILE${NC}"
fi

# Create MCP server .env file
MCP_ENV_FILE="$MCP_SERVER_DIR/.env"
if [[ ! -f "$MCP_ENV_FILE" ]]; then
    echo -e "${BLUE}Creating MCP server .env file...${NC}"
    cat > "$MCP_ENV_FILE" << EOF
# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=memory-project

# API Keys
OPENAI_API_KEY=
VOYAGE_API_KEY=
EOF
    echo -e "${YELLOW}Please configure your API keys in $MCP_ENV_FILE${NC}"
fi

# Verify installation
if [[ -x "$WRAPPER_PATH" && -x "$MCP_WRAPPER_PATH" ]]; then
    echo -e "${GREEN}✅ Hybrid installation successful!${NC}"
    echo ""
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  Repository: $INSTALL_DIR"
    echo "  Python env: $VENV_PATH"
    echo "  MCP server: $MCP_SERVER_DIR"
    echo "  Python indexer: $WRAPPER_PATH"
    echo "  MCP server: $MCP_WRAPPER_PATH"
    echo ""
    echo -e "${BLUE}Python Indexer Usage:${NC}"
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
    echo "  # File watching"
    echo "  claude-indexer watch start --project . --collection my-project"
    echo ""
    echo "  # Search collections"
    echo "  claude-indexer search \"query\" --project . --collection my-project"
    echo ""
    echo "  # Add MCP server configuration"
    echo "  claude-indexer add-mcp my-project"
    echo ""
    echo -e "${BLUE}MCP Server Usage:${NC}"
    echo "  # Test MCP server directly"
    echo "  mcp-qdrant-memory"
    echo ""
    echo -e "${BLUE}Setup Steps:${NC}"
    echo "1. Start Qdrant database:"
    echo "   docker run -p 6333:6333 -v \$(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant"
    echo ""
    echo "2. Configure API keys:"
    echo "   - Edit $SETTINGS_FILE (for Python indexer)"
    echo "   - Edit $MCP_ENV_FILE (for MCP server)"
    echo ""
    echo "3. Test Python indexer:"
    echo "   claude-indexer --project . --collection test"
    echo ""
    echo "4. Configure Claude Code MCP server:"
    echo "   - Use command: node $MCP_SERVER_DIR/dist/index.js"
    echo "   - Set environment variables from $MCP_ENV_FILE"
    echo ""
    echo -e "${GREEN}Both Python indexer and MCP server are now ready!${NC}"
else
    echo -e "${RED}❌ Installation failed${NC}"
    exit 1
fi
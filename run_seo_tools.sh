#!/usr/bin/env bash
#
# Wrapper script to run SEO tools with proper library paths
# This ensures numpy/pandas can find system libraries from flox environment
#

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Find the gcc library path from flox's nix store
GCC_LIB_PATH=$(find /nix/store -name 'libstdc++.so.6' -path '*gcc-*-lib/lib*' 2>/dev/null | head -1 | xargs dirname)
ZLIB_LIB_PATH=$(find /nix/store -name 'libz.so.1' -path '*zlib*/lib*' 2>/dev/null | head -1 | xargs dirname)

if [ -z "$GCC_LIB_PATH" ]; then
    echo "❌ Error: Could not find gcc libraries. Make sure 'flox install gcc' has been run."
    exit 1
fi

if [ -z "$ZLIB_LIB_PATH" ]; then
    echo "❌ Error: Could not find zlib libraries. Make sure 'flox install zlib' has been run."
    exit 1
fi

# Set library path to include flox-provided system libraries
export LD_LIBRARY_PATH="$GCC_LIB_PATH:$ZLIB_LIB_PATH:$LD_LIBRARY_PATH"

# Activate whichever virtualenv exists, then run the command.
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

exec "$@"

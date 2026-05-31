#!/bin/zsh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

export UV_CACHE_DIR="$PROJECT_DIR/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PROJECT_DIR/.uv-python"
APP_PORT="8502"

echo "Mortgage Overpayment Planner"
echo "============================"
echo ""
echo "Starting the app. A browser window should open automatically."
echo "If this is the first run, setup may take a minute."
echo ""

if lsof -nP -iTCP:$APP_PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "The app is already running."
  echo "Opening it in your browser..."
  open "http://localhost:$APP_PORT" >/dev/null 2>&1 || true
  echo ""
  read -r "?Press Return to close this window..."
  exit 0
fi

if [ ! -x "$PROJECT_DIR/.tools/bin/uv" ]; then
  echo "Setting up the app runner..."
  mkdir -p "$PROJECT_DIR/.tools/bin"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$PROJECT_DIR/.tools/bin" sh || {
    echo ""
    echo "Setup could not finish. Please check your internet connection and try again."
    echo "You can close this window."
    read -r "?Press Return to close..."
    exit 1
  }
fi

"$PROJECT_DIR/.tools/bin/uv" sync --dev || {
  echo ""
  echo "The app setup failed. Please close this window and try again."
  read -r "?Press Return to close..."
  exit 1
}

"$PROJECT_DIR/.tools/bin/uv" run streamlit run app.py --server.port "$APP_PORT"

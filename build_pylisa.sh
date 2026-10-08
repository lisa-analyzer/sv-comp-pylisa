#!/bin/bash
set -e
set -o pipefail
PYLISA_BIN_DIR="pylisa-0.1"
VENV_DIR=".sv-comp_venv"

usage() {
    echo "Usage: $0 --pylisa-dir PATH_TO_PYLISA"
    exit 1
}

PYLISA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
    --pylisa-dir)
        PYLISA_DIR="$2"
        shift 2
        ;;
    --help | -h)
        usage
        ;;
    *)
        echo "Unknown argument: $1"
        usage
        ;;
    esac
done

if [[ -z "$PYLISA_DIR" ]]; then
    echo "Error: --pylisa-dir is required."
    usage
fi

echo ">>> PYLISA_DIR=$PYLISA_DIR"
SV_COMP_DIR="."
SVCOMP_BENCHMARK_DIR="$(pwd)/SVCOMP/sv-benchmarks"

PYTHON=${PYTHON:-python3}
echo "Creating venv in $VENV_DIR using $($PYTHON --version)"
$PYTHON -m venv "$VENV_DIR"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
$VENV_PIP install --upgrade pip
echo "Installing pyinstaller..."
$VENV_PIP install pyinstaller
echo "Running vendoryze..."
$VENV_PY ./vendor/vendorize.py

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTDIR="$(pwd)/outputs/$TIMESTAMP"

mkdir -p "$OUTDIR"

if [ -d "$PYLISA_DIR/build" ]; then
    echo "Removing existing pylisa build folder..."
    rm -rf "$PYLISA_DIR/build"
fi

echo "Building pylisa..."
(cd "$PYLISA_DIR" && ./gradlew clean build --refresh-dependencies -x test -x spotlessApply -x spotlessCheck --no-configuration-cache)

if [ -d "$SV_COMP_DIR/$PYLISA_BIN_DIR" ]; then
    echo "Removing existing $SV_COMP_DIR/$PYLISA_BIN_DIR folder..."
    rm -rf "$SV_COMP_DIR/$PYLISA_BIN_DIR"
fi

echo "Unzipping pylisa distribution into $SV_COMP_DIR..."
PYLISA_ZIP=$(ls $PYLISA_DIR/build/distributions/*.zip | head -n1)
if [ -z "$PYLISA_ZIP" ]; then
    echo "Error: No pylisa zip found in build/distributions"
    exit 1
fi
unzip -o "$PYLISA_ZIP" -d "$SV_COMP_DIR/"

PYLISA_DIR_UNZIPPED="$PYLISA_BIN_DIR"
CONFIG_JSON="$SV_COMP_DIR/config.json"

echo "Creating config.json..."
cat >"$CONFIG_JSON" <<EOF
{
    "path_to_sv_comp_benchmark_dir": "$SVCOMP_BENCHMARK_DIR",
    "path_to_lisa_instance": "\"${PYLISA_DIR_UNZIPPED}/lib/*\"",
    "path_to_output_dir": "$OUTDIR"
}
EOF

if [ -f "$SV_COMP_DIR/smoketest.sh" ]; then
    echo "Running smoketest..."
    (cd "$SV_COMP_DIR" && bash smoketest.sh)
else
    echo "Warning: smoketest.sh not found in $SV_COMP_DIR"
fi

echo "Generating pylisa executable."

APP_NAME="pylisa"
MAIN_SCRIPT="main.py"
PYVER=$($VENV_PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENDOR_PATH="vendor/lib/python$PYVER/site-packages"
INCLUDE_ITEMS=(
    "$PYLISA_BIN_DIR:$PYLISA_BIN_DIR"
    "./config.json:."
    "./pyproject.toml:."
)

ADD_DATA_FLAGS=()
for item in "${INCLUDE_ITEMS[@]}"; do
    ADD_DATA_FLAGS+=(--add-data "$item")
done

echo "===================================="
echo " Building project"
echo "  • Main script: $MAIN_SCRIPT"
echo "  • Output name: $APP_NAME"
echo "===================================="

$VENV_PY -m PyInstaller "$MAIN_SCRIPT" \
    --onefile \
    --clean --strip \
    --name "$APP_NAME" \
    --paths "$VENDOR_PATH" \
    "${ADD_DATA_FLAGS[@]}"

echo ""
echo "Build complete!"
echo "Executable created at: dist/$APP_NAME"
echo ""

PYLISA_EXEC="dist/$APP_NAME"
DIST_TEMPLATE="dist-template"
MAIN_FOLDER="$(pwd)"
TEMP_DIR="$(mktemp -d "$MAIN_FOLDER/tmp_dist_XXXX")"
PYLISA_FOLDER="$TEMP_DIR/$PYLISA_BIN_DIR"
ZIP_FILE="$MAIN_FOLDER/pylisa.zip"

if [ -f "$ZIP_FILE" ]; then
    echo "Removing existing $ZIP_FILE in main folder..."
    rm -f "$ZIP_FILE"
fi

echo "Creating temporary folder at $PYLISA_FOLDER..."

mkdir -p "$PYLISA_FOLDER"

cp -r "$DIST_TEMPLATE/." "$PYLISA_FOLDER/"

cp "$PYLISA_EXEC" "$PYLISA_FOLDER/"
chmod +x "$PYLISA_FOLDER/$(basename "$PYLISA_EXEC")"
chmod +x "$PYLISA_FOLDER/smoketest.sh"

echo "Creating zip file $ZIP_FILE..."
(cd "$TEMP_DIR" && zip -r "$ZIP_FILE" "$PYLISA_BIN_DIR")

echo "Cleaning up temporary folder..."
rm -rf "$TEMP_DIR"

echo "Zip package created successfully: $ZIP_FILE"

TEST_DIR="$(mktemp -d "$MAIN_FOLDER/tmp_test_XXXX")"
echo "Unzipping $ZIP_FILE into $TEST_DIR..."
unzip -q "$ZIP_FILE" -d "$TEST_DIR"
echo "Test smoketest.sh of zip"
SMOKETEST="$TEST_DIR/$PYLISA_BIN_DIR/smoketest.sh"
if [ -f "$SMOKETEST" ]; then
    echo "Running smoketest.sh..."
    (cd "$TEST_DIR/$PYLISA_BIN_DIR" && bash smoketest.sh)
else
    echo "Warning: smoketest.sh not found in the zip"
fi

rm -rf "$TEST_DIR"
echo "Temporary test folder cleaned up."

echo "pylisa.zip successfully create in $(pwd)"

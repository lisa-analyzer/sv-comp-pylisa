#!/bin/bash
set -e
set -o pipefail

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "Error: pylisa must be built on Linux x86_64 (got $(uname -s) $(uname -m))"
    exit 1
fi

PYLISA_BIN_DIR="pylisa-0.1"
VENV_DIR=".sv-comp_venv"
# the z3 release shipped with the archive, that pylisa uses to verify its warnings: the same as in the GitHub
# actions of lisa (.github/actions/setup-z3/action.yml) and in build_jlisa.sh, to be kept in sync with them
Z3_VERSION="4.16.0"
Z3_GLIBC="2.39"
Z3_SHA256="7288c49a5bd6dbafd7b0b0d1f65956b91672da24b08f09242919af159be3418e"
# where z3 is extracted (its executable, z3/z3, and its license), as `pylisa check` looks for it
Z3_DIR="z3"

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

Z3_NAME="z3-$Z3_VERSION-x64-glibc-$Z3_GLIBC"
if [ -x "$SV_COMP_DIR/$Z3_DIR/z3" ] && [ "$(cat "$SV_COMP_DIR/$Z3_DIR/VERSION" 2>/dev/null)" = "$Z3_NAME" ]; then
    echo "z3 $Z3_VERSION already downloaded in $SV_COMP_DIR/$Z3_DIR"
else
    echo "Downloading z3 $Z3_VERSION..."
    Z3_TMP="$(mktemp -d)"
    curl --silent --show-error --fail -L -o "$Z3_TMP/z3.zip" \
        "https://github.com/Z3Prover/z3/releases/download/z3-$Z3_VERSION/$Z3_NAME.zip"
    echo "$Z3_SHA256  $Z3_TMP/z3.zip" | sha256sum --check
    unzip -q "$Z3_TMP/z3.zip" "$Z3_NAME/bin/z3" "$Z3_NAME/LICENSE.txt" -d "$Z3_TMP"
    rm -rf "$SV_COMP_DIR/$Z3_DIR"
    mkdir -p "$SV_COMP_DIR/$Z3_DIR"
    mv "$Z3_TMP/$Z3_NAME/bin/z3" "$Z3_TMP/$Z3_NAME/LICENSE.txt" "$SV_COMP_DIR/$Z3_DIR/"
    echo "$Z3_NAME" > "$SV_COMP_DIR/$Z3_DIR/VERSION"
    rm -rf "$Z3_TMP"
fi
chmod +x "$SV_COMP_DIR/$Z3_DIR/z3"
"$SV_COMP_DIR/$Z3_DIR/z3" --version

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

# z3, next to the executable, where `pylisa check` looks for it
cp -r "$SV_COMP_DIR/$Z3_DIR" "$PYLISA_FOLDER/$Z3_DIR"
chmod +x "$PYLISA_FOLDER/$Z3_DIR/z3"
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

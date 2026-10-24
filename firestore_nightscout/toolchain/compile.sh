#!/bin/bash
# Retired stock-firmware compile. The clock runs AWTRIX NG.
# build.sh refuses to start this unless TC002_STOCK_TOOLCHAIN=1.
# Compile Z21_TC002_Demo with the FlyThings arm-linux-gnueabihf toolchain.
# Runs inside the linux/amd64 container. prepare.py has already filled /work/cache.
set -euo pipefail

CACHE=/work/cache
DEMO="$CACHE/demo/Z21_TC002_Demo"
CXX="$CACHE/ssd/toolchain/bin/arm-linux-gnueabihf-g++"
CC="$CACHE/ssd/toolchain/bin/arm-linux-gnueabihf-gcc"
READELF="$CACHE/ssd/toolchain/bin/arm-linux-gnueabihf-readelf"
OUT="$DEMO/Release"
OBJ="$OUT/obj"

if [[ ! -x "$CXX" ]]; then
  echo "Missing $CXX. Run prepare.py on the host first." >&2
  exit 1
fi

"$CXX" --version

includes=(
  -I"$DEMO/src"
  -I"$DEMO/src/dependencies/include"
)
while IFS= read -r dir; do
  includes+=(-I"$dir")
done < <(find "$CACHE/packages" -type d -name include | sort)

flags=(-O2 -fPIC -pipe -fmessage-length=0 -fstack-protector -fno-caller-saves -D__PLATFORM_Z21__ -DUSE_ANDROID_LOG)
cxxflags=("${flags[@]}" -std=c++11 -fexceptions)

mapfile -d '' sources < <(find "$DEMO/src" \
  -path "$DEMO/src/logic" -prune -o \
  -type f \( -name '*.cpp' -o -name '*.cc' -o -name '*.c' \) -print0 | sort -z)
rm -rf "$OBJ/src/logic"

objs=()
for src in "${sources[@]}"; do
  [[ -n "$src" ]] || continue
  rel="${src#"$DEMO"/}"
  obj="$OBJ/${rel}.o"
  mkdir -p "$(dirname "$obj")"
  if [[ -f "$obj" && "$obj" -nt "$src" ]]; then
    objs+=("$obj")
    continue
  fi
  echo "CC $rel"
  if [[ "$src" == *.c ]]; then
    "$CC" "${flags[@]}" "${includes[@]}" -c "$src" -o "$obj"
  else
    "$CXX" "${cxxflags[@]}" "${includes[@]}" -c "$src" -o "$obj"
  fi
  objs+=("$obj")
done

# The IDE builds a shared library (Release/zkgui.so), not an executable.
# main() lives in the clock firmware, which dlopens zkgui.so.
# aec and apc are marked linkLibrary=false in .deps.lock. Linking them
# fails: those binaries need glibc 2.29 and this toolchain is older.
mapfile -d '' libs < <(find "$CACHE/packages" "$DEMO/src/dependencies/lib" -type f \( -name '*.so' -o -name '*.a' \) \
  ! -path '*/aec-*/*' ! -path '*/apc-*/*' -print0 | sort -z)

mkdir -p "$OUT"
echo "LINK ${#objs[@]} objects, ${#libs[@]} libraries -> zkgui.so"
"$CXX" -shared -o "$OUT/zkgui.so" "${objs[@]}" \
  -Wl,--start-group "${libs[@]}" -Wl,--end-group \
  -Wl,-z,now -Wl,-z,relro -Wl,-z,defs -Wl,--warn-common -Wl,-z,combreloc -Wl,--warn-once \
  -Wl,--allow-shlib-undefined \
  -pthread -ldl -lm

"$READELF" -h "$OUT/zkgui.so"
echo "Built $OUT/zkgui.so"

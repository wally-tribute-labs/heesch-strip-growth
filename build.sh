#!/bin/sh
set -eu
# Specialize only the CLI input dispatcher to the hexagonal grid; all solver headers are upstream.
python3 - <<'PY'
from pathlib import Path
s=Path("upstream/src/sat.cpp").read_text()
s=s.replace("int main( int argc", """#undef processInputStream
#define processInputStream(is, f) while ((is).peek() != EOF) { if ((is).get() != 'H') std::abort(); TileInfo<HexGrid<int16_t>> info{is}; f(info); }

int main( int argc""")
Path("sat-hex.cpp").write_text(s)
PY
g++ -std=c++20 -O2 -DNDEBUG -include cstring -Ideps/usr/include -Iupstream/src -Ideps/usr/include/cryptominisat5 sat-hex.cpp upstream/src/isohedral.cpp -Ldeps/usr/lib/aarch64-linux-gnu -Wl,-rpath,'$ORIGIN/deps/usr/lib/aarch64-linux-gnu' -lcryptominisat5 -o sat-hex

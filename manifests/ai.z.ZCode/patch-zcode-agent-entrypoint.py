#!/usr/bin/python3

import pathlib
import sys


STRICT_DIRECTIVES = (b'"use strict";', b"'use strict';")
REQUIRE_SHIM = b'require("/app/lib/zcode-portal-cwd.cjs");'


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} ZCODE_CJS")

    entrypoint = pathlib.Path(sys.argv[1])
    contents = entrypoint.read_bytes()

    if contents.startswith(b"#!"):
        insertion_offset = contents.find(b"\n")
        if insertion_offset < 0:
            raise SystemExit(f"unterminated shebang in {entrypoint}")
        insertion_offset += 1
    else:
        insertion_offset = 0

    for directive in STRICT_DIRECTIVES:
        if contents[insertion_offset:].startswith(directive):
            insertion_offset += len(directive)
            prelude = REQUIRE_SHIM
            break
    else:
        prelude = STRICT_DIRECTIVES[0] + REQUIRE_SHIM

    if contents[insertion_offset:].startswith(REQUIRE_SHIM):
        return

    entrypoint.write_bytes(
        contents[:insertion_offset] + prelude + contents[insertion_offset:]
    )


if __name__ == "__main__":
    main()

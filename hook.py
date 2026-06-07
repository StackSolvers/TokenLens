import json
import subprocess
import os
import sys

def read_stdin_nonblocking():
    try:
        if sys.platform == 'win32':
            import ctypes
            import msvcrt
            handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            avail = ctypes.c_ulong(0)
            res = ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(avail), None
            )
            if res != 0 and avail.value > 0:
                return sys.stdin.read(avail.value)
        else:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                return sys.stdin.read()
    except Exception:
        pass
    return None

def main():
    read_stdin_nonblocking()

    if os.environ.get("TOKENLENS_HOOK_VERBOSE") == "1":
        cli_path = os.path.join(os.path.dirname(__file__), "cli.py")
        try:
            subprocess.run(
                [sys.executable, cli_path, "--compact"],
                stdout=sys.stderr,
                stderr=sys.stderr,
                timeout=15,
                check=False,
            )
        except Exception as e:
            print(f"TokenLens error: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)

    # Return the expected JSON decision payload back to Antigravity
    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()

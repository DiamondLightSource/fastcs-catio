---
name: test-system-preflight
description: Notes on the port architecture in tests/test_system.py — the simulator subprocess and controller now use ephemeral TCP+UDP ports per-test, so port collisions should no longer occur. Includes a diagnostic ladder for any future port-collision investigation.
---

# test-system-preflight

`tests/test_system.py` spawns `python -m tests.ads_sim` as a subprocess. As of
the migrate-fastcs-0.14.0-beta.1 work it now uses **ephemeral TCP and UDP
ports per fixture instance** — no fixed `48898`/`48899` anywhere in the test
flow. Each parametrized case picks fresh ports, passes them to the simulator
via `--port` / `--udp-port`, and to the controller via
`CATioServerController(..., tcp_port=...)` and `RemoteRoute(..., udp_port=...)`.

So back-to-back tests no longer collide on TIME_WAIT (TCP) or lingering UDP
socket state, and you don't need to preflight anything before running
`pytest tests/test_system.py`.

## If you ever do hit a bind error

The pattern that previously caused `OSError: [Errno 98] address already in use`
was a hardcoded port in the fixture; if you see it again it's almost certainly
a regression of that — first check whether the fixture is back to a fixed port.

If something genuinely holds a port the test wants, the diagnostic ladder is:

1. **Confirm the kernel actually has a listener in this netns:**
   ```bash
   awk 'NR>1 && $4 == "0A" {print "port=" $2 " inode=" $10}' /proc/net/tcp
   awk 'NR>1 {print "port=" $2 " inode=" $10}' /proc/net/udp
   ```
   Convert hex port to decimal: `printf '%d\n' 0xBF02` → `48898`.

2. **Map socket inode to PID via `/proc/*/fd`:**
   ```bash
   INODE=<inode-from-step-1>
   for fd in /proc/[0-9]*/fd/*; do
     [ "$(readlink "$fd" 2>/dev/null)" = "socket:[$INODE]" ] && \
       echo "pid=$(echo $fd | cut -d/ -f3) cmd=$(cat ${fd%/fd/*}/comm 2>/dev/null)"
   done
   ```

3. **If step 1 found a row but step 2 finds nothing:** the listener lives in
   a different PID namespace that shares this netns (sibling containers /
   sandboxed setups). From inside that sandbox you cannot identify or kill it.
   The fix is no longer "kill the listener"; it's to make sure the test
   fixture is using ephemeral ports as designed.

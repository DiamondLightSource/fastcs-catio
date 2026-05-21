---
name: fastcs-controller-connect
description: When subclassing fastcs.controllers.Controller (in fastcs-catio's CATioController and any other downstream subclass), every override of async connect() must call await super().connect() — otherwise scan tasks silently never fire because Controller._connected stays False. Symptom is hangs at startup, not errors.
---

# fastcs Controller.connect() must chain to super

## The rule

When you override `async def connect(self)` on a subclass of
`fastcs.controllers.Controller` (>= 0.14), the override **must** call
`await super().connect()` somewhere on every path.

If your class is a middle layer in a multi-level hierarchy (e.g.
`MyServer → MyDeviceBase → Controller`), every level on the chain must do
this — a single missing call breaks the whole tree.

## Why

Since fastcs 0.14, `Controller._create_periodic_scan_coro` gates each scan
loop on `self._connected`:

```python
async def scan_coro() -> None:
    while True:
        if not self._connected:
            await asyncio.sleep(1)
            continue
        ...
```

`_connected` is only flipped to `True` inside the base `Controller.connect()`.
If a subclass override doesn't call `super().connect()`, `_connected` stays
`False` forever and **every `@scan(...)`-decorated method on every controller
in the tree silently never executes**.

## How this presents

- The IOC starts, transports come up, but no scan logs appear.
- Any code that waits on a flag set inside a scan method will hang.
  In fastcs-catio, `notification_enabled` is set inside the `notifications`
  scan, so test fixtures that wait on it time out (the original symptom that
  prompted this skill — `test_ioc_connects_and_discovers_symbols` hung for
  120s waiting for the flag).
- No errors, no warnings — pure silent inactivity. Easy to misdiagnose as a
  network or transport problem.

## Catching it

When a controller in this codebase appears to "do nothing" after startup, the
first thing to check is the `connect()` override chain:

```bash
grep -nE "async def connect" src/fastcs_catio/*.py
```

For each override, confirm `await super().connect()` is present and not
commented out. The failure mode previously seen was a literal `# await
super().connect()` on `CATioController` that broke the chain for every
subclass below it.

## Don't comment-out super calls "to refactor later"

Some of the `connect()` / `initialise()` overrides in catio still have or had
commented-out `# await super().connect()` lines, sometimes with no surrounding
explanation. Treat any commented-out super call in a fastcs lifecycle hook as
suspicious — the framework relies on the chain being intact and the cost of a
broken chain is silent (which makes it expensive to debug).

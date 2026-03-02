# Concerns

## Tech Debt

### High Priority

1. **Single EtherCAT device hardcoded** — `src/fastcs_catio/client.py` has an assertion that blocks multi-master device support. Only one device can be used at a time.

2. **All dynamic symbol types map to `Int()`** — `src/fastcs_catio/terminal_config.py:151` has a TODO: all symbols map to `Int()` regardless of actual type. Should map using `symbol.type_name`.

3. **Route deletion commented out** — `src/fastcs_catio/catio_controller.py:456` route cleanup on disconnect is disabled.

4. **Test suites entirely skipped** — `test_catio_system.py` and `test_catio_performance.py` are both skipped at module level with `reason="TODO these are all failing"`.

### Medium Priority

5. **Global mutable poll period variables** — `src/fastcs_catio/catio_controller.py:390-393` — shared across all controller instances.

6. **Class-level TCP connection** — `src/fastcs_catio/catio_controller.py:63` — single connection shared across all instances.

7. **Notification handle uniqueness** — `src/fastcs_catio/client.py:2549` — not enforced across devices.

8. **`EL3104Controller.read_configuration()` stub** — `src/fastcs_catio/catio_hardware.py:681` — uses `print()` instead of logging, says "NOT IMPLEMENTED YET".

9. **Oversampling factor hardcoded** — `src/fastcs_catio/catio_hardware.py:815-819` — `OVERSAMPLING_FACTOR` constant instead of reading from ADS. Has a TODO comment.

10. **CoE attribute name collision check incomplete** — `src/fastcs_catio/catio_dynamic_controller.py:123`.

## Known Bugs

1. **`_recv_forever` silent exit** — The receive loop exits silently on `AssertionError`, killing the receive task without surfacing errors to the user.

2. **`get_io_from_map()` raises `KeyError`** — On second call, raises `KeyError` instead of returning cached value.

3. **`UDPMessage.invoke_id` is non-thread-safe** — Class-level counter incremented without locking.

## Security

1. **Default password `"1"` hardcoded** — `RemoteRoute` uses a default password of `"1"` for ADS route authentication.

2. **UDP response origin not verified** — No cryptographic verification of ADS UDP responses.

3. **Password transmitted in plaintext** — ADS route passwords sent as plaintext UDP bytes.

> **Context:** These are inherent limitations of the ADS protocol rather than implementation oversights. ADS is designed for closed industrial networks, not public-facing systems.

## Performance

1. **`average()` non-vectorised loop** — GitHub issue #22 open. Manual loop instead of numpy vectorized operation.

2. **Sequential per-slave ADS round-trips on startup** — Device/terminal introspection happens sequentially, could be parallelized.

3. **Unconditional notification array averaging** — Runs every scan cycle regardless of whether new data arrived.

## Fragile Areas

1. **Bare `except Exception` in `_recv_ams_message`** — Catches and logs all exceptions, potentially hiding protocol errors.

2. **Bare `except Exception` in `notifications()` scan** — Same pattern in notification processing.

3. **`symbol_lookup()` manual LUT** — Has multiple `TO DO: REVIEW` branch markers suggesting incomplete logic.

4. **Dynamic controller cache** — Not invalidated on error, may serve stale data.

5. **`CATioControllerSymbolAttributeIO.update()`** — Is a `pass` stub (no-op).

## Scaling Limits

- **Single master device** enforced at two assertion points in `client.py`
- **Unbounded notification queue** — no backpressure mechanism

## Missing Features

- No TCP reconnection logic (connection drops require restart)
- No route cleanup CLI command
- No graceful degradation on partial device failures

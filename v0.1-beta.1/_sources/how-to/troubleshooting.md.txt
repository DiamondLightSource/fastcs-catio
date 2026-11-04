# Troubleshooting

Common issues and their solutions when working with fastcs-catio.

## Test System Issues

### Port 48898 Already in Use

**Problem:** When running `pytest tests/test_system.py`, you get an error:
```
Port 48898 is already in use. A simulator may already be running.
```

But you're certain no simulator is running.

**Cause:** VS Code's auto port-forwarding feature may have automatically forwarded port 48898, which prevents the test simulator from binding to it.

**Solution:**
1. Open VS Code's Ports panel: **View → Ports** (or press `Ctrl+Shift+P` and search for "Ports: Focus on Ports View")
2. Look for port 48898 in the list
3. Right-click on it and select **Stop Forwarding Port** or **Remove Port**
4. Re-run the tests

**Prevention:** You can disable auto port-forwarding in VS Code settings:
- Open Settings (`Ctrl+,`)
- Search for `remote.autoForwardPorts`
- Set it to `false` or configure `remote.autoForwardPortsSource` to exclude port 48898

### Alternative: Using an External Simulator

If you have a simulator already running intentionally, you can tell the tests to use it instead of launching their own:

```bash
pytest tests/test_system.py --external-simulator
```

This skips the port check and internal simulator launch, assuming a simulator is already listening on port 48898.

## VS Code Dev Container Issues

### Terminal Commands Not Showing

**Problem:** Commands executed in the terminal don't display output or appear to hang.

**Solution:** Rebuild the dev container:
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Select **Dev Containers: Rebuild Container**
3. Choose **Rebuild Container Without Cache** for a clean rebuild

### Container Port Binding Issues

**Problem:** After a container restart or rebuild, ports show as already in use even though nothing is running.

**Solution:**
1. Stop all containers: `docker stop $(docker ps -aq)`
2. Remove the specific container: `docker ps -a | grep fastcs-catio` then `docker rm <container-id>`
3. Optionally, prune Docker resources: `docker system prune` (careful - removes unused containers/networks/images)
4. Reopen the folder in the container

## Hardware Connection Issues

### Cannot Connect to PLC/Controller

**Problem:** `fastcs-catio ioc` fails with connection errors.

**Common causes:**
- Network connectivity issues
- Incorrect AMS Net ID or IP address in configuration
- Firewall blocking ADS protocol (port 48898)
- TwinCAT runtime not running on the target

**Solutions:**
- Verify network connectivity: `ping <controller-ip>`
- Check AMS Net ID matches the controller configuration
- Ensure TwinCAT is in Run mode on the controller
- Check firewall settings allow ADS traffic
- Verify the correct configuration file is being used

## Build and Installation Issues

### Package Installation Fails

**Problem:** `uv pip install` or package installation fails.

**Solution:**
- Ensure you're in the dev container or have the correct Python environment active
- Try: `uv sync --reinstall` to force reinstall all packages
- Check `pyproject.toml` for any conflicting version constraints

### Type Checking Failures

**Problem:** `pyright` or `mypy` reports type errors that seem incorrect.

**Solution:**
- Ensure all dependencies are installed: `uv sync`
- Clear type checker cache: `rm -rf .mypy_cache` or `rm -rf .pyright`
- Restart your editor/language server
- Check if you're using the correct Python interpreter from the venv

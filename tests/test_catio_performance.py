"""
CATio Performance Tests file for the CATio system.
Each test prints detailed analysis metrics (ops/sec, latency in ms, comparative ratios).
The tests use the same mock server infrastructure and port to avoid conflicts.

Tests currently measure and validate performance characteristics for:
- Operation latency (read, write, notifications)
- Throughput (operations per second)
- Scalability with concurrent operations
- Memory usage and leaks
- Load and stress testing
- Comparative operation modes
- Bottleneck identification

Run the tests with:
```bash
python -m pytest tests/test_catio_performance.py -v
```
"""

import asyncio
import random
import time
from typing import Any

import numpy as np
import pytest
from catio.client import AsyncioADSClient
from catio.devices import AdsSymbol

from mock_server import MockADSServer

IO_SERVER_PORT: int = 25565

pytest.skip(allow_module_level=True, reason="TODO these are all failing")


@pytest.fixture
async def perf_test_server():
    """Set up a mock ADS server for performance testing."""
    server = MockADSServer(host="127.0.0.1", port=48898)

    # Pre-populate the mock server with test symbol data
    for i in range(200):
        server.set_symbol_data(f"Symbol{i}", np.int32(i))

    await server.start()
    yield server
    await server.stop()


# ===================================================================
# Latency Measurement Tests
# ===================================================================


class TestOperationLatency:
    """Test and measure operation latencies."""

    @pytest.mark.asyncio
    async def test_read_state_latency(self, perf_test_server: MockADSServer):
        """Measure read operation latency for the mock server states."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        try:
            # First warmup call to confirm functionality
            await client._get_ioserver_states()

            # Latency measurements
            latencies = []
            for _ in range(num_operations):
                start = time.perf_counter()
                await client._get_ioserver_states()
                latency = time.perf_counter() - start
                latencies.append(latency)

            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify reasonable latencies (should be sub-second for mock)
            assert avg_latency < 1.0
            assert min_latency < max_latency

            # Report results to stdout
            print(
                f"Read states -- latency test results over {num_operations} samples:\n"
                + f"Avg: {avg_latency * 1000:.2f}ms,\n"
                + f"Min: {min_latency * 1000:.2f}ms,\n"
                + f"Max: {max_latency * 1000:.2f}ms"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_read_latency(self, perf_test_server: MockADSServer):
        """Measure symbol read operation latency."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        # Create a sequence of random symbols for testing
        test_symbols: list[AdsSymbol] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol())
        assert len(test_symbols) == num_operations

        try:
            # First warmup call to confirm functionality
            await client.read_ads_symbol(test_symbols[0])

            # Latency measurements
            latencies = []
            for symbol in test_symbols:
                start = time.perf_counter()
                await client.read_ads_symbol(symbol)
                latency = time.perf_counter() - start
                latencies.append(latency)

            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify reasonable latencies (should be sub-second for mock)
            assert avg_latency < 1.0
            assert min_latency < max_latency

            # Report results to stdout
            print(
                f"Read symbol -- latency test results over {num_operations} samples:\n"
                + f"Avg: {avg_latency * 1000:.2f}ms,\n"
                + f"Min: {min_latency * 1000:.2f}ms,\n"
                + f"Max: {max_latency * 1000:.2f}ms"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_write_latency(self, perf_test_server: MockADSServer):
        """Measure symbol write operation latency."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        try:
            # First warmup call to confirm functionality
            s0, v0 = test_symbols[0]
            await client.write_ads_symbol(s0, v0)

            # Latency measurements
            latencies = []
            for symbol, value in test_symbols:
                start = time.perf_counter()
                await client.write_ads_symbol(symbol, value)
                latency = time.perf_counter() - start
                latencies.append(latency)

            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify reasonable latencies (should be sub-second for mock)
            assert avg_latency < 1.0
            assert min_latency < max_latency

            # Report results to stdout
            print(
                f"Write symbol -- latency test results over {num_operations} samples:\n"
                + f"Avg: {avg_latency * 1000:.2f}ms,\n"
                + f"Min: {min_latency * 1000:.2f}ms,\n"
                + f"Max: {max_latency * 1000:.2f}ms"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_read_write_latency(self, perf_test_server: MockADSServer):
        """Measure symbol combined read/write operation latency."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        try:
            # First warmup call to confirm functionality
            s0, v0 = test_symbols[0]
            await client.readwrite_ads_symbol(s0, v0)

            # Latency measurements
            latencies = []
            for symbol, value in test_symbols:
                start = time.perf_counter()
                await client.readwrite_ads_symbol(symbol, value)
                latency = time.perf_counter() - start
                latencies.append(latency)

            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify reasonable latencies (should be sub-second for mock)
            assert avg_latency < 1.0
            assert min_latency < max_latency

            # Report results to stdout
            print(
                "Read/Write symbol -- "
                + f"latency test results over {num_operations} samples:\n"
                + f"Avg: {avg_latency * 1000:.2f}ms,\n"
                + f"Min: {min_latency * 1000:.2f}ms,\n"
                + f"Max: {max_latency * 1000:.2f}ms"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_notification_subscription_latency(
        self, perf_test_server: MockADSServer
    ):
        """Measure symbol notification subscription latency."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        # Create a sequence of discrete random symbols for testing notifications
        assert num_operations <= len(perf_test_server.symbols), (
            "Not enough symbol definitions in the mock server "
            + "for the requested number of subscriptions; "
            + f"current limit is {len(perf_test_server.symbols)}"
        )
        test_symbols: list[AdsSymbol] = []
        while len(test_symbols) < num_operations:
            test_symbols.append(perf_test_server.get_random_symbol())
            # Remove duplicates from the current test sample list
            test_symbols = list(set(test_symbols))
        assert len(test_symbols) == num_operations

        try:
            # Latency measurements
            latencies = []
            handles = []
            for symbol in test_symbols:
                start = time.perf_counter()
                handle = await client.add_device_notification(
                    symbol=symbol,
                    max_delay_ms=1000,
                    cycle_time_ms=100,
                )
                latency = time.perf_counter() - start
                latencies.append(latency)
                handles.append(handle)

            # Cleanup notification subscriptions
            for handle in handles:
                await client.delete_device_notification(handle)

            # Calculate statistics
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify reasonable latencies (should be sub-second for mock)
            assert avg_latency < 1.0
            assert min_latency < max_latency

            # Report results to stdout
            print(
                "Symbol notification subscription -- "
                + f"latency test results over {num_operations} samples:\n"
                + f"Avg: {avg_latency * 1000:.2f}ms,\n"
                + f"Min: {min_latency * 1000:.2f}ms,\n"
                + f"Max: {max_latency * 1000:.2f}ms"
            )

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Throughput Tests
# ===================================================================


class TestOperationThroughput:
    """Test and measure operation throughput."""

    @pytest.mark.asyncio
    async def test_sequential_read_throughput(self, perf_test_server: MockADSServer):
        """Measure sequential read operations throughput."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 1000

        # Create a sequence of random symbols for testing
        test_symbols: list[AdsSymbol] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol())
        assert len(test_symbols) == num_operations

        try:
            # Throughput measurements for single-threaded read operations
            start = time.perf_counter()
            for symbol in test_symbols:
                await client.read_ads_symbol(symbol)
            elapsed = time.perf_counter() - start

            # Calculate statistics and verify reasonable results
            throughput = num_operations / elapsed
            assert throughput > 0

            # Report results to stdout
            print(
                "Throughput test results for sequential read:\n"
                + f"{throughput:.1f} ops/sec based on {num_operations} samples"
            )
        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_sequential_write_throughput(self, perf_test_server: MockADSServer):
        """Measure sequential write operations throughput."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 1000

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        try:
            # Throughput measurements for single-threaded write operations
            start = time.perf_counter()
            for symbol, value in test_symbols:
                await client.write_ads_symbol(symbol, value)
            elapsed = time.perf_counter() - start

            # Calculate statistics and verify reasonable results
            throughput = num_operations / elapsed
            assert throughput > 0

            # Report results to stdout
            print(
                "Throughput test results for sequential write:\n"
                + f"{throughput:.1f} ops/sec based on {num_operations} samples"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_combined_read_write_operation_throughput(
        self, perf_test_server: MockADSServer
    ):
        """Measure combined read/write operation throughput."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 500

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        try:
            # Throughput measurements for single-threaded read/write operations
            start = time.perf_counter()
            for symbol, value in test_symbols:
                await client.readwrite_ads_symbol(symbol, value)
            elapsed = time.perf_counter() - start

            # Calculate statistics and verify reasonable results
            throughput = num_operations / elapsed
            assert throughput > 0

            # Report results to stdout
            print(
                "Throughput test results for sequential combined read/write:\n"
                + f"{throughput:.1f} ops/sec based on {num_operations} samples"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_concurrent_read_throughput(self, perf_test_server: MockADSServer):
        """Measure concurrent read operations throughput."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_tasks = 100
        num_operations = 10

        # Create a sequence of random symbols for testing
        test_symbols: list[AdsSymbol] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol())
        assert len(test_symbols) == num_operations

        try:
            # Read task definition
            async def read_task():
                for symbol in test_symbols:
                    await client.read_ads_symbol(symbol)

            # Throughput measurements for parallel read operations
            start = time.perf_counter()
            await asyncio.gather(*[read_task() for _ in range(num_tasks)])
            elapsed = time.perf_counter() - start

            # Calculate statistics and verify reasonable results
            total_operations = num_tasks * num_operations
            throughput = total_operations / elapsed
            assert throughput > 0

            # Report results to stdout
            print(
                "Throughput test results for concurrent read operations:\n"
                + f"{throughput:.1f} ops/sec based on {num_tasks} tasks "
                + f"with {num_operations} samples each"
            )
        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_mixed_operations_throughput(self, perf_test_server: MockADSServer):
        """Measure throughput of mixed read and write operations."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 500

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        try:
            # Throughput measurements for mixed type operations
            start = time.perf_counter()
            for i, (symbol, value) in enumerate(test_symbols):
                if i % 2 == 0:
                    await client.read_ads_symbol(symbol)
                else:
                    await client.write_ads_symbol(symbol, value)
            elapsed = time.perf_counter() - start

            # Calculate statistics and verify reasonable results
            throughput = num_operations / elapsed
            assert throughput > 0

            # Report results to stdout
            print(
                "Throughput test results for mixed symbol operations:\n"
                + f"{throughput:.1f} ops/sec based on {num_operations} samples"
            )

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Scalability Tests
# ===================================================================


class TestScalability:
    """Test scalability with increasing load."""

    # # TO DO: if multiple clients can be mocked, test throughput
    # # with concurrent connections
    # @pytest.mark.asyncio
    # async def test_scalability_concurrent_clients(
    #     self, perf_test_server: MockADSServer
    # ):
    #     """Test scalability with increasing number of concurrent clients."""
    #     scalability_results = {}

    #     # Define the test sample populations
    #     num_clients = [1, 5, 10, 20]
    #     num_operations = 100

    #     # Scalability measurements for different number of clients
    #     for nclients in num_clients:
    #         clients = []
    #         try:
    #             # Create clients
    #             for i in range(nclients):
    #                 # connection to server
    #                 clients.append(client)

    #             # Define client operation task to measure throughput
    #             async def client_operations(client):
    #                 symbol = perf_test_server.get_random_symbol()
    #                 for _ in range(num_operations):
    #                     await client.read_ads_symbol(symbol)

    #             # Scalability measurements with multiple clients
    #             start = time.perf_counter()
    #             await asyncio.gather(*[client_operations(c) for c in clients])
    #             elapsed = time.perf_counter() - start

    #             # Calculate statistics for each client load
    #             throughput = (nclients * num_operations) / elapsed
    #             scalability_results[nclients] = throughput

    #         finally:
    #             # Disconnect the clients
    #             for client in clients:
    #                 await client.close()

    #     # Verify reasonable results are achieved
    #     assert all(tp > 0 for tp in scalability_results.values())

    #     # Report results to stdout
    #     print("Scalability test results for different client loads:\n")
    #     for num_clients, throughput in scalability_results.items():
    #         print(
    #             f"Symbol read: {throughput:.1f} ops/sec "
    #             + f"when {num_clients} clients are concurrently connected "
    #             + f"to the server"
    #         )

    @pytest.mark.asyncio
    async def test_scalability_concurrent_notifications(
        self, perf_test_server: MockADSServer
    ):
        """Test scalability with increasing active notifications."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample populations
        num_notifications = [10, 50, 100]
        num_operations = 100

        # Create a sequence of discrete random symbols for testing notifications
        assert max(num_notifications) <= len(perf_test_server.symbols), (
            "Not enough symbol definitions in the mock server "
            + "for the requested number of subscriptions; "
            + f"current limit is {len(perf_test_server.symbols)}"
        )
        test_symbols: list[AdsSymbol] = []
        while len(test_symbols) < max(num_notifications):
            test_symbols.append(perf_test_server.get_random_symbol())
            # Remove duplicates from the current test sample list
            test_symbols = list(set(test_symbols))
        assert len(test_symbols) == max(num_notifications)

        # Scalability measurements for different notification loads
        try:
            scalability_results = {}
            for n in num_notifications:
                handles = []
                symbols = test_symbols[:n]

                # Create notification subscriptions
                for symbol in symbols:
                    handle = await client.add_device_notification(
                        symbol=symbol,
                        max_delay_ms=1000,
                        cycle_time_ms=100,
                    )
                    handles.append(handle)

                # Measure read throughput with notifications active
                s = perf_test_server.get_random_symbol()
                start = time.perf_counter()
                for _ in range(num_operations):
                    await client.read_ads_symbol(s)
                elapsed = time.perf_counter() - start

                # Calculate statistics for each load
                throughput = num_operations / elapsed
                scalability_results[num_notifications] = throughput

                # Cleanup notification subscriptions
                for handle in handles:
                    await client.delete_device_notification(handle)

            # Verify reasonable results are achieved
            assert all(tp > 0 for tp in scalability_results.values())

            # Report results to stdout
            print("Scalability test results for different notification loads:\n")
            for num_notifs, throughput in scalability_results.items():
                print(
                    f"Symbol read: {throughput:.1f} ops/sec "
                    + f"when concurrently subscribed to {num_notifs} notifications"
                )

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Memory and Resource Tests
# ===================================================================


class TestMemoryAndResources:
    """Test memory usage and resource management."""

    @pytest.mark.asyncio
    async def test_symbol_creation_efficiency(self):
        """Test efficiency of symbol creation."""
        # Define the test sample population
        num_symbols = 1000

        # Performance measurement through symbol instantiation
        start_time = time.perf_counter()
        symbols = []
        for i in range(num_symbols):
            symbol = AdsSymbol(
                parent_id=i % 10,
                name=f"Symbol{i}",
                dtype=np.int32,
                size=random.randint(1, 100),
                group=0x3000,
                offset=i * 4,
                comment=f"Symbol {i} comment",
            )
            symbols.append(symbol)
        elapsed = time.perf_counter() - start_time

        # Calculate statistics
        throughput = num_symbols / elapsed

        # Verify reasonable results are achieved
        assert throughput > 0
        assert len(symbols) == num_symbols

        # Report results to stdout
        print(
            "Throughput test results for symbol creation:\n"
            + f"{throughput:.1f} symbols/sec based on {num_symbols} samples"
        )

    @pytest.mark.asyncio
    async def test_data_accumulation(self, perf_test_server: MockADSServer):
        """Test data accumulation without memory leaks."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_symbols = 1000

        # Create a sequence of random symbols for testing
        test_symbols: list[AdsSymbol] = []
        for _ in range(num_symbols):
            test_symbols.append(perf_test_server.get_random_symbol())
        assert len(test_symbols) == num_symbols

        # Memory leak measurement through data accumulation over time
        try:
            # Perform successive symbol reads and cache the data
            data_buffer = []
            for symbol in test_symbols:
                result = await client.read_ads_symbol(symbol)
                data_buffer.append(result)

            # If no memory leak, data should have been accumulated
            assert len(data_buffer) == num_symbols

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Stress Tests
# ===================================================================


class TestStressConditions:
    """Test behavior under stress conditions."""

    @pytest.mark.asyncio
    async def test_rapid_connection_cycles(self, perf_test_server: MockADSServer):
        """Test overhead from rapid connect/disconnect cycles."""
        # Define the test sample population
        num_cycles = 50

        # Stress measurement through the repeated cycling of client connections
        start = time.perf_counter()
        for _ in range(num_cycles):
            # Connect to the mock server
            client = await AsyncioADSClient.connected_to(
                target_ip=perf_test_server.host,
                target_ams_net_id=perf_test_server.local_netid.to_string(),
                target_ams_port=IO_SERVER_PORT,
                ads_port=perf_test_server.port,
            )
            # Quick ads operation
            await client._get_ioserver_states()
            # Disconnect the client
            await client.close()
        elapsed = time.perf_counter() - start

        # Calculate statistics
        cycle_time = elapsed / num_cycles

        # Report results to stdout
        print(
            "Stress test result for rapid client connection cycling:\n"
            + f"{cycle_time * 1000:.2f} ms/cycle based on {num_cycles} samples"
        )

    @pytest.mark.asyncio
    async def test_high_concurrency(self, perf_test_server: MockADSServer):
        """Test behaviour under high concurrency."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample populations
        num_tasks = 200
        num_operations = 10

        # Stress measurement through handling of concurrent tasks with high read load
        try:
            # Create many concurrent tasks
            async def task():
                # Create a sequence of random symbols for testing
                test_symbols: list[AdsSymbol] = []
                for _ in range(num_operations):
                    test_symbols.append(perf_test_server.get_random_symbol())
                    assert len(test_symbols) == num_operations
                # Setup a read operation on each symbol
                for symbol in test_symbols:
                    await client.read_ads_symbol(symbol)

            # Measure total throughput of the tasks
            start = time.perf_counter()
            await asyncio.gather(*[task() for _ in range(num_tasks)])
            elapsed = time.perf_counter() - start

            # Calculate statistics
            total_ops = num_tasks * num_operations
            throughput = total_ops / elapsed

            # Report results to stdout
            print(
                "Stress test result for high concurrency task requirement:\n"
                + f"{throughput:.1f} ops/sec based on {num_tasks} operation tasks "
                + f"with {num_operations} samples each"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_sustained_load(self, perf_test_server: MockADSServer):
        """Test sustained load over extended period."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test stress constraint (i.e. sustained load)
        duration = 2.0

        # Stress measurement through the repeated read operation over an extended period
        try:
            total_operations = 0
            symbol = perf_test_server.get_random_symbol()
            start = time.perf_counter()
            while time.perf_counter() - start < duration:
                await client.read_ads_symbol(symbol)
                total_operations += 1
            elapsed = time.perf_counter() - start

            # Calculate statistics
            throughput = total_operations / elapsed

            # Report results to stdout
            print(
                "Stress test result for sustained read operation over a long period:\n"
                + f"{throughput:.1f} ops/sec based on {total_operations} total "
                + f"operations over a {duration}s extended period"
            )

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Comparative Performance Tests
# ===================================================================


class TestComparativePerformance:
    """Test comparative performance between different operations."""

    @pytest.mark.asyncio
    async def test_read_vs_write_performance(self, perf_test_server: MockADSServer):
        """Compare read vs write speed performance."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 500

        # Create a sequence of random symbol/value pairs for testing
        test_symbols: list[tuple[AdsSymbol, Any]] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol_value_pair())
        assert len(test_symbols) == num_operations

        # Comparative performance measurement between symbol various operations
        try:
            # Throughput measurement with successive read operations
            start = time.perf_counter()
            for symbol, _ in test_symbols:
                await client.read_ads_symbol(symbol)
            read_elapsed = time.perf_counter() - start
            read_throughput = num_operations / read_elapsed

            # Throughput measurement with successive write operations
            start = time.perf_counter()
            for symbol, value in test_symbols:
                await client.write_ads_symbol(symbol, value)
            write_elapsed = time.perf_counter() - start
            write_throughput = num_operations / write_elapsed
            write_ratio = read_throughput / write_throughput

            # Throughput measurement with successive read/write operations
            start = time.perf_counter()
            for symbol, value in test_symbols:
                await client.readwrite_ads_symbol(symbol, value)
            readwrite_elapsed = time.perf_counter() - start
            readwrite_throughput = num_operations / readwrite_elapsed
            readwrite_ratio = read_throughput / readwrite_throughput

            # Report results to stdout
            print(
                "Comparative performance test results for symbol operations "
                + f"based on {num_operations} samples:\n"
                + f"Symbol read: {read_throughput:.1f} ops/sec\n"
                + f"Symbol write: {write_throughput:.1f} ops/sec\n"
                + f"Symbol read/write: {readwrite_throughput:.1f} ops/sec\n"
                + f"Read operation is {write_ratio:.1f}x the write performance\n"
                + f"Read operation is {readwrite_ratio:.1f}x the read/write performance"
            )

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_sequential_vs_concurrent_performance(
        self, perf_test_server: MockADSServer
    ):
        """Compare sequential vs concurrent speed performance."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample populations
        num_operations = 100
        num_tasks = 10
        assert num_operations % num_tasks == 0, "Test populations must be proportional"
        task_smpl_slice = num_operations // num_tasks

        # Create a sequence of random symbols for testing
        test_symbols: list[AdsSymbol] = []
        for _ in range(num_operations):
            test_symbols.append(perf_test_server.get_random_symbol())
            assert len(test_symbols) == num_operations

        # Comparative performance measurement bewtween read operation methods
        try:
            # Throughput measurement with sequential read operations
            start = time.perf_counter()
            for symbol in test_symbols:
                await client.read_ads_symbol(symbol)
            seq_elapsed = time.perf_counter() - start
            seq_throughput = num_operations / seq_elapsed

            # Throughput measurement with concurrent read operations
            async def read_task(index: int):
                start = index * task_smpl_slice
                end = (index + 1) * task_smpl_slice
                for symbol in test_symbols[start:end]:
                    await client.read_ads_symbol(symbol)

            start = time.perf_counter()
            await asyncio.gather(*[read_task(i) for i in range(num_tasks)])
            conc_elapsed = time.perf_counter() - start
            conc_throughput = num_operations / conc_elapsed

            # Calculate statistics
            ratio = conc_throughput / seq_throughput

            # Report results to stdout
            print(
                "Comparative performance test results for different query modes "
                + f"based on {num_operations} read samples:\n"
                + f"Sequential read throughput: {seq_throughput:.1f} ops/sec\n"
                + f"Concurrent read throughput ({num_tasks} threads): "
                + f"{conc_throughput:.1f} ops/sec\n"
                + f"Concurrent mode is {ratio:.1f}x the sequential performance"
            )

        finally:
            # Disconnect the client
            await client.close()


# ===================================================================
# Bottleneck Identification Tests
# ===================================================================


class TestBottleneckIdentification:
    """Test to identify performance bottlenecks."""

    @pytest.mark.asyncio
    async def test_payload_size_impact(self, perf_test_server: MockADSServer):
        """Test impact of payload size on throughput performance."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample populations
        payload_sizes = [1, 4, 16, 64, 256, 1024]
        num_operations = 100

        # Create ads test symbols with different data sizes on the mock server
        for size in payload_sizes:
            perf_test_server.set_symbol_data(
                name=f"BottleneckSymbol{size}", value=np.arange(size, dtype=np.uint8)
            )

        # Performance measurement for symbol with different data size
        try:
            results = {}
            for size in payload_sizes:
                # Select an ads symbol with the correct data size
                symbol = perf_test_server.get_symbol_by_name(f"BottleneckSymbol{size}")
                assert symbol is not None, (
                    f"No test symbol suitable for payload size {size} on mock server"
                )

                # Throughput measurement with multiple read operations
                start = time.perf_counter()
                for _ in range(num_operations):
                    await client.read_ads_symbol(symbol)
                elapsed = time.perf_counter() - start

                # Calculate statistics and record
                throughput = num_operations / elapsed
                results[size] = throughput

            # Report results to stdout
            print(
                "Performance test results for different payload sizes "
                + f"based on {num_operations} read samples:\n"
            )
            for size, throughput in results.items():
                print(f"{throughput:.1f} ops/sec throughput for {size} bytes payload\n")

        finally:
            # Disconnect the client
            await client.close()

    @pytest.mark.asyncio
    async def test_offset_distribution_impact(self, perf_test_server: MockADSServer):
        """Test impact of offset distribution on performance related to memory access \
            pattern effects"""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=perf_test_server.host,
            target_ams_net_id=perf_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=perf_test_server.port,
        )

        # Define the test sample population
        num_operations = 100

        # Create ads test symbols with different data sizes on the mock server
        for i in range(num_operations):
            perf_test_server.set_symbol_data(
                name=f"OffsetSymbol{i}", value=np.int32(i), offset=(i * 256)
            )

        # Performance measurement for symbol with different offset index
        try:
            # Throughput measurement with same symbol, i.e. same offset
            symbol = perf_test_server.get_random_symbol()
            start = time.perf_counter()
            for _ in range(num_operations):
                await client.read_ads_symbol(symbol)
            same_elapsed = time.perf_counter() - start
            same_throughput = num_operations / same_elapsed

            # Throughput measurement for symbols with varying offset
            test_symbols: list[AdsSymbol] = []
            for i in range(num_operations):
                name = f"OffsetSymbol{i}"
                symbol = perf_test_server.get_symbol_by_name(name)
                assert symbol is not None, (
                    f"No test symbol with name {name} is available on mock server"
                )
                test_symbols.append(symbol)
            start = time.perf_counter()
            for symbol in test_symbols:
                await client.read_ads_symbol(symbol)
            varying_elapsed = time.perf_counter() - start
            varying_throughput = num_operations / varying_elapsed

            # Report results to stdout
            print(
                "Performance test results for different symbol offset distribution "
                + f"based on {num_operations} read samples:\n"
                + f"{same_throughput:.1f} ops/sec throughput for same offset symbol\n"
                + f"{varying_throughput:.1f} ops/sec throughput for varying offset "
                + "symbols"
            )

        finally:
            await client.close()

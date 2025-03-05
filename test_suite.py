import unittest
import threading
import time
import socket
import os
import random
from datetime import datetime
from queue import Queue

# Import the VirtualMachine class and main functions
from vm import VirtualMachine
import main  # to access setup_vms and virtual_machines

class TestVirtualMachine(unittest.TestCase):
    def setUp(self):
        # Create a dummy VM on an unused port with no peers
        self.vm = VirtualMachine(999, 12000, [], 5)
        # Force the VM to be "running" so that we can test tick and update methods
        self.vm.running = True
        # Ensure the VM has an internal message queue for testing
        if not hasattr(self.vm, 'message_queue'):
            self.vm.message_queue = Queue()

    def tearDown(self):
        self.vm.stop()
        log_file = f"vm_{self.vm.id}.log"
        if os.path.exists(log_file):
            os.remove(log_file)

    def test_update_logical_clock_no_message(self):
        # Without a received message, the logical clock should simply increment.
        initial = self.vm.logical_clock
        self.vm.update_logical_clock()
        self.assertEqual(self.vm.logical_clock, initial + 1)

    def test_update_logical_clock_with_message(self):
        # When given a received message time, the clock becomes max(current, received) + 1.
        self.vm.logical_clock = 3
        self.vm.update_logical_clock(5)
        self.assertEqual(self.vm.logical_clock, 6)  # max(3,5) + 1 = 6

    def test_update_logical_clock_with_lower_message(self):
        # If the received clock is lower than current, clock still increments.
        self.vm.logical_clock = 10
        self.vm.update_logical_clock(4)
        self.assertEqual(self.vm.logical_clock, 11)  # max(10,4) + 1 = 11

    def test_process_message(self):
        # Insert a message into the queue and process it.
        self.vm.logical_clock = 0
        self.vm.message_queue.put(10)
        processed = self.vm.process_message()
        self.assertTrue(processed)
        # Logical clock becomes max(0,10) + 1 = 11.
        self.assertEqual(self.vm.logical_clock, 11)

    def test_multiple_message_processing(self):
        # Enqueue multiple messages and process them sequentially.
        self.vm.logical_clock = 0
        messages = [2, 7, 3]
        for msg in messages:
            self.vm.message_queue.put(msg)
        # Process first message
        self.vm.process_message()  # clock: max(0,2) + 1 = 3
        self.assertEqual(self.vm.logical_clock, 3)
        # Process second message
        self.vm.process_message()  # clock: max(3,7) + 1 = 8
        self.assertEqual(self.vm.logical_clock, 8)
        # Process third message
        self.vm.process_message()  # clock: max(8,3) + 1 = 9
        self.assertEqual(self.vm.logical_clock, 9)

    def test_internal_event(self):
        # Calling an internal event should increment the logical clock.
        initial = self.vm.logical_clock
        self.vm.internal_event()
        self.assertEqual(self.vm.logical_clock, initial + 1)

    def test_multiple_internal_events(self):
        # Calling internal_event multiple times should increment the clock accordingly.
        initial = self.vm.logical_clock
        for _ in range(5):
            self.vm.internal_event()
        self.assertEqual(self.vm.logical_clock, initial + 5)

    def test_send_message_no_connection(self):
        # Attempting to send a message without a connection should log an error but not crash.
        try:
            self.vm.send_message(12345)
        except Exception as e:
            self.fail(f"send_message raised an exception unexpectedly: {e}")

    def test_peer_connections(self):
        # Create two VMs that are peers to one another and verify that they connect.
        vm1 = VirtualMachine(1, 13000, [13001], 5)
        vm2 = VirtualMachine(2, 13001, [13000], 5)
        vm1.start()
        vm2.start()
        # Allow time for servers to start
        time.sleep(2)
        vm1.connect_to_peers()
        vm2.connect_to_peers()
        self.assertIn(13001, vm1.peer_connections)
        self.assertIn(13000, vm2.peer_connections)
        # Clean up
        vm1.stop()
        vm2.stop()
        for vm_id in [1, 2]:
            log_file = f"vm_{vm_id}.log"
            if os.path.exists(log_file):
                os.remove(log_file)

    def test_run_stop(self):
        # Test that running a VM in its own thread and then stopping it sets the running flag to False.
        vm = VirtualMachine(100, 14000, [], 5)
        t = threading.Thread(target=vm.run)
        t.daemon = True
        t.start()
        time.sleep(2)
        vm.stop()
        self.assertFalse(vm.running)
        log_file = f"vm_{vm.id}.log"
        if os.path.exists(log_file):
            os.remove(log_file)

    def test_stop_method_idempotence(self):
        # Calling stop multiple times should not raise an error.
        try:
            self.vm.stop()
            self.vm.stop()  # second call should be safe
        except Exception as e:
            self.fail(f"Calling stop() twice raised an exception: {e}")

    def test_run_method_thread(self):
        # Run the vm in a separate thread, send a message, and ensure it is processed.
        self.vm.logical_clock = 0
        # Start the run method in a separate thread
        t = threading.Thread(target=self.vm.run)
        t.daemon = True
        t.start()
        # Enqueue a message after a short delay
        time.sleep(1)
        self.vm.message_queue.put(15)
        time.sleep(1)
        # Processed message should update logical clock to max(current,15)+1
        self.assertGreaterEqual(self.vm.logical_clock, 16)

class TestMainFunctionality(unittest.TestCase):
    def setUp(self):
        # Clear the global list of VMs in main before setting up new ones.
        main.virtual_machines.clear()
        self.vms = main.setup_vms(num_vms=3, base_port=15000)

    def tearDown(self):
        for vm in self.vms:
            vm.stop()
            log_file = f"vm_{vm.id}.log"
            if os.path.exists(log_file):
                os.remove(log_file)
        # Clear the global list again to keep tests isolated.
        main.virtual_machines.clear()

    def test_setup_vms(self):
        # Ensure that 3 VMs are set up with proper ports and clock rates.
        self.assertEqual(len(self.vms), 3)
        expected_ports = [15000, 15001, 15002]
        for i, vm in enumerate(self.vms):
            self.assertEqual(vm.port, expected_ports[i])
            self.assertTrue(1 <= vm.clock_rate <= 6)

    def test_run_vms(self):
        # Start VMs in threads, let them run for a short time, then check if they are running.
        threads = main.run_vms(self.vms)
        time.sleep(3)  # Allow some ticks to occur.
        for vm in self.vms:
            self.assertTrue(vm.running)
        # Now stop all VMs and ensure they are not running.
        for vm in self.vms:
            vm.stop()
        time.sleep(1)
        for vm in self.vms:
            self.assertFalse(vm.running)

    def test_setup_vms_unique_ids(self):
        # Ensure that VMs set up have unique IDs.
        ids = [vm.id for vm in self.vms]
        self.assertEqual(len(ids), len(set(ids)), "VM IDs should be unique")

    def test_random_clock_rate_range(self):
        # Verify that the clock rates for each VM are within the expected range.
        for vm in self.vms:
            self.assertGreaterEqual(vm.clock_rate, 1)
            self.assertLessEqual(vm.clock_rate, 6)

    def test_run_and_stop_all_vms(self):
        # Run all VMs, wait, then stop them and verify none are running.
        threads = main.run_vms(self.vms)
        time.sleep(3)
        for vm in self.vms:
            self.assertTrue(vm.running)
        for vm in self.vms:
            vm.stop()
        time.sleep(1)
        for vm in self.vms:
            self.assertFalse(vm.running)

if __name__ == '__main__':
    unittest.main()

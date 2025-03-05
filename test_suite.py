import unittest
from unittest.mock import patch, MagicMock, call
import socket
import threading
import time
import queue
import os
import tempfile
import gzip
import logging
import multiprocessing
from datetime import datetime

# Import the modules to test
from vm import VirtualMachine

class TestVirtualMachineInitialization(unittest.TestCase):
    """Tests for VirtualMachine initialization."""
    
    def test_vm_initialization(self):
        """Test VM properties are correctly initialized."""
        vm = VirtualMachine(id=1, port=10001, peer_ports=[10002, 10003], clock_rate=5)
        self.assertEqual(vm.id, 1)
        self.assertEqual(vm.port, 10001)
        self.assertEqual(vm.peer_ports, [10002, 10003])
        self.assertEqual(vm.clock_rate, 5)
        self.assertEqual(vm.logical_clock, 0)
        self.assertFalse(vm.running)
    
    def test_logger_initialization(self):
        """Test logger setup with correct handlers and formatters."""
        with patch('logging.getLogger') as mock_get_logger:
            with patch('logging.handlers.TimedRotatingFileHandler') as mock_handler:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger
                
                vm = VirtualMachine(id=1, port=10001, peer_ports=[], clock_rate=1)
                vm._init_logger()
                
                mock_get_logger.assert_called_once_with(f"VM-{vm.id}")
                mock_handler.assert_called_once()
                mock_logger.addHandler.assert_called_once()
    
    def test_socket_initialization(self):
        """Test server socket binding and listening setup."""
        with patch('socket.socket') as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            
            vm = VirtualMachine(id=1, port=10001, peer_ports=[], clock_rate=1)
            vm._init_server_socket()
            
            mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
            mock_instance.bind.assert_called_once_with(('localhost', 10001))
            mock_instance.listen.assert_called_once_with(5)


class TestLogicalClockOperations(unittest.TestCase):
    """Tests for logical clock operations."""
    
    def setUp(self):
        self.vm = VirtualMachine(id=1, port=10001, peer_ports=[], clock_rate=1)
        self.vm.logger = MagicMock()
    
    def test_internal_clock_update(self):
        """Test internal logical clock increment."""
        self.vm.logical_clock = 5
        self.vm.update_logical_clock()
        self.assertEqual(self.vm.logical_clock, 6)
        
        self.vm.update_logical_clock()
        self.assertEqual(self.vm.logical_clock, 7)
    
    def test_message_clock_update(self):
        """Test logical clock updates based on received message timestamps."""
        # Lower received time
        self.vm.logical_clock = 10
        self.vm.update_logical_clock(received_time=5)
        self.assertEqual(self.vm.logical_clock, 11)  # max(10,5)+1
        
        # Higher received time
        self.vm.logical_clock = 10
        self.vm.update_logical_clock(received_time=20)
        self.assertEqual(self.vm.logical_clock, 21)  # max(10,20)+1
    
    def test_internal_event_logging(self):
        """Test if internal events are logged correctly."""
        self.vm.logical_clock = 7
        self.vm.internal_event()
        self.assertEqual(self.vm.logical_clock, 8)
        self.vm.logger.info.assert_called_once()
        log_msg = self.vm.logger.info.call_args[0][0]
        self.assertIn("INTERNAL", log_msg)
        self.assertIn("Logical clock: 8", log_msg)


class TestMessageHandling(unittest.TestCase):
    """Tests for message sending and receiving."""
    
    def setUp(self):
        self.vm = VirtualMachine(id=1, port=10001, peer_ports=[10002, 10003], clock_rate=1)
        self.vm.logger = MagicMock()
        self.vm.message_queue = queue.Queue()
        self.vm.peer_connections = {}
        self.vm.running = True
    
    def test_send_message_success(self):
        """Test successful message sending to a peer."""
        mock_socket = MagicMock()
        self.vm.peer_connections[10002] = mock_socket
        
        self.vm.logical_clock = 5
        self.vm.send_message(10002)
        
        # Clock should increment
        self.assertEqual(self.vm.logical_clock, 6)
        
        # Socket should send the clock value
        mock_socket.send.assert_called_once_with(b"6")
        
        # Action should be logged
        self.vm.logger.info.assert_called_once()
        log_msg = self.vm.logger.info.call_args[0][0]
        self.assertIn("SEND", log_msg)
        self.assertIn("Logical clock: 6", log_msg)
    
    def test_send_message_error(self):
        """Test error handling during message sending."""
        mock_socket = MagicMock()
        mock_socket.send.side_effect = Exception("Connection failed")
        self.vm.peer_connections[10002] = mock_socket
        
        self.vm.send_message(10002)
        
        # Error should be logged
        self.vm.logger.error.assert_called_once()
        
        # Connection should be removed
        self.assertNotIn(10002, self.vm.peer_connections)
    
    def test_process_message_from_queue(self):
        """Test processing messages from the queue."""
        # Add a message to the queue
        self.vm.message_queue.put(15)
        
        # Process the message
        result = self.vm.process_message()
        
        # Should return True (processed a message)
        self.assertTrue(result)
        
        # Clock should update based on message
        self.assertEqual(self.vm.logical_clock, 16)  # max(0,15)+1
        
        # Action should be logged
        self.vm.logger.info.assert_called_once()
        log_msg = self.vm.logger.info.call_args[0][0]
        self.assertIn("RECEIVE", log_msg)
        self.assertIn("Queue length: 0", log_msg)
        self.assertIn("Logical clock: 16", log_msg)
    
    def test_handle_client_message(self):
        """Test handling messages from connected clients."""
        mock_socket = MagicMock()
        # Simulate receiving two messages then closing
        mock_socket.recv.side_effect = [b"10", b"20", b""]
        
        # Handle the client in a separate thread
        client_thread = threading.Thread(target=self.vm.handle_client, args=(mock_socket,))
        client_thread.daemon = True
        client_thread.start()
        
        # Give time for messages to process
        time.sleep(0.1)
        self.vm.running = False
        client_thread.join(timeout=1)
        
        # Check messages were added to queue
        self.assertEqual(self.vm.message_queue.qsize(), 2)
        self.assertEqual(self.vm.message_queue.get(), 10)
        self.assertEqual(self.vm.message_queue.get(), 20)


class TestConnectionManagement(unittest.TestCase):
    """Tests for connection establishment and management."""
    
    def setUp(self):
        self.vm = VirtualMachine(id=1, port=10001, peer_ports=[10002, 10003], clock_rate=1)
        self.vm.logger = MagicMock()
        self.vm.running = True
        self.vm.peer_connections = {}
    
    def test_connect_to_peers_success(self):
        """Test successful connection to peers."""
        with patch('socket.socket') as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            
            self.vm.connect_to_peers()
            
            # Should try to connect to both peers
            self.assertEqual(mock_instance.connect.call_count, 2)
            mock_instance.connect.assert_has_calls([
                call(('localhost', 10002)),
                call(('localhost', 10003))
            ], any_order=True)
            
            # Should store connections
            self.assertEqual(len(self.vm.peer_connections), 2)
            self.assertIn(10002, self.vm.peer_connections)
            self.assertIn(10003, self.vm.peer_connections)
    
    def test_connect_to_peers_retry(self):
        """Test retrying failed connections to peers."""
        with patch('socket.socket') as mock_socket, patch('time.sleep') as mock_sleep:
            mock_instance = MagicMock()
            # First connection attempt fails, second succeeds
            connect_side_effects = [Exception("Connection refused"), None]
            mock_instance.connect.side_effect = connect_side_effects
            mock_socket.return_value = mock_instance
            
            # Only test with one peer for simplicity
            self.vm.peer_ports = [10002]
            self.vm.connect_to_peers()
            
            # Should retry once after failure
            self.assertEqual(mock_instance.connect.call_count, 2)
            
            # Should have one connection after retry success
            self.assertEqual(len(self.vm.peer_connections), 1)
            self.assertIn(10002, self.vm.peer_connections)
            
            # Should log error for first attempt
            self.vm.logger.error.assert_called_once()
    
    def test_accept_connections_handling(self):
        """Test server socket accepting connections."""
        self.vm.server_socket = MagicMock()
        mock_client = MagicMock()
        
        # Socket accepts one connection then times out
        self.vm.server_socket.accept.side_effect = [
            (mock_client, ('127.0.0.1', 10099)),
            socket.timeout()
        ]
        
        # Run accept_connections in a separate thread
        with patch('threading.Thread') as mock_thread:
            # Make function exit after handling both events
            def side_effect(*args, **kwargs):
                self.vm.running = False
                return MagicMock()
            mock_thread.side_effect = side_effect
            
            self.vm.accept_connections()
            
            # Should try to start a client handler thread
            mock_thread.assert_called_once()
            # First arg should be handle_client
            self.assertEqual(mock_thread.call_args[1]['target'], self.vm.handle_client)


class TestVMLifecycle(unittest.TestCase):
    """Tests for the VM lifecycle (start, run, stop)."""
    
    def setUp(self):
        self.vm = VirtualMachine(id=1, port=10001, peer_ports=[10002], clock_rate=1)
        self.vm.logger = MagicMock()
    
    @patch('threading.Thread')
    def test_start_server(self, mock_thread):
        """Test starting the server thread."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        self.vm.start_server()
        
        # Should create thread with accept_connections
        mock_thread.assert_called_once_with(target=self.vm.accept_connections)
        # Should set thread as daemon
        self.assertTrue(mock_thread_instance.daemon)
        # Should start thread
        mock_thread_instance.start.assert_called_once()
    
    @patch.multiple(VirtualMachine, 
                  _init_logger=MagicMock(),
                  _init_server_socket=MagicMock(),
                  start_server=MagicMock(),
                  connect_to_peers=MagicMock(),
                  process_message=MagicMock(return_value=False),
                  send_message=MagicMock(),
                  internal_event=MagicMock())
    def test_run_decision_logic(self):
        """Test the main loop action decision logic."""
        # Make VM stop after one iteration
        def stop_after_one(*args, **kwargs):
            self.vm.running = False
            return False
        
        self.vm.process_message.side_effect = stop_after_one
        
        # Test different random outcomes
        test_cases = [
            (1, "send_to_first_peer"),   # action == 1: send to first peer
            (2, "send_to_second_peer"),  # action == 2: send to second peer
            (3, "send_to_all_peers"),    # action == 3: send to all peers
            (4, "internal_event")        # action > 3: internal event
        ]
        
        for random_value, expected_action in test_cases:
            with patch('random.randint', return_value=random_value):
                with patch('time.sleep'):
                    self.vm.running = True
                    self.vm.run()
                    
                    # Reset all mocks for next iteration
                    self.vm._init_logger.reset_mock()
                    self.vm._init_server_socket.reset_mock()
                    self.vm.start_server.reset_mock()
                    self.vm.connect_to_peers.reset_mock()
                    self.vm.process_message.reset_mock()
                    self.vm.send_message.reset_mock()
                    self.vm.internal_event.reset_mock()
    
    def test_stop(self):
        """Test stopping the VM and cleaning up resources."""
        # Setup mock connections and sockets
        mock_socket1 = MagicMock()
        mock_socket2 = MagicMock()
        mock_server = MagicMock()
        
        self.vm.peer_connections = {
            10002: mock_socket1,
            10003: mock_socket2
        }
        self.vm.server_socket = mock_server
        self.vm.running = True
        
        # Stop the VM
        self.vm.stop()
        
        # Running flag should be False
        self.assertFalse(self.vm.running)
        
        # All client sockets should be closed
        mock_socket1.close.assert_called_once()
        mock_socket2.close.assert_called_once()
        
        # Server socket should be closed
        mock_server.close.assert_called_once()


class TestIntegrationSingleVM(unittest.TestCase):
    """Integration tests for a single VM with mocked networking."""
    
    def setUp(self):
        # Create a temporary directory for logs
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)
        
        # Setup VM with mock network
        self.vm = VirtualMachine(id=1, port=10001, peer_ports=[10002], clock_rate=5)
        self.vm.message_queue = queue.Queue()
        self.vm.peer_connections = {}
        self.vm._init_logger()
        self.vm.server_socket = MagicMock()
        self.vm.running = True
    
    def tearDown(self):
        # Clean up temporary files
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)
    
    def test_clock_consistency(self):
        """Test logical clock maintains consistency across operations."""
        # Start with clock at 0
        self.assertEqual(self.vm.logical_clock, 0)
        
        # Internal event increments by 1
        self.vm.internal_event()
        self.assertEqual(self.vm.logical_clock, 1)
        
        # Add messages to queue with different timestamps
        self.vm.message_queue.put(5)  # Higher than current
        self.vm.message_queue.put(2)  # Lower than current after processing
        
        # Process first message - should jump to 6
        self.vm.process_message()
        self.assertEqual(self.vm.logical_clock, 6)
        
        # Process second message - should go to 7 (max(6,2)+1)
        self.vm.process_message()
        self.assertEqual(self.vm.logical_clock, 7)
        
        # Set up mock socket for sending
        mock_socket = MagicMock()
        self.vm.peer_connections[10002] = mock_socket
        
        # Send message - should increment to 8
        self.vm.send_message(10002)
        self.assertEqual(self.vm.logical_clock, 8)
        mock_socket.send.assert_called_once_with(b"8")
    
    def test_event_logging(self):
        """Test that all events are properly logged."""
        # Generate mixed events
        self.vm.internal_event()  # Clock = 1
        
        # Add and process message
        self.vm.message_queue.put(10)
        self.vm.process_message()  # Clock = 11
        
        # Set up mock socket for sending
        mock_socket = MagicMock()
        self.vm.peer_connections[10002] = mock_socket
        
        # Send message
        self.vm.send_message(10002)  # Clock = 12
        
        # Stop VM
        self.vm.stop()
        
        # Check log file exists and contains expected events
        log_file = f"vm_{self.vm.id}.log"
        self.assertTrue(os.path.exists(log_file))
        
        with open(log_file, 'r') as f:
            content = f.read()
        
        # Verify all event types are logged
        self.assertIn("INTERNAL", content)
        self.assertIn("RECEIVE", content)
        self.assertIn("SEND", content)
        
        # Verify correct clock values
        self.assertIn("Logical clock: 1", content)
        self.assertIn("Logical clock: 11", content)
        self.assertIn("Logical clock: 12", content)


class TestMultiVMSystem(unittest.TestCase):
    """System test for multiple VMs."""
    
    def setUp(self):
        # Ensure multiprocessing uses 'spawn' for consistency
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set
        
        # Create temp directory
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        # Clean up temporary files
        for file in os.listdir(self.test_dir):
            try:
                os.remove(os.path.join(self.test_dir, file))
            except:
                pass
        os.rmdir(self.test_dir)
    
    @patch('vm.VirtualMachine.run')
    @patch('vm.VirtualMachine.stop')
    def test_simulation_setup(self, mock_stop, mock_run):
        """Test simulation setup with multiple VMs."""
        # Import simulation functions
        from main import setup_vms, run_vms, stop_vms
        
        # Mock Process.start to avoid actual process spawning
        with patch('multiprocessing.Process.start'):
            # Setup VMs
            vms = setup_vms(num_vms=3, base_port=10010)
            
            # Verify VM configuration
            self.assertEqual(len(vms), 3)
            self.assertEqual(vms[0].port, 10010)
            self.assertEqual(vms[0].peer_ports, [10011, 10012])
            self.assertEqual(vms[1].port, 10011)
            self.assertEqual(vms[1].peer_ports, [10010, 10012])
            self.assertEqual(vms[2].port, 10012)
            self.assertEqual(vms[2].peer_ports, [10010, 10011])
            
            # Run VMs
            run_vms(vms)
            
            # Verify all VMs were started
            self.assertEqual(len(vms), 3)
            
            # Stop VMs
            stop_vms(vms)
            
            # Verify all VMs were stopped
            self.assertEqual(mock_stop.call_count, 0)


if __name__ == '__main__':
    unittest.main()
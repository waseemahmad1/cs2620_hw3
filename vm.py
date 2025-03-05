import socket
import threading
import time
import random
import logging
from datetime import datetime
import queue
import os
import gzip
import logging.handlers  # For log rotation
from multiprocessing import Process

class VirtualMachine(Process):
    def __init__(self, id, port, peer_ports, clock_rate):
        Process.__init__(self)
        self.id = id
        self.port = port
        self.peer_ports = peer_ports
        self.clock_rate = clock_rate  # Ticks per second
        self.logical_clock = 0
        self.running = False
        # Don't initialize objects that can't be pickled here

    def _init_logger(self):
        self.logger = logging.getLogger(f"VM-{self.id}")
        self.logger.setLevel(logging.INFO)
        log_filename = f"vm_{self.id}.log"
        handler = logging.handlers.TimedRotatingFileHandler(
            log_filename, when="M", interval=2, backupCount=5)
        handler.suffix = "%Y-%m-%d_%H-%M-%S.gz"
        def gzip_rotator(source, dest):
            with open(source, 'rb') as sf:
                with gzip.open(dest, 'wb') as df:
                    df.writelines(sf)
            os.remove(source)
        handler.rotator = gzip_rotator
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _init_server_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)

    def start_server(self):
        """Start a daemon thread to accept incoming connections."""
        self.server_thread = threading.Thread(target=self.accept_connections)
        self.server_thread.daemon = True
        self.server_thread.start()

    def accept_connections(self):
        """Accept connections from peers."""
        self.server_socket.settimeout(1.0)
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.daemon = True
                client_handler.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting connection: {e}")

    def handle_client(self, client_socket):
        """Handle messages from a connected peer."""
        client_socket.settimeout(1.0)
        while self.running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break
                received_time = int(data.decode())
                self.message_queue.put(received_time)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error handling client: {e}")
                break
        client_socket.close()

    def connect_to_peers(self):
        """Connect to all specified peers."""
        for peer_port in self.peer_ports:
            if peer_port in self.peer_connections:
                continue
            retries = 5
            while retries > 0 and self.running:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect(('localhost', peer_port))
                    self.peer_connections[peer_port] = s
                    self.logger.info(f"Connected to peer at port {peer_port}")
                    break
                except Exception as e:
                    self.logger.error(f"Failed to connect to peer at port {peer_port}: {e}")
                    retries -= 1
                    time.sleep(1)

    def update_logical_clock(self, received_time=None):
        """Update the logical clock per Lamport's algorithm."""
        if received_time is not None:
            self.logical_clock = max(self.logical_clock, received_time) + 1
        else:
            self.logical_clock += 1

    def send_message(self, peer_port):
        """Send a message (logical clock time) to a peer."""
        if peer_port not in self.peer_connections:
            self.logger.error(f"Not connected to peer at port {peer_port}")
            return
        try:
            self.update_logical_clock()
            message = str(self.logical_clock).encode()
            self.peer_connections[peer_port].send(message)
            self.logger.info(f"SEND to {peer_port}, System time: {datetime.now()}, Logical clock: {self.logical_clock}")
        except Exception as e:
            self.logger.error(f"Error sending message to peer at port {peer_port}: {e}")
            try:
                self.peer_connections[peer_port].close()
            except:
                pass
            del self.peer_connections[peer_port]

    def process_message(self):
        """Process one message from the queue (one per clock cycle)."""
        try:
            if not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                q_len = self.message_queue.qsize()
                self.update_logical_clock(message)
                self.logger.info(f"RECEIVE, System time: {datetime.now()}, Queue length: {q_len}, Logical clock: {self.logical_clock}")
                return True
        except queue.Empty:
            pass
        return False

    def internal_event(self):
        """Perform an internal event by updating the logical clock."""
        self.update_logical_clock()
        self.logger.info(f"INTERNAL, System time: {datetime.now()}, Logical clock: {self.logical_clock}")

    def run(self):
        """Main loop of the virtual machine process."""
        # Initialize non-pickleable objects here
        self.message_queue = queue.Queue()
        self.peer_connections = {}
        
        # Set up logging and server socket
        self._init_logger()
        self._init_server_socket()
        
        # Start the server 
        self.running = True
        self.start_server()
        
        time.sleep(1)  # Allow the server thread to initialize
        self.connect_to_peers()
        
        tick_interval = 1.0 / self.clock_rate
        try:
            while self.running:
                start_time = time.time()
                if not self.process_message():
                    action = random.randint(1, 10)
                    if action == 1 and self.peer_ports:
                        self.send_message(self.peer_ports[0])
                    elif action == 2 and self.peer_ports:
                        if len(self.peer_ports) >= 2:
                            self.send_message(self.peer_ports[1])
                        else:
                            self.send_message(self.peer_ports[0])
                    elif action == 3 and self.peer_ports:
                        for peer_port in self.peer_ports:
                            self.send_message(peer_port)
                    else:
                        self.internal_event()
                elapsed = time.time() - start_time
                sleep_time = max(0, tick_interval - elapsed)
                time.sleep(sleep_time)
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the virtual machine and clean up."""
        self.running = False
        if hasattr(self, 'peer_connections'):
            for s in self.peer_connections.values():
                try:
                    s.close()
                except:
                    pass
        if hasattr(self, 'server_socket'):
            try:
                self.server_socket.close()
            except:
                pass
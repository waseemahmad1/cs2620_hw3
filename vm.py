import socket
import threading
import time
import random
import logging
from datetime import datetime
import queue

class VirtualMachine:
    def __init__(self, id, port, peer_ports, clock_rate):
        self.id = id
        self.port = port
        self.peer_ports = peer_ports
        self.clock_rate = clock_rate  # Ticks per second
        self.logical_clock = 0
        self.message_queue = queue.Queue()
        self.running = False
        
        # Set up logging
        self.logger = logging.getLogger(f"VM-{id}")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(f"vm_{id}.log")
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Set up server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        
        # Connections to peers
        self.peer_connections = {}
    
    def start(self):
        """Start the virtual machine"""
        self.running = True
        
        # Start server thread to accept connections
        self.server_thread = threading.Thread(target=self.accept_connections)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def accept_connections(self):
        """Accept connections from peers"""
        self.server_socket.settimeout(1.0)  # Set timeout to allow checking running flag
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
        """Handle messages from a connected peer"""
        client_socket.settimeout(1.0)  # Set timeout to allow checking running flag
        while self.running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                # Assume the message is the logical clock time of the sender
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
        """Connect to all peers"""
        for peer_port in self.peer_ports:
            if peer_port in self.peer_connections:
                continue  # Already connected
            
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
        """Update the logical clock according to Lamport's algorithm"""
        if received_time is not None:
            self.logical_clock = max(self.logical_clock, received_time) + 1
        else:
            self.logical_clock += 1
    
    def send_message(self, peer_port):
        """Send a message (logical clock time) to a peer"""
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
            # Try to reconnect
            try:
                self.peer_connections[peer_port].close()
            except:
                pass
            del self.peer_connections[peer_port]
    
    def process_message(self):
        """Process a single message from the queue (one per clock cycle)"""
        try:
            # Non-blocking check for a message
            if not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                queue_length = self.message_queue.qsize()
                self.update_logical_clock(message)
                self.logger.info(f"RECEIVE, System time: {datetime.now()}, Queue length: {queue_length}, Logical clock: {self.logical_clock}")
                return True
        except queue.Empty:
            pass
        return False
    
    def internal_event(self):
        """Handle an internal event"""
        self.update_logical_clock()
        self.logger.info(f"INTERNAL, System time: {datetime.now()}, Logical clock: {self.logical_clock}")
    
    def run(self):
        """Run the main loop of the virtual machine"""
        if not self.running:
            self.start()
        
        # Give server time to start
        time.sleep(1)
        
        # Connect to peers
        self.connect_to_peers()
        
        tick_interval = 1.0 / self.clock_rate
        
        try:
            while self.running:
                start_time = time.time()
                
                # Process a message or perform a random action
                if not self.process_message():
                    # No message to process, perform a random action
                    action = random.randint(1, 10)
                    
                    if action == 1 and self.peer_ports:
                        # Send to the first peer in the list
                        self.send_message(self.peer_ports[0])
                    elif action == 2 and self.peer_ports:
                        # If there is a second peer, send to it; otherwise, send to the only peer
                        if len(self.peer_ports) >= 2:
                            self.send_message(self.peer_ports[1])
                        else:
                            self.send_message(self.peer_ports[0])
                    elif action == 3 and self.peer_ports:
                        # Send to all peers
                        for peer_port in self.peer_ports:
                            self.send_message(peer_port)
                    else:
                        # Internal event
                        self.internal_event()
                
                # Sleep to maintain clock rate
                elapsed = time.time() - start_time
                sleep_time = max(0, tick_interval - elapsed)
                time.sleep(sleep_time)
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the virtual machine"""
        self.running = False
        
        # Close peer connections
        for s in self.peer_connections.values():
            try:
                s.close()
            except:
                pass
        
        # Close server socket
        try:
            self.server_socket.close()
        except:
            pass

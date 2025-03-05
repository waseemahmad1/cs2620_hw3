import threading
import signal
import sys
import time
import random
import logging
from vm import VirtualMachine

# Set up global logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("main.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("Main")

# Global list to keep track of all VMs
virtual_machines = []

def setup_vms(num_vms = 3, base_port = 10000, min_rate = 1, max_rate = 6):
    """
    Set up multiple virtual machines with different clock rates.
    Each VM is created with a unique port and a random clock rate between min_rate and max_rate.
    """
    # Create ports for each VM
    ports = [base_port + i for i in range(num_vms)]
    
    # Create VMs
    for i in range(num_vms):
        # All other ports are peers
        peer_ports = [p for p in ports if p != ports[i]]
        
        # Random clock rate between min_rate and max_rate
        clock_rate = random.randint(min_rate, max_rate)
        
        vm = VirtualMachine(i+1, ports[i], peer_ports, clock_rate)
        virtual_machines.append(vm)
        
        logger.info(f"Created VM {i+1} on port {ports[i]} with clock rate {clock_rate} ticks/s")
    
    return virtual_machines

def run_vms(vms):
    """
    Start each VM in its own thread.
    """
    threads = []
    for vm in vms:
        thread = threading.Thread(target=vm.run)
        thread.daemon = True
        threads.append(thread)
        thread.start()
        logger.info(f"Started VM {vm.id}")
    
    return threads

def signal_handler(sig, frame):
    """
    Handle Ctrl+C to gracefully shut down all VMs.
    """
    logger.info("Shutting down all virtual machines...")
    for vm in virtual_machines:
        vm.stop()
    
    logger.info("Shutdown complete. Exiting.")
    sys.exit(0)

def main():
    """
    Main function to set up and run the system.
    """
    logger.info("Starting Lamport Clock Simulation")
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start VMs
    vms = setup_vms(num_vms=3)
    threads = run_vms(vms)
    
    logger.info("All VMs are running. Press Ctrl+C to stop.")
    
    try:
        # Keep the main thread alive to allow keyboard interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # This will be caught by the signal handler
        pass

if __name__ == "__main__":
    main()



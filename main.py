import threading
import signal
import sys
import time
import random
import logging
from vm import VirtualMachine

# global log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("main.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("Main")

virtual_machines = []

def setup_vms(num_vms = 3, base_port = 10000, min_rate = 1, max_rate = 6):
    # Create ports for each VM
    ports = [base_port + i for i in range(num_vms)]
    
    # Create VMs
    for i in range(num_vms):
        peer_ports = [p for p in ports if p != ports[i]]
        
        # Random clock rate between min_rate and max_rate
        clock_rate = random.randint(min_rate, max_rate)
        
        vm = VirtualMachine(i+1, ports[i], peer_ports, clock_rate)
        virtual_machines.append(vm)
        
        logger.info(f"Created VM {i+1} on port {ports[i]} with clock rate {clock_rate} ticks/s")
    
    return virtual_machines

def run_vms(vms):
    threads = []
    for vm in vms:
        thread = threading.Thread(target=vm.run)
        thread.daemon = True
        threads.append(thread)
        thread.start()
        logger.info(f"Started VM {vm.id}")
    
    return threads

def signal_handler(sig, frame):
    logger.info("Shutting down all virtual machines...")
    for vm in virtual_machines:
        vm.stop()
    
    logger.info("Shutdown complete. Exiting.")
    sys.exit(0)

def main():
    logger.info("Starting Lamport Clock Simulation")
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # create and start VMs
    vms = setup_vms(num_vms=3)
    threads = run_vms(vms)
    
    logger.info("All VMs are running. Press Ctrl+C to stop.")
    
    try:
        # Keep the main thread alive to allow keyboard interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()



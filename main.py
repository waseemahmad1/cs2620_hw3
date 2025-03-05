import signal
import sys
import time
import random
import logging
from vm import VirtualMachine

# Set up global logging for main.
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

def setup_vms(num_vms=3, base_port=10000, min_rate=1, max_rate=6):
    """Set up multiple VMs with unique ports, randomized clock rates, and peer lists."""
    ports = [base_port + i for i in range(num_vms)]
    for i in range(num_vms):
        peer_ports = [p for p in ports if p != ports[i]]
        clock_rate = random.randint(min_rate, max_rate)
        vm = VirtualMachine(i+1, ports[i], peer_ports, clock_rate)
        virtual_machines.append(vm)
        logger.info(f"Created VM {i+1} on port {ports[i]} with clock rate {clock_rate} ticks/s")
    return virtual_machines

def run_vms(vms):
    """Start each VM process."""
    for vm in vms:
        vm.start()  # Launch each VM as a separate process.
        logger.info(f"Started VM {vm.id}")

def stop_vms(vms):
    """Stop all VM processes and wait for them to terminate."""
    for vm in vms:
        if vm.is_alive():
            vm.running = False  # Signal the process to stop
            logger.info(f"Stopping VM {vm.id}")
            vm.join(timeout=2)  # Wait for process to terminate
            if vm.is_alive():
                logger.warning(f"VM {vm.id} did not terminate gracefully, terminating...")
                vm.terminate()  # Force terminate if it doesn't stop gracefully

def signal_handler(sig, frame):
    """Gracefully shut down all VMs on SIGINT."""
    logger.info("Shutting down all virtual machines...")
    stop_vms(virtual_machines)
    logger.info("Shutdown complete. Exiting.")
    sys.exit(0)

def main():
    logger.info("Starting Lamport Clock Simulation")
    signal.signal(signal.SIGINT, signal_handler)
    vms = setup_vms(num_vms=3)
    run_vms(vms)
    logger.info("All VMs are running. Press Ctrl+C to stop.")
    try:
        # Keep the main process running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_vms(vms)

if __name__ == "__main__":
    main()
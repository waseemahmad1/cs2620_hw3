# cs2620_hw3

The following exercise was completed collaboratively by Max Peng and Waseem Ahmad.

## Implementation Details

1. **Clock Rate:** Operates at a randomly assigned clock rate between 1–6 ticks per second.
2. **Communication:** Connects to all other VMs via TCP sockets, ensuring reliable message delivery.
3. **Message Queue:** Maintains an asynchronous queue for incoming messages that is processed independently of the VM’s clock rate.
4. **Logical Clock:** Updates according to Lamport's rules:
   - **Internal Event:** Increment clock by 1.
   - **Send Event:** Increment clock by 1, then send the updated clock value.
   - **Receive Event:** Set clock to `max(local_clock, received_clock) + 1`.
5. **Logging:** Records every event with timestamps, logical clock values, and other relevant information. Log files are rotated every 2 minutes for longer simulations and compressed with gzip to manage disk space efficiently.

## Project Structure

- **vm.py:** Defines the `VirtualMachine` class, handling logical clock updates, message passing, and event processing.
- **main.py:** Initializes and runs the virtual machines, managing process creation and overall simulation control.
- **test_suite.py:** Contains unit tests for various functionalities, including logical clock updates, message handling, and VM connectivity.
- **plots.py:** Parses log files, generates statistical summaries, and visualizes key performance metrics (e.g. queue lengths and clock jumps).
- **README.md:** Provides documentation for project setup, usage instructions, and design decisions.

## Requirements

- Python 3.9+
- Required packages:
  - pandas
  - matplotlib
  - numpy

Install the required packages with:

```bash
pip install pandas matplotlib numpy
```

## Running the Simulation

### Basic Simulation

To run a basic simulation with the default configuration:

```bash
python3 main.py
```

This will:
- Create 3 virtual machines with random clock rates (1–6 ticks per second)
- Run the simulation for a predetermined duration (e.g., 60 seconds)
- Generate individual log files for each VM in the working directory

### Analyzing Results

After running a simulation or experiment, you can analyze the results with:

```bash
python3 plots.py
```

The analysis script will:
- Parse log files from each VM
- Generate visualizations of queue lengths and logical clock jumps over time
- Produce detailed statistical summaries and comparisons across different VMs

## Running Unit Tests

To ensure the functionality of key components such as logical clock updates, message handling, and VM connectivity, a suite of unit tests is provided in `test_suite.py`. To run these tests, simply execute:

```bash
python3 test_suite.py
```

This command will run all defined tests and report any failures or errors, helping to verify that each module of the simulation works as intended.

## Configurable Parameters in main.py

- `num_machines`: Number of virtual machines to simulate.
- `max_clock_rate`: Maximum clock rate for the virtual machines (default is 6 ticks per second).
- `internal_event_range`: Range for determining the probability of processing an internal event versus sending messages.

Additionally, we can play around with the **internal event probability** in vm.py:
  - The probability of processing an internal event versus sending a message is determined by the random selection `random.randint(1, 10)` in the code.
  - This results in approximately a 70% chance of an internal event (for random values 4–10) and a 30% chance of sending a message (for values 1–3).

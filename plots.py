import pandas as pd
import matplotlib.pyplot as plt
import re
from datetime import datetime

def parse_log_file(filename):
    # parse log files for relevant information
    data = []
    pattern = re.compile(
        r'^(?P<log_ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<event>[^,]+), System time: (?P<sys_time>[\d\- :.]+), (?P<details>.*)$'
    )
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if m:
                log_ts_str = m.group("log_ts")
                log_ts = datetime.strptime(log_ts_str, "%Y-%m-%d %H:%M:%S,%f")
                event = m.group("event").strip()
                sys_time_str = m.group("sys_time").strip()
                sys_time = datetime.strptime(sys_time_str, "%Y-%m-%d %H:%M:%S.%f")
                details = m.group("details")
                # Extract logical clock value.
                lc = None
                lc_match = re.search(r'Logical clock:\s*(\d+)', details)
                if lc_match:
                    lc = int(lc_match.group(1))
                # Extract queue length if present.
                q_len = None
                q_match = re.search(r'Queue length:\s*(\d+)', details)
                if q_match:
                    q_len = int(q_match.group(1))
                data.append({
                    "log_ts": log_ts,
                    "system_time": sys_time,
                    "event": event,
                    "logical_clock": lc,
                    "queue_length": q_len
                })
    df = pd.DataFrame(data)
    df.sort_values(by="system_time", inplace=True)
    return df

def parse_all_logs(filenames):

    dfs = []
    for fname in filenames:
        df = parse_log_file(fname)
        # Extract VM id from the filename.
        parts = fname.split("_")
        if len(parts) > 1:
            vm_id = parts[1].split(".")[0]
        else:
            vm_id = "unknown"
        df["vm_id"] = vm_id
        dfs.append(df)
    combined_df = pd.concat(dfs, ignore_index=True)
    combined_df.sort_values(by="system_time", inplace=True)
    return combined_df

def plot_queue_sizes(df):
    # plot queue length 
    plt.figure(figsize=(12, 6))
    for vm_id, group in df.groupby("vm_id"):
        df_receive = group[group["event"].str.upper() == "RECEIVE"]
        plt.plot(df_receive["system_time"], df_receive["queue_length"], marker='o', linestyle='-', label=f"VM {vm_id}")
    plt.xlabel("System Time")
    plt.ylabel("Queue Length")
    plt.title("Queue Length Over Time (All VMs)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()

def compute_jump_stats(df):
    # comute jump stats
    stats = {}
    for vm_id, group in df.groupby("vm_id"):
        group = group.dropna(subset=["logical_clock"]).sort_values(by="system_time")
        group["jump"] = group["logical_clock"].diff()
        stats[vm_id] = group["jump"].describe()
    return stats

def compute_drift(df):
    
    drift_results = {}
    for vm_id, group in df.groupby("vm_id"):
        group = group.dropna(subset=["logical_clock"]).sort_values(by="system_time")
        if not group.empty:
            start_time = group["system_time"].iloc[0]
            end_time = group["system_time"].iloc[-1]
            elapsed_seconds = (end_time - start_time).total_seconds()
            final_lc = group["logical_clock"].iloc[-1]
            drift = final_lc - elapsed_seconds
            drift_results[vm_id] = {
                "final_logical_clock": final_lc,
                "elapsed_seconds": elapsed_seconds,
                "drift": drift
            }
    return drift_results

def print_jump_stats_table(jump_stats):
    
    summary_list = []
    for vm_id, stats in jump_stats.items():
        temp = stats.to_dict()
        temp["vm_id"] = vm_id
        summary_list.append(temp)
    summary_df = pd.DataFrame(summary_list)
    return summary_df

if __name__ == '__main__':
    filenames = ["vm_1.log", "vm_2.log", "vm_3.log"]
    df_all = parse_all_logs(filenames)
    
    plot_queue_sizes(df_all)
    
    jump_stats = compute_jump_stats(df_all)
    print("Jump Statistics by VM:")
    for vm_id, stats in jump_stats.items():
        print(f"VM {vm_id}:")
        print(stats)
        print()
        
    drift_results = compute_drift(df_all)
    print("Drift Results by VM:")
    for vm_id, result in drift_results.items():
        print(f"VM {vm_id}: Final Logical Clock: {result['final_logical_clock']}, " \
              f"Elapsed Seconds: {result['elapsed_seconds']:.2f}, " \
              f"Drift (final LC - elapsed seconds): {result['drift']:.2f}")
    
    jump_summary_df = print_jump_stats_table(jump_stats)
    print("\nJump Summary Table:")
    print(jump_summary_df)

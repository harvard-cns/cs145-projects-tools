#! /usr/bin/python3

# Usage ./apps/send_traffic.py --trace {trace_file} [--logdir {log_dir}]
# 	Send traffic between hosts inside the Mininet based on the generated trace file {trace_file}
# 	The iperf and memcached performance results and their error logs will be recorded in the directory {log_dir}  

# import collections
# from collections import defaultdict
import os
import re
import shutil
import time
import sys
import subprocess
import math
import argparse
from p4utils.utils.helper import load_topo
from subprocess import Popen
from termcolor import colored

# The list of available hostnames used throughout all projects
HOSTS=[]
MN_PATH='~/mininet'
MN_UTIL=os.path.join(MN_PATH, 'util', 'm')
LOG_DIR='logs'

# Command templates used to run memcached server/client and iperf server/client
CmdMemcachedClient = {
    'start': 'stdbuf -o0 -e0 python apps/memcached_client.py {start_time} {host_name} {traffic_file} > {log_dir}/{host_name}_mc.log 2> {log_dir}/{host_name}_mc_error.log',
    'kill': 'sudo killall "python apps/memcached_client.py" 2>/dev/null'
}
CmdMemcachedServer = {
    'start': 'memcached -u p4 -m 100 >/dev/null 2>&1',
    'kill': 'sudo killall memcached 2>/dev/null'
}
CmdIperfClient = {
    'start': 'stdbuf -o0 -e0 ./apps/traffic_generator/traffic_sender --topofile {topo_file} --host {host_name} --protocol {proto} --tracefile {traffic_file} --start_time {start_time} --logdir {log_dir} --verbose --port {port} > {log_dir}/{host_name}_iperf_error.log 2>&1',
    'kill': 'sudo killall "traffic_sender" 2>/dev/null'
}
CmdIperfServer = {
    'start': 'stdbuf -o0 -e0 ./apps/traffic_generator/traffic_receiver --topofile {topo_file} --host {host_name} --protocol {proto} --start_time {start_time} --logdir {log_dir} --verbose > {log_dir}/{host_name}_iperf_server_error.log 2>&1',
    'kill': 'sudo killall "traffic_receiver" 2>/dev/null'
}

# MnExec(hostname, command):
# 	Execute the 'command' on host with name 'hostname'
def MnExec(hostName, command):
    cmd = '%s %s %s' % (MN_UTIL, hostName, command)
    p = Popen(cmd, shell=True)
    return p

# wait_util(t):
#	Let the thread to sleep until time 't'
def wait_util(t):
    now = time.time()
    if now >= t:
        return
    time.sleep(t - now)

# read_mc_latencies():
#	Read the latency results generated by memcached_client.py,
#	which are located in {LOG_DIR}/{hostname}_mc.log
def read_mc_latencies():
    res = []
    for host in HOSTS:
        log_fn = "%s/%s_mc.log" % (LOG_DIR, host)
        if os.path.exists(log_fn):
            with open(log_fn, "r") as f:
                lines = f.readlines()
                res.extend(lines)
    res = list(map(float, res))
    return res

# read_iperf_throughputs():
# 	Read the throughput results generated by iperf_client.py
# 	which are located in {LOG_DIR}/{hostname}_iperf.log
def read_iperf_throughputs():
    res = []
    for host in HOSTS:
        log_fn = "%s/%s_iperf.log" % (LOG_DIR, host)
        with open(log_fn, "r") as f:
            lines = f.readlines()
            res.extend(lines)
    res = list(map(float, res))
    return res

def read_iperf_throughputs_from_server():
    res = []
    for host in HOSTS:
        log_fn = "%s/%s_iperf_server.log" % (LOG_DIR, host)
        with open(log_fn, "r") as f:
            lines = f.readlines()
            res.extend(lines)
    res = list(map(float, res))
    return res
        
def make_traffic_generator():
    p = Popen("cd apps/traffic_generator; make; cd ../..", shell=True)
    p.communicate()
    if p.returncode != 0:
        print("Make traffic generator error!")
        sys.exit(1)

# Experiment class:
#	Used to start memcached and iperf servers/clients on different hosts
class Experiment:
    def __init__(self, traffic_file, hosts, duration, protocol, port_num=5001):
        self.traffic_file = traffic_file
        self.hosts = hosts
        self.duration = duration
        self.protocol = protocol
        self.port_num = port_num
        self.mode = 0
        self.mc_server_proc = {}
        self.mc_client_proc = {}
        self.iperf_server_proc = {}
        self.iperf_client_proc = {}
        self.mc_hosts = []
        with open(traffic_file, "r") as file:
            lines = file.readlines()
            if lines[0].strip() == '':
                self.mode = 1
            else:
                tokens = lines[0].strip().split()
                assert(len(tokens) % 2 == 0)
                idx = 0
                while idx < len(tokens):
                    self.mc_hosts.append(tokens[idx])
                    idx += 2
    def start(self):
        now = time.time()
        print("start iperf and memcached servers")
        self.start_time = int(now) + 10
        for host in self.hosts:
            if self.mode == 0 and host in self.mc_hosts:
                print("Run memcached server on host {0}".format(host))
                self.run_mc_server(host)
            print("Run iperf server on host {0}".format(host))
            self.run_iperf_server(host)
        print("Wait 5 sec for iperf and memcached servers to start")
        time.sleep(5)
        print("Start iperf and memcached clients")
        for host in self.hosts:
            if self.mode == 0:
                print("Run memcached client on host {0}".format(host))
                self.run_mc_client(host)
            print("Run iperf client on host {0}".format(host))
            self.run_iperf_client(host)

        print("Wait for experiment to finish")
        wait_util(self.start_time + self.duration)
        print("Stop everything")
        for host in self.hosts:
            if self.mode == 0 and host in self.mc_hosts:
                self.stop_mc_server(host)
                self.stop_mc_client(host)
            self.stop_iperf_server(host)
            self.stop_iperf_client(host)

    def run_mc_server(self, host):
        p = MnExec(host, CmdMemcachedServer["start"])
        self.mc_server_proc[host] = p
    def stop_mc_server(self, host):
        self.mc_server_proc[host].kill()
    def run_mc_client(self, host):
        p = MnExec(host, CmdMemcachedClient["start"].format(start_time = self.start_time, host_name = host, traffic_file = self.traffic_file, log_dir = LOG_DIR))
        self.mc_client_proc[host] = p
    def stop_mc_client(self, host):
        self.mc_client_proc[host].wait()
    def run_iperf_server(self, host):
        p = MnExec(host, CmdIperfServer["start"].format(start_time = self.start_time, log_dir = LOG_DIR, host_name = host, proto = self.protocol, topo_file=args.topo))
        self.iperf_server_proc[host] = p
    def stop_iperf_server(self, host):
        MnExec(host, CmdIperfServer["kill"])
    def run_iperf_client(self, host):
        p = MnExec(host, CmdIperfClient["start"].format(start_time = self.start_time, host_name = host, traffic_file = self.traffic_file, log_dir = LOG_DIR, proto = self.protocol, topo_file=args.topo, port=self.port_num))
        self.iperf_client_proc[host] = p
    def stop_iperf_client(self, host):
        self.iperf_client_proc[host].wait()

    # calc_score(a, b):
    #	Calculate the weighted performance score for this run
    #	The final score is a weighted combination of logarithm of average iperf throughput
    #	and logarithm of average memcached latency
    def calc_score(self, a, b):
        scorea = 0
        scoreb = 0
        if self.mode == 0:
            mc_latency = read_mc_latencies()
            latency_scores = list(map(lambda x: math.log(x, 10), mc_latency))
            if len(latency_scores) > 0:
                scoreb = sum(latency_scores) / len(latency_scores)
                avg_latency = sum(mc_latency) / len(mc_latency)
                print("Average latency of Memcached Requests: {0} us".format(avg_latency))
                # print("Average log(latency) of Memcached Requests: {0}".format(scoreb))
        iperf_bps = 0
        if self.protocol == "udp":
            iperf_bps = read_iperf_throughputs_from_server()
        elif self.protocol == "tcp":
            iperf_bps = read_iperf_throughputs()
        bps_scores = list(map(lambda x: math.log(x, 10), iperf_bps))
        if len(bps_scores) > 0:
            scorea = sum(bps_scores) / len(bps_scores)
            avg_thru = sum(iperf_bps) / len(iperf_bps)
            print("Average throughput of Iperf Traffic: {0} kbps".format(avg_thru))
            # print("Average log(throughput) of Iperf Traffic: {0}".format(scorea))
        # print("The final score is: {0}".format(a * scorea - b * scoreb))

def is_not_comment(line):
    return len(line) > 0 and line[0] != '#'

def read_score_config(score_file):
    with open(score_file, "r") as file:
        a,b = map(float, file.readlines())
    return a,b

def make_log_dir():
    if os.path.exists(LOG_DIR): shutil.rmtree(LOG_DIR)
    os.makedirs(LOG_DIR)

def calc_duration(trace_fn):
    last_time = 0.0
    with open(trace_fn, "r") as trace_file:
        lines = trace_file.readlines()[1:]
        for line in lines:
            tokens = line.split()
            flow_type = int(tokens[2])
            flow_end_time = 0.0
            if flow_type == 0 or flow_type == 1:
                flow_end_time = float(tokens[1])
            else:
                flow_end_time = float(tokens[1]) + float(tokens[4])
            last_time = max(last_time, flow_end_time)
    return last_time / 1000000.0 + 10

parser = argparse.ArgumentParser(description='A traffic generator')
parser.add_argument('--trace', help='Traffic trace file', required=True)
parser.add_argument('--logdir', help='The directory storing the logs', default="logs")
parser.add_argument('--topo', help='The directory storing the topology.json', default="topology.json")
parser.add_argument('--protocol', help='TCP/UDP for sending iperf traffic', default="tcp", choices=["tcp", "udp"])
parser.add_argument('--port', help='Specific port for TCP sender', default="0")
args = parser.parse_args()
if __name__ == '__main__':
    topo = load_topo(args.topo)
    HOSTS = topo.get_hosts().keys()	
    LOG_DIR = args.logdir
    duration = calc_duration(args.trace)

    make_traffic_generator()

    assert(int(args.port) >= 0 and int(args.port) < 65536)

    print(colored("########### Traffic Sender ############", 'green'))
    print("Trace file: {0}".format(args.trace))
    print("Host list: {0}".format(HOSTS))
    print("Traffic duration: {0} seconds".format(duration))
    print("Log directory: {0}".format(args.logdir))

    # The default weight for memcached latency and iperf throughput are both 1
    a = 1
    b = 1

    make_log_dir()

    e = Experiment(args.trace, HOSTS, duration, args.protocol, int(args.port))
    e.start()
    
    time.sleep(3)
    e.calc_score(a, b)
    
    script_path = os.path.dirname(__file__)
    subprocess.Popen("{}/kill_traffic.sh".format(script_path), shell=True)

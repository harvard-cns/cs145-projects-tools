#! /bin/bash

# Usage ./apps/kill_traffic.sh
#   Kill the traffic generator background processes

sudo killall "python apps/memcached_client.py" 2>/dev/null
sudo killall memcached 2>/dev/null
sudo killall "traffic_sender" 2>/dev/null
sudo killall "traffic_receiver" 2>/dev/null
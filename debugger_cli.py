#!/usr/bin/env python3

from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI
import code
import readline
import rlcompleter

class RoutingController(object):

    def __init__(self):
        self.topo = load_topo("topology.json")
        self.controllers = {}
        self.init()

    def init(self):
        self.connect_to_switches()

    def connect_to_switches(self):
        for p4switch in self.topo.get_p4switches():
            thrift_port = self.topo.get_thrift_port(p4switch)
            self.controllers[p4switch] = SimpleSwitchThriftAPI(thrift_port)

if __name__ == "__main__":
    topo_controller = RoutingController()
    topo = topo_controller.topo
    # print("\n\nRoutingController initialized: use the object variable 'controller' for debugging...\n\n") # This will be printed when the RoutingController is initialized
    
    # form variables with each switch's name (the key) and the corresponding controller (the value)
    for key, value in topo_controller.controllers.items():
        globals()[key] = value
    
    ############# Configure and start the debugging session #############
    readline.parse_and_bind('tab: complete') # Enable tab completion
    exit_msg = "Debugging session ended."
    start_msg = "\n\n#############################################################\n"
    start_msg += "Welcome to the RoutingController debugging session!\n"
    start_msg += "#############################################################\n"
    start_msg += "PRECONFIGURED VARIABLES:\n"
    start_msg += "'topo_controller': RoutingController() object for the entire topology\n"
    start_msg += "'topo': the topology object\n\n"
    start_msg += "Controller handles to the corresponding switches:\n"
    start_msg += " ".join([f"{key}" for key, value in topo_controller.controllers.items()])
    start_msg += "\n\n"
    start_msg += "TIP: use 'dir()' to see all available variables and functions.\n"
    start_msg += "TIP: use tab for auto-completion and to see available methods and attributes.\n"
    start_msg += "Type 'exit' or 'Ctrl+d' to end the session.\n"
    start_msg += "\n\n"
    # Start interactive debugging session
    code.interact(local=locals(), banner=start_msg, exitmsg=exit_msg) 
    
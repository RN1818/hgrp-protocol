"""
packet_transfer_simulator.py
Simulates packet transfer in HGRP protocol and displays routing tables.
"""

import json
import sys
import os
from hgrp_topology import generate_topology
from hgrp_protocol import HGRPNetwork
from hgrp_visualiser import print_hop_trace
from collections import defaultdict
import random


class PacketTransferSimulator:
    """Simulate packet transfer with detailed routing table analysis."""
    
    def __init__(self, config_file='config_hgrp.json', protocol_name='HGRP', max_num_links=float('inf')):
        """Initialize simulator with a packet-routing network."""
        self.config_file = config_file
        self.protocol_name = protocol_name
        self.config = self.load_config()
        self.calculations = {}
        self.num_routers = None
        self.results = None
        self.num_routes_through_root = 0
        
        if not self.config:
            raise Exception(f"Failed to load config from {config_file}")
        
        # Generate topology
        if max_num_links != float('inf'):
            print(f"Max number of links for OSPF simulation: {max_num_links}")
        self.topo = generate_topology(self.config, max_num_links=max_num_links)
        print("Number of links in topology:", len(self.topo.links))
        
        # Initialize HGRP network
        self.network = HGRPNetwork(self.topo)
    
    def load_config(self):
        """Load network configuration from JSON."""
        cfg_path = self.config_file
        if not os.path.exists(cfg_path):
            # Try resolving relative to this script directory
            alt = os.path.join(os.path.dirname(__file__), self.config_file)
            if os.path.exists(alt):
                cfg_path = alt
            else:
                print(f"Error: {self.config_file} not found.")
                return None

        with open(cfg_path, 'r') as f:
            config_data = json.load(f)

        topo_cfg = config_data['network_topology']
        config = {
            'depth':                 topo_cfg.get('depth'),
            'branch_factors':        topo_cfg.get('branch_factors'),
            'count_routers':         topo_cfg.get('count_routers'),
            'count_border_routers':  topo_cfg.get('count_border_routers'),
            'count_parent_connections': topo_cfg.get('count_parent_connections'),
            'cost_min':              topo_cfg.get('cost_min'),
            'cost_max':              topo_cfg.get('cost_max'),
            'seed':                  topo_cfg.get('seed'),
        }
        return config
    
    def get_routing_table_entry(self, router_id):
        """Get formatted routing table for a router."""
        router = self.network.get_router(router_id)
        if not router:
            return None
        
        entries = []
        for route in router.routing_table:
            entries.append({
                'destination': str(route.prefix),
                'next_hop': route.next_hop,
                'cost': route.metric,
                'type': route.route_type
            })
        return entries
    

    def print_all_routing_tables(self):
        """Print routing tables for all routers."""
        print("\n" + "="*80)
        print(f"{self.protocol_name.upper()} ROUTING TABLES")
        print("="*80)
        
        all_routers = sorted(self.network.all_router_ids())
        self.num_routers = len(all_routers)
        
        for router_id in all_routers:
            router = self.network.get_router(router_id)
            rnode = router.rnode
            
            print(f"\n+-- Router {router_id} (Region: {rnode.region_path}, Depth: {rnode.depth})")
            print(f"|   Network Prefix: {rnode.get_network_prefix()}")
            print(f"|   Border Router: {rnode.is_border_router}")
            print(f"|   Routing Table ({len(router.routing_table)} entries):")
            
            if not router.routing_table:
                print("|   [Empty - No routes learned yet]")
            else:
                # Sort by destination prefix
                routes = sorted(router.routing_table, key=lambda r: str(r.prefix))
                
                for i, route in enumerate(routes):
                    is_last = i == len(routes) - 1
                    prefix = "`--" if is_last else "|--"
                    
                    print(f"|   {prefix} Dest: {route.prefix:20s} | "
                          f"NH: {str(route.next_hop):8s} | "
                          f"Cost: {route.metric:3d} | "
                          f"Type: {route.route_type:6s}")
            print("|")
    

    def print_routing_table_summary(self):
        """Print summary of routing tables across network."""
        print("\n" + "="*80)
        print("ROUTING TABLE SUMMARY")
        print("="*80)
        
        all_routers = sorted(self.network.all_router_ids())
        
        total_routes = 0
        routes_by_type = defaultdict(int)
        
        for router_id in all_routers:
            router = self.network.get_router(router_id)
            total_routes += len(router.routing_table)
            
            for route in router.routing_table:
                routes_by_type[route.route_type] += 1
        
        print(f"\nTotal route entries across all routers: {total_routes}")
        print(f"Number of routers: {len(all_routers)}")
        print(f"Average routes per router: {total_routes / len(all_routers):.2f}")
        
        print("\nRoutes by type:")
        for route_type, count in sorted(routes_by_type.items()):
            print(f"  {route_type:15s}: {count:3d}")
    

    def simulate_packet_flow(self, src_router_id, dst_prefix, verbose=True):
        """
        Simulate packet transfer from source to destination.
        
        Args:
            src_router_id: Source router ID
            dst_prefix: Destination prefix
            verbose: Print detailed hop information
        
        Returns:
            List of hops showing the packet path
        """
        if verbose:
            print(f"\nTracing packet from Router {src_router_id} to {dst_prefix}")
        
        hops = self.network.trace_packet(src_router_id, dst_prefix)
        
        if verbose:
            print("\nPacket Path:")
            print("-" * 60)
            for i, hop in enumerate(hops, 1):
                print(f"  Hop {i}: Router {hop.router_id}")
                print(f"    Action: {hop.action}")
                if hop.next_router:
                    print(f"    Next Router: {hop.next_router}")
            print("-" * 60)
        
        return hops
    
    def simulate_multiple_flows(self):
        """Simulate multiple packet flows and report delivery statistics."""
        print("\n" + "="*80)
        print(f"{self.protocol_name.upper()} PACKET FLOW SIMULATION")
        print("="*80)
        
        all_routers = sorted(self.network.all_router_ids())
        self.num_routers = len(all_routers)
        root_routers = [r.router_id for r in self.topo.regions['root'].routers]
        router_to_choose = [rid for rid in all_routers if rid not in root_routers]
        self.calculations = {rid:0 for rid in all_routers}
        
        # max_flows = 1000000
        # counter = 0
        # # Generate test flows: from each router to each other router's prefix
        # test_flows = []
        # for src_rid in router_to_choose:
        #     for dst_rid in router_to_choose:
        #         if src_rid != dst_rid:
        #             counter += 1
        #             if counter > max_flows:
        #                 break
        #             src_router = self.network.get_router(src_rid)
        #             dst_router = self.network.get_router(dst_rid)
        #             dst_prefix = str(dst_router.rnode.get_network_prefix())
        #             test_flows.append((src_rid, dst_rid, dst_prefix))

        # Generate a smaller set of test flows for demonstration
        test_flows = []
        total_flows = 20000
        for _ in range(total_flows):
            src_rid = random.choice(router_to_choose)
            dst_rid = random.choice([rid for rid in router_to_choose if rid != src_rid])
            if src_rid != dst_rid:
                src_router = self.network.get_router(src_rid)
                dst_router = self.network.get_router(dst_rid)
                dst_prefix = str(dst_router.rnode.get_network_prefix())
                test_flows.append((src_rid, dst_rid, dst_prefix))
        
        # Run flows and collect statistics
        results = {
            'delivered': 0,
            'dropped': 0,
            'no_route': 0,
            'loop_detected': 0,
            'total': len(test_flows)
        }
        
        print(f"\nSimulating {len(test_flows)} packet flows...")
        counter = 0
        for src_rid, dst_rid, dst_prefix in test_flows:
            hops = self.simulate_packet_flow(src_rid, dst_prefix, verbose=False)
            counter += 1
            if counter % 1000 == 0:
                print(f"Checking test flow: {counter}")
            if hops:
                last_hop = hops[-1]
                if last_hop.action == 'DELIVERED':
                    results['delivered'] += 1
                elif last_hop.action == 'DROPPED':
                    results['dropped'] += 1
                elif last_hop.action == 'NO_ROUTE':
                    results['no_route'] += 1
                elif last_hop.action == 'LOOP_DETECTED':
                    results['loop_detected'] += 1
                for hop in hops:
                    self.calculations[hop.router_id] += 1
                for hop in hops:
                    if hop.router_id in root_routers:
                        self.num_routes_through_root += 1
                        break
        
        # Print statistics
        print("\n" + "="*80)
        print(f"{self.protocol_name.upper()} PACKET FLOW STATISTICS")
        print("="*80)
        print(f"Total flows simulated: {results['total']}")
        print(f"Successfully delivered: {results['delivered']} ({100*results['delivered']/results['total']:.1f}%)")
        print(f"Dropped (destination unreachable): {results['dropped']} ({100*results['dropped']/results['total']:.1f}%)")
        print(f"No route found: {results['no_route']} ({100*results['no_route']/results['total']:.1f}%)")
        print(f"Loops detected: {results['loop_detected']} ({100*results['loop_detected']/results['total']:.1f}%)")
        
        self.results = results
    
    def print_network_topology(self):
        """Print network topology information."""
        print("\n" + "="*80)
        print("NETWORK TOPOLOGY")
        print("="*80)
        
        print(f"\nConfiguration:")
        print(f"  Depth: {self.config['depth']}")
        print(f"  Branch factors: {self.config['branch_factors']}")
        print(f"  Routers per region: {self.config['count_routers']}")
        print(f"  Border routers per region: {self.config['count_border_routers']}")
        print(f"  Parent connections: {self.config['count_parent_connections']}")
        print(f"  Link cost range: {self.config['cost_min']}-{self.config['cost_max']}")
        
        # Count total routers and links
        all_routers = self.network.all_router_ids()
        all_links = self.topo.links
        
        print(f"\nNetwork Statistics:")
        print(f"  Total routers: {len(all_routers)}")
        print(f"  Total links: {len(all_links)}")
        print(f"  Total regions: {len(self.topo.regions)}")

    
    def analyze_traffic(self):
        """Analyze traffic patterns across the network."""
        
        # Print mean number of calculations per router
        total_calculations = sum(self.calculations.values())
        mean_calculations = total_calculations / self.num_routers if self.num_routers else 0
        mean_calculation_per_flow = total_calculations / self.results['total'] if self.results else 0
        # print(f"\nTotal routing calculations across all routers: {total_calculations}")
        # print(f"\nMean calculations per flow: {mean_calculation_per_flow:.2f}")
        # print(f"Mean calculations per router: {mean_calculations:.2f}")

        # Print congession points (routers with highest calculations)
        sorted_calculations = sorted(self.calculations.items(), key=lambda x: x[1], reverse=True)
        print("\nTop 5 routers by routing calculations:")
        for i, (router_id, calc_count) in enumerate(sorted_calculations[:5], 1):
            print(f"  {i}. Router {router_id}: {calc_count} calculations")
        
        # Print number of packets processes by root region
        root_region = self.topo.regions['root']
        root_router_ids = [r.router_id for r in root_region.routers]
        root_calculations = sum(self.calculations[rid] for rid in root_router_ids)
        print(f"\nTotal calculations in root region: {root_calculations}")
        print(f"Number of flows that passed through root region: {self.num_routes_through_root}")

def main():
    """Main entry point."""
    simulator = PacketTransferSimulator('config_hgrp.json', protocol_name='HGRP')
    
    # Print network topology
    simulator.print_network_topology()
    
    # Print all routing tables
    simulator.print_all_routing_tables()
    
    # Print routing table summary
    simulator.print_routing_table_summary()
    
    # Simulate multiple packet flows
    simulator.simulate_multiple_flows()

    simulator.analyze_traffic()


if __name__ == '__main__':
    main()

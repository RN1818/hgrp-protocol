"""
hgrp_vs_ospf_comparison.py
Comprehensive comparison of HGRP and OSPF routing protocols.
Compares convergence time, routing table size, packet delivery, and scalability.
"""

import json
import sys
import os
from packet_transfer_simulator import PacketTransferSimulator
from collections import defaultdict


class ProtocolComparison:
    """Compare HGRP and OSPF performance metrics."""

    def __init__(self, config_ospf='config_ospf.json', config_hgrp='config_hgrp.json'):
        """Initialize comparison with both simulators using dedicated configs."""
        print("\n" + "="*80)
        print("INITIALIZING HGRP vs OSPF COMPARISON")
        print("="*80)

        # Both cases use the same HGRP engine; only topology/config changes.
        print("\n[1/2] Initializing HGRP simulator...")
        self.hgrp_sim = PacketTransferSimulator(config_hgrp, protocol_name="HGRP")
        print("      HGRP initialized")

        # OSPF case is simulated with the same packet-transfer engine.
        print("[2/2] Initializing OSPF-like simulator...")
        self.ospf_sim = PacketTransferSimulator(config_ospf, protocol_name="OSPF", max_num_links=len(self.hgrp_sim.topo.links))
        print("      OSPF initialized")

        self.config = self.hgrp_sim.config
        self._validate_router_count_parity()

    def _validate_router_count_parity(self):
        """Ensure both config topologies produce the same number of routers."""
        hgrp_count = len(self.hgrp_sim.network.all_router_ids())
        ospf_count = len(self.ospf_sim.network.all_router_ids())

        print("\nRouter Count Check:")
        print(f"  HGRP routers: {hgrp_count}")
        print(f"  OSPF routers: {ospf_count}")

        if hgrp_count != ospf_count:
            print("WARNING: Router count mismatch between config_hgrp.json and config_ospf.json:")
            print(f"  HGRP={hgrp_count}, OSPF={ospf_count}.")
            print("  Adjust configs so both topologies contain the same number of routers for a more direct comparison.")
    
    # Timing-based convergence analysis removed. Use calculation-based analysis instead.


    def compute_calculation_analysis(self):
        """Estimate number of SPF/adjacency calculations performed.

        Definitions:
        - A "calculation" is counted as one adjacency traversal (edge visit) during SPF.
        - HGRP: each router runs SPF within its region only.
        - OSPF: each router runs SPF on entire topology.
        """
        print("\n" + "="*80)
        print("CALCULATION COMPLEXITY ANALYSIS")
        print("="*80)

        # Count total edges in full topology (undirected)
        total_links = len(self.hgrp_sim.topo.links)
        total_edges = total_links  # links dict stores unique (r1,r2)

        # OSPF: each router visits ~2 * total_edges adjacency traversals per SPF
        num_routers = len(self.ospf_sim.network.all_router_ids())
        ospf_total_calcs = num_routers * (2 * total_edges)
        ospf_avg_per_router = ospf_total_calcs / num_routers if num_routers else 0

        # HGRP: each router runs SPF on its region; compute edges per region
        region_edges = {}
        for region_path, region in self.hgrp_sim.topo.regions.items():
            # Count links fully inside this region
            rset = {r.router_id for r in region.routers}
            ecount = 0
            for (a, b), link in self.hgrp_sim.topo.links.items():
                if a in rset and b in rset:
                    ecount += 1
            region_edges[region_path] = ecount

        hgrp_total_calcs = 0
        for rid, router in self.hgrp_sim.network.routers.items():
            reg = router.rnode.region_path
            # estimate adjacency traversals ~= 2 * edges_in_region
            ecount = region_edges.get(reg, 0)
            hgrp_total_calcs += 2 * ecount

        hgrp_avg_per_router = hgrp_total_calcs / num_routers if num_routers else 0

        print(f"\nTopology: routers={num_routers}, links={total_links}, regions={len(region_edges)}")
        print(f"\nEstimated OSPF calculations: {ospf_total_calcs} total, {ospf_avg_per_router:.1f} avg/router")
        print(f"Estimated HGRP calculations: {hgrp_total_calcs} total, {hgrp_avg_per_router:.1f} avg/router")
        print(f"Reduction (HGRP vs OSPF): {ospf_total_calcs - hgrp_total_calcs} calculations ({100*(ospf_total_calcs-hgrp_total_calcs)/ospf_total_calcs:.1f}% fewer if positive)")
    

    def compare_routing_tables(self):
        """Compare routing table sizes and contents."""
        print("\n" + "="*80)
        print("ROUTING TABLE COMPARISON")
        print("="*80)
        
        hgrp_total_routes = 0
        ospf_total_routes = 0
        
        hgrp_routers = sorted(self.hgrp_sim.network.all_router_ids())
        ospf_routers = sorted(self.ospf_sim.network.all_router_ids())
        
        # Assuming same number of routers
        num_routers = len(hgrp_routers)
        
        for rid in hgrp_routers:
            router = self.hgrp_sim.network.get_router(rid)
            # print(f"Router {rid:30s} | HGRP routes: {len(router.routing_table):3d}")
            hgrp_total_routes += len(router.routing_table)
        
        for rid in ospf_routers:
            router = self.ospf_sim.network.routers[rid]
            # print(f"Router {rid:30s} | OSPF routes: {len(router.routing_table):3d}")
            ospf_total_routes += len(router.routing_table)
        
        print(f"\nNetwork Statistics:")
        print(f"  Total routers: {num_routers}")
        print(f"  Total links: {len(self.hgrp_sim.topo.links)}")
        print(f"  Total regions: {len(self.hgrp_sim.topo.regions)}")
        
        print(f"\nHGRP Routing Table Statistics:")
        print(f"  Total route entries: {hgrp_total_routes}")
        print(f"  Average entries per router: {hgrp_total_routes / num_routers:.2f}")
        print(f"  Routes per link ratio: {hgrp_total_routes / len(self.hgrp_sim.topo.links):.2f}")
        
        print(f"\nOSPF Routing Table Statistics:")
        print(f"  Total route entries: {ospf_total_routes}")
        print(f"  Average entries per router: {ospf_total_routes / num_routers:.2f}")
        print(f"  Routes per link ratio: {ospf_total_routes / len(self.ospf_sim.topo.links):.2f}")
        
        print(f"\nComparison:")
        diff = hgrp_total_routes - ospf_total_routes
        diff_percent = (diff / ospf_total_routes * 100) if ospf_total_routes > 0 else 0
        
        if diff < 0:
            print(f"  HGRP has {abs(diff)} fewer routes ({abs(diff_percent):.1f}% less)")
        elif diff > 0:
            print(f"  HGRP has {diff} more routes ({diff_percent:.1f}% more)")
        else:
            print(f"  Both protocols have equal routing table sizes")
    

    def analyze_route_types(self):
        """Analyze route types in HGRP vs OSPF."""
        print("\n" + "="*80)
        print("ROUTE TYPE ANALYSIS")
        print("="*80)
        
        hgrp_route_types = defaultdict(int)
        hgrp_routers = sorted(self.hgrp_sim.network.all_router_ids())
        
        print("\nHGRP Route Types:")
        for rid in hgrp_routers:
            router = self.hgrp_sim.network.get_router(rid)
            for route in router.routing_table:
                hgrp_route_types[route.route_type] += 1
        
        for route_type, count in sorted(hgrp_route_types.items()):
            print(f"  {route_type:15s}: {count:3d} routes")
        
        print("\nOSPF Route Types:")
        print("  OSPF uses flat routing (no hierarchical route types)")
        ospf_total = sum(len(self.ospf_sim.network.routers[rid].routing_table) 
                        for rid in sorted(self.ospf_sim.network.all_router_ids()))
        print(f"  All routes are destination-based: {ospf_total} routes")
    

    def compare_packet_delivery(self):
        """Compare packet delivery statistics."""
        print("\n" + "="*80)
        print("PACKET DELIVERY COMPARISON")
        print("="*80)
        
        print("\nRunning HGRP packet flow simulation...")
        hgrp_results = self.hgrp_sim.simulate_multiple_flows()
        
        print("\nRunning OSPF packet flow simulation...")
        ospf_results = self.ospf_sim.simulate_multiple_flows()

        print("\n" + "="*80)
        print("TRAFFIC ANALYSIS OF HGRP SIMULATION")
        print("="*80)
        self.hgrp_sim.analyze_traffic()

        print("\n" + "="*80)
        print("TRAFFIC ANALYSIS OF OSPF SIMULATION")
        print("="*80)
        self.ospf_sim.analyze_traffic()
        

    # Scalability analysis removed per request.
    
    def generate_comprehensive_report(self):
        """Generate comprehensive comparison report."""
        print("\n" + "="*80)
        print("COMPREHENSIVE HGRP vs OSPF COMPARISON REPORT")
        print("="*80)
        # Run selected comparisons
        self.compare_routing_tables()
        self.analyze_route_types()
        self.compare_packet_delivery()
        # New analyses: calculation complexity and congestion/load
        # self.compute_calculation_analysis()
        # self.analyze_congestion()


def main():
    """Main entry point."""
    comparison = ProtocolComparison(config_ospf='config_ospf1.json', config_hgrp='config_hgrp1.json')
    comparison.generate_comprehensive_report()


if __name__ == '__main__':
    main()

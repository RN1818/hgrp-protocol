"""
hgrp_main.py
CLI entry point for the HGRP network simulator.

Usage:
    python3 hgrp_main.py

Commands:
    draw                            Redraw the network graph
    info   <router>                 Show router identity and config
    address <router>                Show router's network prefix & subnet
    lsdb   <router>                 Show Link State Database
    spf    <router>                 Show SPF tree (connected routers, next hop, cost)
    routing <router>                Show routing table
    summary <router>                Show summary table
    forward <router> <prefix>       Trace a packet hop by hop
    step                            Run one propagation round
    routers                         List all router IDs
    regions                         List all regions and their routers
    help                            Show this help
    quit                            Exit
"""

import sys
import os
import json
from hgrp_topology import generate_topology
from hgrp_protocol import HGRPNetwork
from hgrp_visualiser import draw_network, print_hop_trace


def load_config(config_file='config.json'):
    """Load network configuration from JSON."""
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    else:
        print(f"  Error: {config_file} not found.")
        return None

    topo_cfg = config_data['network_topology']
    config = {
        'depth':                 topo_cfg.get('depth', 3),
        'branch_factors':        topo_cfg.get('branch_factors', [2, 2]),
        'count_routers':         topo_cfg.get('count_routers', [3, 2, 4]),
        'count_border_routers':  topo_cfg.get('count_border_routers', [2, 2, 2]),
        'count_parent_connections': topo_cfg.get('count_parent_connections', 2),
        'cost_min':              topo_cfg.get('cost_min', 1),
        'cost_max':              topo_cfg.get('cost_max', 10),
        'seed':                  topo_cfg.get('seed', 42),
    }

    output_cfg = config_data.get('output', {})
    config['output_dir'] = output_cfg.get('directory', './output')
    config['image_dpi'] = output_cfg.get('image_dpi', 130)

    return config


# ── Helper Functions ──────────────────────────────────────────────────────────

def find_router(topo, net, name):
    """Find a router by full path or short name.
    
    Returns tuple: (topo_router, hgrp_router) or (None, None) if not found
    """
    # Try full path first
    if name in topo.routers:
        rnode = topo.routers[name]
        hgrp_router = net.get_router(name)
        return rnode, hgrp_router
    
    # Try short name (everything after the last '/')
    for full_id, rnode in topo.routers.items():
        short_name = full_id.split('/')[-1]
        if short_name == name:
            hgrp_router = net.get_router(full_id)
            return rnode, hgrp_router
    
    return None, None


# ── CLI ───────────────────────────────────────────────────────────────────────

def run_cli(net, topo, output_dir, image_dpi):
    """Interactive CLI for network simulation."""
    print("\nNetwork ready. Type 'help' for commands.\n")
    last_path = None   # for highlighting on next draw

    while True:
        try:
            raw = input("hgrp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        # ── help ──────────────────────────────────────────────────────────
        if cmd == 'help':
            print(__doc__)

        # ── quit ──────────────────────────────────────────────────────────
        elif cmd in ('quit', 'exit', 'q'):
            print("Goodbye.")
            break

        # ── draw ──────────────────────────────────────────────────────────
        elif cmd == 'draw':
            draw_network(topo, highlight_path=last_path, title='HGRP Network', 
                        output_dir=output_dir, image_dpi=image_dpi)
            last_path = None

        # ── routers ───────────────────────────────────────────────────────
        elif cmd == 'routers':
            rids = net.all_router_ids()
            cols = 5
            print(f"\n  {len(rids)} routers:")
            for i in range(0, len(rids), cols):
                row = rids[i:i+cols]
                print('  ' + '   '.join(f'{r:<18}' for r in row))
            print()

        # ── regions ───────────────────────────────────────────────────────
        elif cmd == 'regions':
            print()
            for path, region in sorted(topo.regions.items()):
                print(f"  {path:<30} depth={region.depth}  "
                      f"routers={len(region.routers)}  "
                      f"borders={len(region.border_routers)}")
            print()

        # ── info <router> ─────────────────────────────────────────────────
        elif cmd == 'info':
            if len(parts) < 2:
                print("  Usage: info <router_id>"); 
                continue
            rnode, _ = find_router(topo, net, parts[1])
            if not rnode:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── Router: {rid} ──")
            print(f"  Region:              {rnode.region_path}")
            print(f"  Depth:               {rnode.depth}")
            print(f"  Border router:       {'Yes' if rnode.is_border_router else 'No'}")
            print(f"  Parent router:       {'Yes' if rnode.is_parent_router else 'No'}")
            if rnode.is_border_router:
                print(f"  Parent routers:      {len(rnode.parent_routers)}")
            if rnode.is_parent_router:
                print(f"  Child border routers: {[r.router_id for r in rnode.child_border_routers]}")
            print(f"  Network prefix:      {rnode.get_network_prefix()}/{rnode.get_network_subnet()}")
            print()

        # ── address <router> ──────────────────────────────────────────────
        elif cmd == 'address':
            if len(parts) < 2:
                print("  Usage: address <router_id>"); 
                continue
            rnode, _ = find_router(topo, net, parts[1])
            if not rnode:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── Network Address: {rid} ──")
            print(f"  Network prefix:      {rnode.get_network_prefix()}")
            print(f"  Subnet mask:         /{rnode.get_network_subnet()}")
            print()

        # ── lsdb <router> ─────────────────────────────────────────────────
        elif cmd == 'lsdb':
            if len(parts) < 2:
                print("  Usage: lsdb <router_id>"); 
                continue
            rnode, hgrp_router = find_router(topo, net, parts[1])
            if not hgrp_router:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── LSDB: {rid} (region: {hgrp_router.rnode.region_path}) ──")
            if not hgrp_router.lsdb:
                print("  (empty)")
            else:
                for router_id, entry in sorted(hgrp_router.lsdb.items()):
                    print(f"  {router_id}:")
                    for neighbour_id, cost in entry.links:
                        print(f"      → {neighbour_id} (cost={cost})")
            print()

        # ── spf <router> ──────────────────────────────────────────────────
        elif cmd == 'spf':
            if len(parts) < 2:
                print("  Usage: spf <router_id>"); 
                continue
            rnode, hgrp_router = find_router(topo, net, parts[1])
            if not hgrp_router:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── SPF Tree: {rid} (region: {hgrp_router.rnode.region_path}) ──")
            if not hgrp_router.spf_result:
                print("  (empty)")
            else:
                print(f"  {'Router':<20} {'Next Hop':<20} {'Cost':<10}")
                print(f"  {'-'*20} {'-'*20} {'-'*10}")
                for router_id, spf_entry in sorted(hgrp_router.spf_result.items()):
                    if spf_entry.metric == float('inf'):
                        cost_str = "∞"
                    else:
                        cost_str = str(int(spf_entry.metric))
                    next_hop = spf_entry.next_hop if spf_entry.next_hop else "Self"
                    print(f"  {router_id:<20} {next_hop:<20} {cost_str:<10}")
            print()

        # ── routing <router> ──────────────────────────────────────────────
        elif cmd == 'routing':
            if len(parts) < 2:
                print("  Usage: routing <router_id>"); 
                continue
            rnode, hgrp_router = find_router(topo, net, parts[1])
            if not hgrp_router:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── Routing Table: {rid} ──")
            if not hgrp_router.routing_table:
                print("  (empty)")
            else:
                for route in hgrp_router.routing_table:
                    next_hop = route.next_hop if route.next_hop else "N/A"
                    print(f"  {route.prefix:<15} → {next_hop:<18} metric={route.metric} ({route.route_type})")
            print()

        # ── summary <router> ──────────────────────────────────────────────
        elif cmd == 'summary':
            if len(parts) < 2:
                print("  Usage: summary <router_id>"); 
                continue
            rnode, hgrp_router = find_router(topo, net, parts[1])
            if not hgrp_router:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            rid = rnode.router_id
            print(f"\n  ── Summary Table: {rid} ──")
            if not hgrp_router.summary_table:
                print("  (empty)")
            else:
                for (prefix_str, origin_region), entry in sorted(hgrp_router.summary_table.items()):
                    print(f"  {prefix_str} ({net.find_router_by_prefix(prefix_str)}) from {origin_region:<15}:", end=' ' )
                    if entry.best_path_index is not None:
                        best_path = entry.paths[entry.best_path_index]
                        print(f"Best path via {best_path.border_router_id} (metric={best_path.metric})")
                    else:
                        print(f"No available path")
            print()

        # ── forward <router> <prefix> ─────────────────────────────────────
        elif cmd == 'forward':
            if len(parts) < 3:
                print("  Usage: forward <router_id> <prefix>"); 
                print("  Example: forward root0 10.0.1.0/24"); 
                continue
            
            rnode, hgrp_router = find_router(topo, net, parts[1])
            if not hgrp_router:
                print(f"  Unknown router: {parts[1]}"); 
                continue
            
            rid = rnode.router_id
            prefix = parts[2]

            # If prefix is a router ID, get its network
            if "/" not in prefix:
                prefix_rnode, _ = find_router(topo, net, prefix)
                if prefix_rnode:
                    prefix = prefix_rnode.get_network_prefix()
            
            hops = net.trace_packet(rid, prefix)
            print_hop_trace(hops, rid, prefix)

            # Extract path for highlighting
            path = [h.router_id for h in hops if h.router_id]
            if path:
                last_path = path
                draw_network(topo, highlight_path=last_path, title='HGRP Network — Forwarding Path', 
                            output_dir=output_dir, image_dpi=image_dpi)
                
        # get link given two router short ids, return cost or none
        elif cmd == 'link':
            if len(parts) < 3:
                print("  Usage: link <router1> <router2>"); 
                continue
            r1, r2 = parts[1], parts[2]
            # Resolve short names to full IDs
            rnode1, _ = find_router(topo, net, r1)
            rnode2, _ = find_router(topo, net, r2)
            if not rnode1 or not rnode2:
                print(f"  Unknown router(s): {r1 if not rnode1 else ''} {r2 if not rnode2 else ''}"); 
                continue
            a, b = rnode1.router_id, rnode2.router_id
            cost = net.get_link_cost(a, b)
            if cost is not None:
                print(f"  Link {a} ↔ {b} has cost {cost}.")
            else:
                print(f"  No link found between {a} and {b}.")

        # ── fail <r1> <r2> ────────────────────────────────────────────────
        elif cmd == 'fail':
            if len(parts) < 3:
                print("  Usage: fail <router1> <router2>"); 
                continue
            r1, r2 = parts[1], parts[2]
            # Resolve short names to full IDs
            rnode1, _ = find_router(topo, net, r1)
            rnode2, _ = find_router(topo, net, r2)
            if not rnode1 or not rnode2:
                print(f"  Unknown router(s): {r1 if not rnode1 else ''} {r2 if not rnode2 else ''}"); 
                continue
            a, b = rnode1.router_id, rnode2.router_id
            if net.fail_link(a, b):
                print(f"  Link {a} ↔ {b} failed.")
                print("  Type 'step' to propagate changes.")
            else:
                print(f"  No link found between {a} and {b}.")

        # ── recover <r1> <r2> ─────────────────────────────────────────────
        elif cmd == 'recover':
            if len(parts) < 3:
                print("  Usage: recover <router1> <router2>"); 
                continue
            r1, r2 = parts[1], parts[2]
            # Resolve short names to full IDs
            rnode1, _ = find_router(topo, net, r1)
            rnode2, _ = find_router(topo, net, r2)
            if not rnode1 or not rnode2:
                print(f"  Unknown router(s): {r1 if not rnode1 else ''} {r2 if not rnode2 else ''}"); 
                continue
            a, b = rnode1.router_id, rnode2.router_id
            if net.recover_link(a, b):
                print(f"  Link {a} ↔ {b} recovered.")
                print("  Type 'step' to propagate changes.")
            else:
                print(f"  No link found between {a} and {b}.")

        # ── step ──────────────────────────────────────────────────────────
        elif cmd == 'step':
            print("  Running propagation round...")
            events = net.propagate_one_round()
            if events:
                for e in events:
                    print(f"    {e}")
            else:
                print("    Network already converged — no changes.")
            draw_network(topo, highlight_path=last_path, title='HGRP Network', 
                        output_dir=output_dir, image_dpi=image_dpi)
            print()

        else:
            print(f"  Unknown command: '{cmd}'. Type 'help'.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    print("\n╔════════════════════════════════════════════════════════╗")
    print("║     HGRP Hierarchical Gradient Routing Protocol       ║")
    print("║              Network Simulator (v2)                    ║")
    print("╚════════════════════════════════════════════════════════╝\n")
    
    print("  Loading configuration from config.json...")
    config = load_config('config.json')
    if not config:
        sys.exit(1)

    # Create output directory
    output_dir = config['output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"  Created output directory: {output_dir}")
    
    print(f"  Output directory: {output_dir}")
    print(f"  Image DPI: {config['image_dpi']}\n")

    print("  Building topology...")
    topo = generate_topology(config)
    
    print(f"    Depth: {topo.depth}")
    print(f"    Regions: {len(topo.regions)}")
    print(f"    Routers: {len(topo.routers)}")
    print(f"    Links: {len(topo.links)}")

    print("\n  Running initial convergence...")
    net = HGRPNetwork(topo)

    print("\n  Drawing network topology...")
    draw_network(topo, title='HGRP Network — Initial State', output_dir=output_dir, image_dpi=config['image_dpi'])
    
    print("\nEntering interactive CLI...\n")
    run_cli(net, topo, output_dir, config['image_dpi'])


if __name__ == '__main__':
    main()

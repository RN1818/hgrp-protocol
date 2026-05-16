"""
hgrp_protocol.py
Complete HGRP protocol implementation: SPF, SA propagation, routing tables, packet forwarding.
"""

import heapq
from collections import defaultdict
import ipaddress

# ── Protocol Constants ────────────────────────────────────────────────────────

W_C = 1                             # Cost weight in composite metric
W_S = 1                             # Stability weight (unused in simulation - stable links always)
SUMMARY_DEAD_INTERVAL = 120         # SA timeout in simulation rounds
METRIC_CHANGE_THRESHOLD = 0.10      # 10% change triggers new SA advertisement


# ── HGRPNetwork ───────────────────────────────────────────────────────────────

class HGRPNetwork:
    """
    Manages all routers and drives protocol events.
    - Runs SPF on all regions
    - Propagates Summary Advertisements (SAs) bottom-up
    - Rebuilds routing tables
    - Traces packet forwarding
    """
    
    def __init__(self, topo):
        self.topo = topo
        self.routers = {} 
        for rid, rnode in topo.routers.items():
            self.routers[rid] = HGRPRouter(rnode, topo, self)
        self.converge_all()
    
    def converge_all(self):
        """Full convergence: SPF → SA propagation → routing table rebuild."""
        # Phase 1: SPF in every region
        for rid, router in self.routers.items():
            router.run_spf()
        
        # Phase 2: SA propagation bottom-up, level by level
        max_depth = max((r.depth for r in self.topo.routers.values()), default=0)
        for d in range(max_depth, 0, -1):
            print(f"Processing depth {d} for SA propagation")
            for rid, router in self.routers.items():
                if router.rnode.depth == d and router.rnode.is_border_router:
                    #print(f"Generating SA from router {rid} at depth {d}")
                    router.generate_and_send_sa()
        
        # Phase 3: Build routing tables
        for rid, router in self.routers.items():
            router.build_routing_table()
    
    
    def trace_packet(self, src_router_id, dst_prefix):
        """Trace a packet from source to destination."""
        hops = []
        visited = set()
        current = src_router_id
        
        while True:
            if current in visited:
                hops.append(HopResult(current, 'LOOP_DETECTED', None, None))
                break
            
            visited.add(current)
            router = self.routers[current]
            hop = router.forwarding_decision(dst_prefix)
            hops.append(hop)
            
            if hop.action in ('DELIVERED', 'DROPPED', 'NO_ROUTE'):
                break
            
            # Move to next router
            next_rid = hop.next_router
            if next_rid is None:
                break
            
            current = next_rid
        
        return hops
    
    def get_router(self, router_id):
        """Get an HGRP router by ID."""
        return self.routers.get(router_id)
    
    def all_router_ids(self):
        """Get all router IDs sorted."""
        return sorted(self.routers.keys())
    
    def find_router_by_prefix(self, prefix):
        """Find router ID that owns a given prefix (if any)."""
        for rid, router in self.routers.items():
            if router.rnode.get_network_prefix() == prefix:
                return rid
        print(f"No router found for prefix {prefix}")
        return None
    
    def get_link_cost(self, router_id_1, router_id_2):
        """Get link cost between two routers if they are directly connected."""
        link = self.topo.links.get((router_id_1, router_id_2)) or self.topo.links.get((router_id_2, router_id_1))
        return link.cost if link else None


# ── HGRPRouter ────────────────────────────────────────────────────────────────

class HGRPRouter:
    """
    Per-router protocol state: LSDB, summary table, SPF result, routing table.
    """
    
    def __init__(self, rnode, topo, network):
        self.rnode = rnode            # Router node from topology
        self.topo = topo              # Full topology
        self.network = network        # HGRPNetwork for calling other routers
        self.lsdb_dirty = True        # True if region topology changed
        
        # Protocol state
        self.lsdb = {}                # router_id → LSDBEntry
        self.spf_result = {}          # router_id → SPFEntry
        self.summary_table = {}       # (prefix_str, origin_region) → SummaryEntry
        self.routing_table = []       # List of RouteEntry, sorted by prefix
    
    # ── SPF (Shortest Path First) ─────────────────────────────────────────────
    
    def run_spf(self):
        """
        Run Dijkstra's algorithm on this router's region.
        Composite metric: cost + stability_penalty (0 in simulation)
        """
        region_path = self.rnode.region_path
        src_id = self.rnode.router_id
        
        # Build adjacency list from all region links (undirected graph)
        adj = defaultdict(list)
        region = self.topo.regions[region_path]
        for link in region.links:
            if link.alive:
                rid1 = link.router_1.router_id
                rid2 = link.router_2.router_id
                weight = W_C * link.cost  # stability_penalty = 0 in simulation
                adj[rid1].append((rid2, weight))
                adj[rid2].append((rid1, weight))
        
        # Get all routers in this region
        region_routers = self.topo.get_routers_in_region(region_path)
        
        # Dijkstra
        dist = {rid: float('inf') for rid in region_routers}
        prev = {rid: None for rid in region_routers}
        dist[src_id] = 0
        heap = [(0, src_id)]
        
        while heap:
            current_dist, u = heapq.heappop(heap)
            if current_dist > dist[u]:
                continue
            
            for v, weight in adj[u]:
                alt = dist[u] + weight
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(heap, (alt, v))
        
        self.spf_result.clear()
        for rid in region_routers:
            if rid == src_id:
                self.spf_result[rid] = SPFEntry(rid, 0, None)
            elif dist[rid] == float('inf'):
                self.spf_result[rid] = SPFEntry(rid, float('inf'), None)
            else:
                next_hop = self._trace_next_hop(prev, src_id, rid)
                self.spf_result[rid] = SPFEntry(rid, dist[rid], next_hop)
    
        self._rebuild_lsdb()
    

    def _trace_next_hop(self, prev, src, dst):
        """Trace back to find immediate next hop."""
        if prev[dst] is None:
            return None
        if prev[dst] == src:
            return dst
        return self._trace_next_hop(prev, src, prev[dst])
    

    def _rebuild_lsdb(self):
        """Rebuild LSDB from region links."""
        self.lsdb.clear()
        region_path = self.rnode.region_path
        
        # Get all same-region links
        region = self.topo.regions[region_path]
        for link in region.links:
            if link.alive:
                rid1 = link.router_1.router_id
                rid2 = link.router_2.router_id
                
                if rid1 not in self.lsdb:
                    self.lsdb[rid1] = LSDBEntry(rid1)
                if rid2 not in self.lsdb:
                    self.lsdb[rid2] = LSDBEntry(rid2)
                
                self.lsdb[rid1].links.append((rid2, link.cost))
                self.lsdb[rid2].links.append((rid1, link.cost))
    
    # ── Summary Advertisements (SAs) ──────────────────────────────────────────
    
    def _compute_subtree_prefixes(self):
        """Compute all prefixes reachable in this router's subtree."""
        result = {}
        
        # Add prefixes from own region (via SPF)
        for rid in self.rnode.region.router_ids:
            if rid in self.spf_result:
                spf_entry = self.spf_result[rid]
                if spf_entry.metric < float('inf'):
                    prefix_str = self.topo.routers[rid].get_network_prefix()
                    result[prefix_str] = spf_entry.metric
        
        # Add prefixes from child regions (via summary table)
        for (prefix_str, origin_region), summary_entry in self.summary_table.items():
            if summary_entry.best_path_index is not None:
                best_path = summary_entry.paths[summary_entry.best_path_index]
                if best_path.alive:
                    result[prefix_str] = best_path.metric
                if best_path.metric == 0:
                    print(f"Zero metric in subtree from summary: {self.rnode.router_id} to {prefix_str} via {best_path.border_router_id}")
        
        return result
    

    def generate_and_send_sa(self):
        """Generate and send SAs to parent region."""
        if (not self.rnode.is_border_router) or (self.rnode.is_root_router):
            return False
        
        subtree_prefixes = self._compute_subtree_prefixes()
        to_advertise = {}
        
        for prefix_str, metric in subtree_prefixes.items():
            to_advertise[prefix_str] = metric

        parent_region_routers = self.rnode.parent_routers[0].region.routers
        my_parent_router_ids = {r.router_id for r in self.rnode.parent_routers}

        for router in parent_region_routers:
            router_hgrp = self.network.routers[router.router_id]
            for prefix_str, metric in to_advertise.items():
                if router.router_id in my_parent_router_ids:
                    pr_metric = self._get_link_cost(router.router_id)
                    router_hgrp.receive_sa(self.rnode.router_id, prefix_str, metric + pr_metric, "ADVERTISE", self.rnode.region.path, self.rnode.router_id)
                else:
                    nearest_parent_router, npr_metric = self._find_nearest_parent_router()
                    entry = router_hgrp.spf_result.get(nearest_parent_router)
                    router_hgrp.receive_sa(entry.next_hop, prefix_str, metric + npr_metric + entry.metric, "ADVERTISE", self.rnode.region.path, self.rnode.router_id)

        return True

    def _find_nearest_parent_router_in_region(self):
        """Find nearest parent router in the same region."""
        best_metric = float('inf')
        best_router_id = None
        for router in self.rnode.region.routers:
            if router.is_parent_router and router.router_id != self.rnode.router_id:
                entry = self.spf_result[router.router_id]
                if entry.metric < best_metric:
                    best_metric = entry.metric
                    best_router_id = router.router_id
        return best_router_id

    
    def _get_link_cost(self, router_id):
        if self.topo.links.get((self.rnode.router_id, router_id)) is not None:
            return self.topo.links[(self.rnode.router_id, router_id)].cost
        elif self.topo.links.get((router_id, self.rnode.router_id)) is not None:
            return self.topo.links[(router_id, self.rnode.router_id)].cost
        return None
    
    def receive_sa(self, previous_rid, prefix_str, metric, action, origin_region_path, sender_id):
        """Process an incoming SA from a child border router."""
        origin_key = (prefix_str, origin_region_path)
        
        if action == "ADVERTISE":
            if origin_key not in self.summary_table:
                self.summary_table[origin_key] = SummaryEntry(prefix_str, origin_region_path)
            
            entry = self.summary_table[origin_key]
            path_entry = None
            for p in entry.paths:
                if p.border_router_id == previous_rid:
                    path_entry = p
                    break
            
            if path_entry is None:
                path_entry = PathRecord(previous_rid, previous_rid, metric)
                entry.paths.append(path_entry)
            else:
                path_entry.metric = metric
            
            path_entry.age = 0
            path_entry.alive = True
            self._update_best_path(entry)

    
    def _update_best_path(self, entry):
        """Update best_path_index for a summary entry."""
        best_metric = float('inf')
        best_index = None
        
        for i, path in enumerate(entry.paths):
            if path.alive and path.metric < best_metric:
                best_metric = path.metric
                best_index = i
        
        entry.best_path_index = best_index
    
    # ── Routing Table ─────────────────────────────────────────────────────────
    
    def build_routing_table(self):
        """Build routing table from LSDB and summary table."""
        self.routing_table = []
        
        # Group routes by prefix to keep only the best (lowest metric) entry per prefix
        routes_by_prefix = {}
        
        # INTRA_REGION routes from SPF
        region_path = self.rnode.region_path
        for rid in self.topo.get_routers_in_region(region_path):
            if rid in self.spf_result:
                spf_entry = self.spf_result[rid]
                if spf_entry.metric < float('inf'):
                    prefix_str = self.topo.routers[rid].get_network_prefix()
                    
                    # Skip routes to self with next_hop=None (except if it's our own prefix for delivery)
                    if spf_entry.next_hop is None and rid != self.rnode.router_id:
                        continue
                    
                    # Keep only the best route for this prefix
                    if prefix_str not in routes_by_prefix or spf_entry.metric < routes_by_prefix[prefix_str][2]:
                        routes_by_prefix[prefix_str] = (spf_entry.next_hop, 'INTRA_REGION', spf_entry.metric)
        
        # SUMMARY routes from child regions
        for (prefix_str, origin_region), entry in self.summary_table.items():
            if entry.best_path_index is not None:
                best_path = entry.paths[entry.best_path_index]
                
                # Keep summary route if it's better than any existing route or if no INTRA_REGION route exists
                if prefix_str not in routes_by_prefix or best_path.metric < routes_by_prefix[prefix_str][2]:
                    routes_by_prefix[prefix_str] = (best_path.next_hop, 'SUMMARY', best_path.metric)
        
        # ESCALATE routes to parent region
        for parent_router in self.rnode.parent_routers:
            prefix_str = parent_router.get_network_prefix()
            cost = self._get_link_cost(parent_router.router_id)
            if prefix_str not in routes_by_prefix or cost < routes_by_prefix[prefix_str][2]:
                routes_by_prefix[prefix_str] = (parent_router.router_id, 'ESCALATE', cost)

        if not self.rnode.is_border_router:
            # Add default route to nearest parent router if no specific route exists
            default_prefix = '0.0.0.0/0'
            if default_prefix not in routes_by_prefix:
                nearest_border_router, metric = self._find_nearest_border_router()              
                if nearest_border_router is not None:
                    if self._get_link_cost(nearest_border_router) is None:
                        entry = self.spf_result.get(nearest_border_router)
                        routes_by_prefix[default_prefix] = (entry.next_hop, 'ESCALATE', entry.metric)
                    else:
                        routes_by_prefix[default_prefix] = (nearest_border_router, 'ESCALATE', metric)
        
        # Convert dictionary back to list
        for prefix_str, (next_hop, route_type, metric) in routes_by_prefix.items():
            self.routing_table.append(RouteEntry(prefix_str, next_hop, metric, route_type))
        
        # Sort by prefix for longest-match lookup
        self.routing_table.sort(key=lambda r: r.prefix, reverse=True)
    
    def forwarding_decision(self, dst_prefix):
        # Forwarding is done by using the routing table. First check intra region routing entries, then summary, if not use escalate.
        # Convert prefix to network for matching
        try:
            dst_net = ipaddress.ip_network(dst_prefix, strict=False)
        except Exception:
            return HopResult(self.rnode.router_id, 'DROPPED', None, 'Invalid prefix')
        
        if dst_net.subnet_of(self.rnode.ip_address):
            return HopResult(self.rnode.router_id, 'DELIVERED', None, 'Local delivery')

        # Longest-prefix match: routing_table is pre-sorted by prefix string; iterate and pick first matching
        # Priority: INTRA_REGION -> SUMMARY -> ESCALATE (but table may contain mixed entries)
        best_match = None
        for route in self.routing_table:
            if dst_net.subnet_of(ipaddress.ip_network(route.prefix, strict=False)):
                best_match = route
                break
        
        if best_match is None:
            if self.rnode.is_root_router:
                return HopResult(self.rnode.router_id, 'DROPPED', None, 'No route and this is root')
            elif self.rnode.is_border_router:
                return HopResult(self.rnode.router_id, 'ESCALATE', self._find_nearest_parent_router()[0], 'Escalate to parent')
            else:
                nearest_border = self._find_nearest_border_router()
                next_hop = self.spf_result.get(nearest_border).next_hop
                return HopResult(self.rnode.router_id, 'ESCALATE',next_hop, 'Forward to nearest border router')

        if best_match.next_hop is None:
            return HopResult(self.rnode.router_id, 'DROPPED', None, 'No next hop for matched route')
        
        if best_match.route_type == 'ESCALATE':
            return HopResult(self.rnode.router_id, 'ESCALATE', best_match.next_hop, 'Escalate to parent')
        if best_match.route_type == 'INTRA_REGION':
            return HopResult(self.rnode.router_id, 'LOCAL', best_match.next_hop, f'Forward locally via {best_match.next_hop}')
        if best_match.route_type == 'SUMMARY':
            return HopResult(self.rnode.router_id, 'SUMMARY', best_match.next_hop, f'Forward to child region via {best_match.next_hop}')
        
        # diplay all information about the route and the decision if unhandled route type
        print(best_match.__dict__)
        return HopResult(self.rnode.router_id, 'ESCALATE',self._find_nearest_border_router()[0], 'Unhandled route type')
        
    
    def _find_nearest_border_router(self):
        """Find nearest border router via SPF to reach parent region."""
        best_metric = float('inf')
        best_border = None
        
        region_path = self.rnode.region_path
        for rid in self.topo.get_border_routers_in_region(region_path):
            if rid in self.spf_result:
                spf_entry = self.spf_result[rid]
                if spf_entry.metric < best_metric:
                    best_metric = spf_entry.metric
                    best_border = rid
        
        return best_border, best_metric

    def _find_nearest_parent_router(self):
        """Find nearest parent router via SPF to reach parent region."""
        best_metric = float('inf')
        best_parent = None
        
        for parent_router in self.rnode.parent_routers:
            if parent_router.is_parent_router:
                link_cost = self._get_link_cost(parent_router.router_id)
                if link_cost is not None and link_cost < best_metric:
                    best_metric = link_cost
                    best_parent = parent_router.router_id
        
        return best_parent, best_metric


# ── Data Structures ───────────────────────────────────────────────────────────

class LSDBEntry:
    """Link State Database entry - one entry per router in region."""
    def __init__(self, router_id):
        self.router_id = router_id
        self.links = []  # List of (neighbour_id, cost)


class SPFEntry:
    """SPF result - distance and next hop to a router."""
    def __init__(self, router_id, metric, next_hop):
        self.router_id = router_id
        self.metric = metric # metric to reach this router from self, not just link cost to next hop
        self.next_hop = next_hop  # Immediate next hop


class SummaryEntry:
    """Summary table entry - one per prefix from child regions."""
    def __init__(self, prefix_str, origin_region):
        self.prefix = prefix_str
        self.origin_region = origin_region
        self.paths = []  # List of PathRecord
        self.best_path_index = None  # Index of best path


class PathRecord:
    """One path to a prefix via a specific border router."""
    def __init__(self, border_router_id, next_hop, metric):
        self.border_router_id = border_router_id
        self.next_hop = next_hop
        self.metric = metric
        self.age = 0
        self.alive = True


class RouteEntry:
    """Routing table entry."""
    def __init__(self, prefix, next_hop, metric, route_type):
        self.prefix = prefix         # e.g., '10.0.1.0'
        self.next_hop = next_hop     # Router ID
        self.metric = metric
        self.route_type = route_type  # INTRA_REGION, SUMMARY, or DEFAULT


class HopResult:
    """Result of a forwarding decision at one router."""
    def __init__(self, router_id, action, next_router, reason):
        self.router_id = router_id
        self.action = action        # DELIVERED, DROPPED, FORWARD_LOCAL, FORWARD_SUMMARY, ESCALATE, NO_ROUTE, LOOP_DETECTED
        self.next_router = next_router
        self.reason = reason
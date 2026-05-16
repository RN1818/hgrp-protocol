"""
hgrp_topology.py
Generates a hierarchical network topology for the HGRP simulator.

The topology is a rooted tree of regions. Each region contains routers.
Border routers connect child regions to their parent regions.
"""

import random
import ipaddress
from collections import defaultdict

def generate_topology(config, max_num_links=float('inf')):
    """Generate a new topology from config."""
    random.seed(config.get('seed', 42))
    topology = TopologyData(config, ospf_max_num_links=max_num_links)
    topology.generate()
    return topology


class TopologyData:
    """
    Manages the entire network topology: regions, routers, and links.
    
    Key data structures:
    - routers: dict of router_id → Router
    - links: dict of (r1_id, r2_id) → Link
    - regions: dict of region_path → Region
    - root: the root Region
    - depth: maximum depth of region hierarchy
    """
    
    def __init__(self, config, ospf_max_num_links=float('inf')):
        self.config = config
        self.depth = config['depth']
        self.branch_factors = config['branch_factors']
        self.cost_min = config['cost_min']
        self.cost_max = config['cost_max']
        self.count_border_routers = config['count_border_routers']
        self.count_routers = config['count_routers']
        self.count_parent_connections = config.get('count_parent_connections', 1)
        self.ospf_max_num_links = ospf_max_num_links # for simulating ospf
        print(f"Max links: {self.ospf_max_num_links}")

        self.routers = {}           # router_id → Router
        self.links = {}             # (r1_id, r2_id) → Link
        self.regions = {}           # region_path → Region
        self.root = None
        self.region_counters = {}   # depth_index → next unique index for that depth

    
    def generate(self):
        """Build the complete topology."""
        # Initialize region counters for each depth level
        for i in range(self.depth):
            self.region_counters[i] = 0
        
        self.root = Region('root', 0, None, 'root')
        self.regions['root'] = self.root
        
        for i in range(self.count_routers[0]):
            router_id = f'root{i}'
            router = Router(
                router_id,
                self.root,
                self.root.path,
                ipaddress.ip_network(f'10.0.{i}.0/24', strict=False)
            )
            router.is_root_router = True
            self.root.routers.append(router)
            self.routers[router_id] = router
        
        # Add intra-region links for root
        self._add_intra_region_links(self.root)
        
        self._generate_children(self.root, 0)
        
        # Add inter-region links after all regions and routers are created
        self._add_inter_region_links()
    
    def _generate_children(self, region, depth_index):
        """Recursively generate child regions."""
        if depth_index >= self.depth:
            return

        branch_factor = self.branch_factors[depth_index]
        for _ in range(branch_factor):
            # Get next unique index for this depth level
            index = self.region_counters[depth_index]
            self.region_counters[depth_index] += 1
            
            child_name = f'{chr(97 + depth_index)}{index}'
            child_path = f'{region.path}/{child_name}'
            child = Region(child_name, region.depth + 1, region, child_path)
            region.children.append(child)
            self.regions[child_path] = child
            
            # Add routers to child region (if router count is defined for this depth)
            if depth_index + 1 < len(self.count_routers):
                router_count = self.count_routers[depth_index + 1]
                for i in range(router_count):
                    router_id = f'{child_path}r{i}'
                    router = Router(
                        router_id,
                        child,
                        child_path,
                        ipaddress.ip_network(f'{depth_index + 11}.{index}.{i}.0/24', strict=False)
                    )
                    child.routers.append(router)
                    self.routers[router_id] = router
                
                # Add random intra-region links
                self._add_intra_region_links(child, branch_factor - self.region_counters[depth_index] + 1)
            
            self._generate_children(child, depth_index + 1)

    def _add_intra_region_links(self, region, link_factor=None):
        """Add random links between routers in the same region."""
        if len(region.routers) < 2:
            return
        # print(f"Link factor: {link_factor}")
        
        # Ensure connectivity: create a ring
        for i in range(len(region.routers)):
            r1 = region.routers[i]
            r2 = region.routers[(i + 1) % len(region.routers)]
            cost = random.randint(self.cost_min, self.cost_max)
            link = Link(r1, r2, cost, cross_region=False)
            self.links[(r1.router_id, r2.router_id)] = link
            region.links.append(link)
            r1.siblings.append(r2)
            r2.siblings.append(r1)
        
        if link_factor is None:
            # Add random additional links
            for i in range(len(region.routers)):
                for j in range(i + 2, len(region.routers)):
                    if random.random() < 0.5:  # 50% chance for each potential link
                        r1 = region.routers[i]
                        r2 = region.routers[j]
                        cost = random.randint(self.cost_min, self.cost_max)
                        link = Link(r1, r2, cost, cross_region=False)
                        self.links[(r1.router_id, r2.router_id)] = link
                        region.links.append(link)
                        r1.siblings.append(r2)
                        r2.siblings.append(r1)
        else:
            # Add random additional links
            if self.ospf_max_num_links < float('inf'):
                # print(f"So far num_length: {len(self.links)}")
                link_probability = self.ospf_max_num_links / (len(region.routers) * (len(region.routers) + 1) / 2) / self.branch_factors[0] * 0.8
                # print(f"Link probability: {link_probability}")
            else:
                link_probability = 0.5
            for i in range(len(region.routers)):
                for j in range(i + 2, len(region.routers)):
                    if random.random() < link_probability:
                        if self.ospf_max_num_links != float('inf'):
                            if len(self.links) + link_factor * len(region.routers) >= self.ospf_max_num_links:
                                print("Max link exceeded")
                                return
                        r1 = region.routers[i]
                        r2 = region.routers[j]
                        cost = random.randint(self.cost_min, self.cost_max)
                        link = Link(r1, r2, cost, cross_region=False)
                        self.links[(r1.router_id, r2.router_id)] = link
                        region.links.append(link)
                        r1.siblings.append(r2)
                        r2.siblings.append(r1)

    def _add_inter_region_links(self):
        """Connect child regions to parent via border routers."""
        for region_path, region in self.regions.items():
            if region.parent is None:  # Skip root region
                continue
            
            parent_region = region.parent
            if not parent_region.routers:
                continue
            
            # Determine number of border routers
            border_count = min(
                self.count_border_routers[region.depth],
                len(region.routers),
                len(parent_region.routers)
            )
            
            # First border_count routers are border routers
            for i in range(border_count):
                border_router = region.routers[i]
                border_router.is_border_router = True
                region.border_routers.append(border_router)
                
                # Connect to random parent routers
                num_connections = min(
                    self.count_parent_connections,
                    len(parent_region.routers)
                )
                selected_parents = random.sample(parent_region.routers, num_connections)
                
                for parent_router in selected_parents:
                    cost = random.randint(self.cost_min, self.cost_max)
                    link = Link(border_router, parent_router, cost, cross_region=True)
                    self.links[(border_router.router_id, parent_router.router_id)] = link
                    border_router.parent_routers.append(parent_router)
                    parent_router.child_border_routers.append(border_router)
                    # Mark this parent router as receiving connections from child border routers
                    parent_router.is_parent_router = True
    
    # ── Helper methods for protocol ───────────────────────────────────────────
    
    def get_region(self, region_path):
        """Get a region by its path."""
        return self.regions.get(region_path)
    
    def get_same_region_neighbours(self, router_id):
        """Get all neighbours of a router within the same region."""
        router = self.routers.get(router_id)
        if not router:
            return []
        
        neighbours = []
        for link_key, link in self.links.items():
            if link.alive and not link.cross_region:
                if link.router_1.router_id == router_id:
                    neighbours.append((link.router_2.router_id, link.cost))
                elif link.router_2.router_id == router_id:
                    neighbours.append((link.router_1.router_id, link.cost))
        
        return neighbours
    
    def get_routers_in_region(self, region_path):
        """Get all router IDs in a region."""
        region = self.regions.get(region_path)
        if not region:
            return []
        return [r.router_id for r in region.routers]
    
    def get_border_routers_in_region(self, region_path):
        """Get all border router IDs in a region."""
        region = self.regions.get(region_path)
        if not region:
            return []
        return [r.router_id for r in region.border_routers]
    
    def fail_link(self, r1_id, r2_id):
        """Mark a link as failed."""
        link = self.links.get((r1_id, r2_id)) or self.links.get((r2_id, r1_id))
        if link:
            link.alive = False
            return True
        return False
    
    def recover_link(self, r1_id, r2_id):
        """Mark a link as recovered."""
        link = self.links.get((r1_id, r2_id)) or self.links.get((r2_id, r1_id))
        if link:
            link.alive = True
            return True
        return False
    
    def is_link_alive(self, r1_id, r2_id):
        """Check if a link is alive."""
        link = self.links.get((r1_id, r2_id)) or self.links.get((r2_id, r1_id))
        if link:
            return link.alive
        return False
                            

class Region:
    """Represents a region in the hierarchy."""
    
    def __init__(self, name, depth, parent, path):
        self.name = name                # Simple name (e.g., 'a0')
        self.path = path                # Full path (e.g., 'root/a0')
        self.depth = depth              # Depth in tree
        self.parent = parent            # Parent region (None if root)
        self.children = []              # Child regions
        self.routers = []               # All routers in this region
        self.border_routers = []        # Border routers only
        self.links = []                 # Intra-region links
    
    @property
    def region_name(self):
        """Alias for path, used by protocol."""
        return self.path
    
    @property
    def router_ids(self):
        """Get all router IDs in this region."""
        return [r.router_id for r in self.routers]


class Router:
    """Represents a router in the network."""
    
    def __init__(self, router_id, region, region_path, ip_address):
        self.router_id = router_id
        self.is_root_router = False
        self.region = region              # Region this router belongs to
        self.region_path = region_path    # Path of region (for protocol)
        self.ip_address = ip_address      # Management IP network
        self.is_border_router = False     # True if connects to parent
        self.is_parent_router = False     # True if receives connections from child border routers
        self.parent_routers = []          # Parent region routers (if border router)
        self.child_border_routers = []    # Child border routers
        self.siblings = []                # Neighbours in same region
    
    @property
    def depth(self):
        """Return depth from region."""
        return self.region.depth
    
    @property
    def region_name(self):
        """Return region path."""
        return self.region_path
    
    def get_network_prefix(self):
        """Get network prefix as an IP address string."""
        return str(self.ip_address.network_address)
    
    def get_network_subnet(self):
        return self.ip_address.prefixlen
    

class Link:
    def __init__(self, router_1, router_2, cost, cross_region):
        self.router_1 = router_1
        self.router_2 = router_2
        self.cost = cost
        self.cross_region = cross_region
        self.alive = True
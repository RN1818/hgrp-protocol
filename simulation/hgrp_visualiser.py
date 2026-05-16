"""
hgrp_visualiser.py
Network visualization for HGRP simulations using Kamada-Kawai layout and comprehensive legend.
"""

import os
from typing import List, Dict, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

# ── Matplotlib Configuration ──────────────────────────────────────────────────

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
})

# ── Color Palette ─────────────────────────────────────────────────────────────

# Depth-based color mapping (one color per depth level)
DEPTH_COLORS = {
    0: "#a1008c",
    1: "#eff300f9",
    2: '#2ca02c',
    3: '#d62728',
    4: "#22eed3",
    5: '#8c564b',
}
# DEPTH_COLORS = {
#     0: '#1f77b4',  # Blue for root (depth 0)
#     1: '#ff7f0e',  # Orange for depth 1
#     2: '#2ca02c',  # Green for depth 2
#     3: '#d62728',  # Red for depth 3
#     4: '#9467bd',  # Purple for depth 4
#     5: '#8c564b',  # Brown for depth 5
# }

def _get_depth_color(depth: int) -> str:
    """Get color for a router based on depth."""
    if depth in DEPTH_COLORS:
        return DEPTH_COLORS[depth]
    # For deeper levels, cycle through colors
    return list(DEPTH_COLORS.values())[depth % len(DEPTH_COLORS)]


# Edge colors
INTRA_EDGE_COLOUR = "#555555"       # Dark grey
CROSS_EDGE_COLOUR = "#FF6F00"       # Orange
FAILED_EDGE_COLOUR = "#FF5252"      # Bright red
HIGHLIGHT_EDGE_COLOUR = "#2600FF"   # Blue


# ── Network Drawing ───────────────────────────────────────────────────────────

def draw_network(topo, highlight_path: Optional[List[str]] = None,
                 title: str = 'HGRP Network',
                 output_dir: str = './output',
                 image_dpi: int = 130) -> None:
    """
    Draw the HGRP network with Kamada-Kawai layout.

    Parameters:
        topo:           TopologyData object with routers, regions, links
        highlight_path: Optional list of router IDs forming a forwarding path
        title:          Figure title and filename base
        output_dir:     Directory where to save PNG files
        image_dpi:      Resolution in dots per inch
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    filename = (title.lower().replace(' ', '_').replace('—', '')
                     .replace('–', '').replace(':', '')) + '.png'
    save_path = os.path.join(output_dir, filename)

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_title(title, fontsize=14, fontweight='bold', pad=14)
    ax.axis('off')

    # Build NetworkX graph
    G = nx.Graph()
    for rid, rnode in topo.routers.items():
        G.add_node(rid, region=rnode.region_path, is_border=rnode.is_border_router)

    for link_key, link in topo.links.items():
        G.add_edge(link.router_1.router_id, link.router_2.router_id,
                   cost=link.cost, alive=link.alive, cross=link.cross_region)

    # Draw components
    pos = nx.kamada_kawai_layout(G, scale=2)
    _draw_nodes(ax, G, pos, topo)
    _draw_edges(ax, G, pos, topo, highlight_path)
    _draw_labels(ax, G, pos)
    _draw_legend(ax, topo, highlight_path)

    plt.tight_layout()
    plt.savefig(save_path, dpi=image_dpi, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Graph saved: {save_path}")


# ── Node Drawing ──────────────────────────────────────────────────────────────

def _draw_nodes(ax, G, pos: Dict, topo) -> None:
    """Draw nodes colored by depth with size by router type."""
    node_colors = []
    node_sizes = []

    for rid in G.nodes():
        # Get depth from topology
        router = topo.routers[rid]
        depth = router.depth
        node_colors.append(_get_depth_color(depth))

        is_border = G.nodes[rid].get('is_border', False)
        is_root = router.is_root_router
        node_sizes.append(1000 if (is_border or is_root) else 500)

    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_colors,
        node_size=node_sizes,
        edgecolors='#000000',
        linewidths=1.2,
        ax=ax,
        alpha=0.92
    )


# ── Edge Drawing ──────────────────────────────────────────────────────────────

def _draw_edges(ax, G, pos: Dict, topo, highlight_path: Optional[List] = None) -> None:
    """Draw edges with categorization by type and state."""
    alive_intra = []
    alive_cross = []
    failed_edges = []

    for u, v, data in G.edges(data=True):
        if data['alive']:
            if data['cross']:
                alive_cross.append((u, v))
            else:
                alive_intra.append((u, v))
        else:
            failed_edges.append((u, v))

    # Prepare highlight path
    highlighted = []
    if highlight_path and len(highlight_path) > 1:
        path_set = set(zip(highlight_path[:-1], highlight_path[1:]))
        path_set |= {(b, a) for a, b in path_set}
        highlighted = [(u, v) for u, v in alive_intra + alive_cross 
                      if (u, v) in path_set or (v, u) in path_set]

    # Draw failed edges first
    if failed_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=failed_edges,
            edge_color=FAILED_EDGE_COLOUR,
            width=2.0,
            style='dotted',
            ax=ax,
            alpha=0.6
        )

    # Draw intra-region edges
    if alive_intra:
        nx.draw_networkx_edges(
            G, pos, edgelist=alive_intra,
            edge_color=INTRA_EDGE_COLOUR,
            width=1.5,
            ax=ax
        )

    # Draw cross-region edges
    if alive_cross:
        nx.draw_networkx_edges(
            G, pos, edgelist=alive_cross,
            edge_color=CROSS_EDGE_COLOUR,
            width=2.5,
            style='dashed',
            ax=ax
        )

    # Draw highlighted path on top
    if highlighted:
        nx.draw_networkx_edges(
            G, pos, edgelist=highlighted,
            edge_color=HIGHLIGHT_EDGE_COLOUR,
            width=3.0,
            ax=ax
        )


# ── Label Drawing ─────────────────────────────────────────────────────────────

def _draw_labels(ax, G, pos: Dict) -> None:
    """Draw short router names on nodes (only the part after the last '/')."""
    labels = {}
    for node in G.nodes():
        # Extract short name - get everything after the last '/'
        if '/' in node:
            short_name = node.split('/')[-1]
        else:
            short_name = node
        labels[node] = short_name
    
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_weight='bold', ax=ax,
                            font_color='black')


# ── Legend ────────────────────────────────────────────────────────────────────

def _draw_legend(ax, topo, highlight_path: Optional[List] = None) -> None:
    """Draw comprehensive legend."""
    legend_items = []

    # Depth legend
    legend_items.append(mpatches.Patch(facecolor='white', edgecolor='white',
                                       label='Hierarchy Depth:'))
    # Find max depth in topology
    max_depth = max((r.depth for r in topo.routers.values()), default=0)
    for depth in range(max_depth + 1):
        color = _get_depth_color(depth)
        legend_items.append(mpatches.Patch(facecolor=color, edgecolor='black',
                                           linewidth=0.8, label=f"  • Depth {depth}"))

    legend_items.append(None)  # Separator

    # Node types
    legend_items.append(
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='grey',
                   markersize=8, label='Internal router')
    )
    legend_items.append(
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='grey',
                   markersize=10, label='Border router')
    )

    legend_items.append(None)  # Separator

    # Edge types
    legend_items.append(
        plt.Line2D([0], [0], color=INTRA_EDGE_COLOUR, linewidth=1.5,
                   label='Intra-region link')
    )
    legend_items.append(
        plt.Line2D([0], [0], color=CROSS_EDGE_COLOUR, linewidth=2.5,
                   linestyle='dashed', label='Cross-region link')
    )
    legend_items.append(
        plt.Line2D([0], [0], color=FAILED_EDGE_COLOUR, linewidth=2.0,
                   linestyle='dotted', label='Failed link')
    )

    if highlight_path:
        legend_items.append(
            plt.Line2D([0], [0], color=HIGHLIGHT_EDGE_COLOUR, linewidth=4,
                       label='Packet path')
        )

    # Filter None entries
    legend_items_filtered = [l for l in legend_items if l is not None]

    ax.legend(handles=legend_items_filtered, loc='upper left',
              bbox_to_anchor=(0.01, 0.99), fontsize=8,
              framealpha=0.95, title='Legend',
              title_fontsize=9, edgecolor='#333333', fancybox=True)


# ── Packet Trace Printing ─────────────────────────────────────────────────────

def print_hop_trace(hops: List, src: str, dst_prefix: str) -> None:
    """Print a formatted packet trace showing hop-by-hop forwarding."""
    print(f"\n  Packet trace: {src} → {dst_prefix}")
    print(f"  {'-' * 70}")
    for i, hop in enumerate(hops):
        icon = {
            'LOCAL': '→',
            'SUMMARY': '↓',
            'ESCALATE': '↑',
            'DELIVERED': 'OK',
            'DROPPED': 'XX',
            'NO_ROUTE': 'XX',
            'LOOP_DETECTED': '⟳',
        }.get(hop.action, '?')

        print(f"  {i+1:2d}. {icon} {hop.router_id:<20} "
              f"{hop.action:<18} {hop.reason if hop.reason else ''}")

    print(f"  {'-' * 70}")
    final = hops[-1]
    if final.action == 'DELIVERED':
        print(f"  Result: DELIVERED")
    elif final.action in ('DROPPED', 'NO_ROUTE'):
        print(f"  Result: DROPPED — {final.reason}")
    elif final.action == 'LOOP_DETECTED':
        print(f"  Result: LOOP DETECTED")
    print()

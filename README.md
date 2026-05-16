# HGRP Protocol

This repository contains a simulation of the Hierarchical Gradient Routing Protocol (HGRP), along with supporting visualisation tools.

The Hierarchical Gradient Routing Protocol (HGRP) is a link-state interior gateway protocol designed for a single administrative domain. It extends OSPF by replacing the fixed two-level area structure with a recursively uniform hierarchy of arbitrary depth, where identical forwarding and flooding rules apply at every level.

HGRP preserves OSPF’s adjacency model, reliable flooding, and Dijkstra-based shortest path computation. It introduces Summary Advertisements to propagate reachability upward in the hierarchy while limiting topology change notifications to the originating region.

The design addresses OSPF’s scalability limitations, where full link-state replication within an area causes network-wide flooding and frequent SPF recomputation. Although OSPF areas reduce this overhead, the fixed two-level structure is insufficient for deeply nested networks.

HGRP generalises the hierarchy to an operator-defined multi-level model and uses a forwarding escalation mechanism to maintain loop-free routing without requiring global topology knowledge at every router.


## Content

The `/simulation/` directory contains the following files:

- `hgrp_main.py` - interactive CLI for building and simulating an HGRP network
- `packet_transfer_simulator.py` - batch packet-flow simulator
- `hgrp_vs_ospf_comparison.py` - comparison report for HGRP and OSPF
- `hgrp_protocol.py` - routing protocol implementation
- `hgrp_topology.py` - topology generation
- `hgrp_visualiser.py` - network drawing and hop tracing
- `config_hgrp.json` - default HGRP simulation config
- `config_ospf.json` - default OSPF comparison config

## Requirements

Install the Python packages listed in `requirements.txt`.

If you are using the workspace virtual environment, activate it first, then install dependencies:

```bash
pip install -r requirements.txt
```

## How to run

### Interactive HGRP simulator

Run the CLI and use the built-in commands such as `draw`, `routers`, `regions`, `routing`, and `forward`:

```bash
python hgrp_main.py
```

Available CLI commands:

- `draw` - redraw the network graph
- `info <router>` - show router identity and config
- `address <router>` - show the router network prefix and subnet
- `lsdb <router>` - show the Link State Database
- `spf <router>` - show the SPF tree
- `routing <router>` - show the routing table
- `summary <router>` - show the summary table
- `forward <router> <prefix>` - trace a packet hop by hop
- `step` - run one propagation round
- `routers` - list all router IDs
- `regions` - list all regions and their routers
- `help` - show the CLI help text
- `quit` - exit the simulator

### HGRP vs OSPF comparison

This generates a comparison report using `config_hgrp.json` and `config_ospf.json`:

```bash
python hgrp_vs_ospf_comparison.py
```

## Configuration

- `config_hgrp.json` controls the HGRP topology used by the simulator.
- `config_ospf.json` controls the OSPF comparison topology.

## Output

Generated diagrams and other artifacts are written to the `output/` folder used by each script.

## Contributors

- [Roshan Nimantha](https://github.com/RN1818)
- [Manitha Ayanaja](https://github.com/ManiiAya)
- [Sasith Induwara](https://github.com/SasithIM)
- [Mishen Weerasinghe](https://github.com/Mishen-Weerasinghe)

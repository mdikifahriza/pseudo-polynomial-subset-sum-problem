"""
ATSP - Input Parsing, TSPLIB Format Support, Matrix Builders, and Precomputations
Supports Euclidean coordinate inputs, TSPLIB (.tsp) standard format, general distance matrices,
and Held-Karp / MST lower-bound precomputations.
"""
import math
import heapq
from typing import List, Tuple, Union, Optional, Dict, Set, Any


def parse_coords_input(raw: str) -> List[Tuple[float, float]]:
    """
    Parses coordinate string formats:
    - "0,0; 10,0; 10,10; 0,10"
    - "0 0 \n 10 0 \n 10 10"
    - "1 25.0 30.5 \n 2 40.0 55.2"
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Coordinate input string cannot be empty.")

    raw_lines = raw.replace(";", "\n").split("\n")
    lines = [
        x.strip()
        for x in raw_lines
        if x.strip() and not x.strip().startswith(("#", "//", "TYPE", "NAME", "CITY", "COMMENT"))
    ]
    coords: List[Tuple[float, float]] = []

    for line in lines:
        parts = [p.strip() for p in line.replace(",", " ").split() if p.strip()]
        if len(parts) < 2:
            continue
        try:
            if len(parts) >= 3 and parts[0].isdigit():
                x, y = float(parts[1]), float(parts[2])
            else:
                x, y = float(parts[0]), float(parts[1])
            coords.append((x, y))
        except ValueError:
            raise ValueError(f"Invalid numeric coordinate entry: '{line}'")

    if len(coords) < 3:
        raise ValueError(f"At least 3 cities are required to form a Hamiltonian cycle (found {len(coords)}).")

    return coords


def parse_matrix_input(raw: str) -> List[List[float]]:
    """
    Parses a 2D distance matrix string formatted by rows.
    """
    raw_lines = raw.strip().split("\n")
    lines = [
        x.strip()
        for x in raw_lines
        if x.strip() and not x.strip().startswith(("#", "//", "TYPE", "NAME", "MATRIX", "COMMENT"))
    ]
    matrix: List[List[float]] = []
    for line in lines:
        row = [float(p.strip()) for p in line.replace(",", " ").split() if p.strip()]
        if row:
            matrix.append(row)

    n = len(matrix)
    if n < 3:
        raise ValueError(f"Distance matrix must be at least 3x3 (detected {n}x{n}).")
    for i, row in enumerate(matrix):
        if len(row) != n:
            raise ValueError(f"Row {i} has length {len(row)}, expected {n}.")
    return matrix


def parse_tsplib_content(content: str) -> Tuple[List[List[float]], Optional[List[Tuple[float, float]]], Dict[str, Any]]:
    """
    Parses standard TSPLIB (.tsp) benchmark format files.
    Supports EUC_2D, CEIL_2D, ATT, GEO, and EXPLICIT matrix representations.
    Returns: (adj_matrix, coords_or_None, metadata_dict)
    """
    lines = content.strip().splitlines()
    meta: Dict[str, str] = {}
    section = "HEADER"
    coord_lines: List[str] = []
    weight_lines: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line == "EOF":
            continue

        if section == "HEADER":
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().upper()] = v.strip()
            elif line.upper() == "NODE_COORD_SECTION":
                section = "NODE_COORD_SECTION"
            elif line.upper() == "EDGE_WEIGHT_SECTION":
                section = "EDGE_WEIGHT_SECTION"
            elif line.upper() in ["DISPLAY_DATA_SECTION", "TOUR_SECTION"]:
                section = "OTHER_SECTION"
        elif section == "NODE_COORD_SECTION":
            if line.upper() in ["EDGE_WEIGHT_SECTION", "DISPLAY_DATA_SECTION", "TOUR_SECTION", "EOF"]:
                section = "OTHER_SECTION"
            else:
                coord_lines.append(line)
        elif section == "EDGE_WEIGHT_SECTION":
            if line.upper() in ["NODE_COORD_SECTION", "DISPLAY_DATA_SECTION", "TOUR_SECTION", "EOF"]:
                section = "OTHER_SECTION"
            else:
                weight_lines.append(line)

    dimension = int(meta.get("DIMENSION", 0))
    weight_type = meta.get("EDGE_WEIGHT_TYPE", "EUC_2D").upper()

    # 1. Parse NODE_COORD_SECTION
    if coord_lines:
        coords: List[Tuple[float, float]] = []
        for cl in coord_lines:
            tokens = cl.replace(",", " ").split()
            if len(tokens) >= 3:
                coords.append((float(tokens[1]), float(tokens[2])))
            elif len(tokens) == 2:
                coords.append((float(tokens[0]), float(tokens[1])))

        n = len(coords)
        if dimension > 0 and n != dimension:
            # use actual coordinates count
            dimension = n

        adj = [[0.0] * n for _ in range(n)]

        if weight_type in ["EUC_2D", "CEIL_2D"]:
            for i in range(n):
                for j in range(i + 1, n):
                    d = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
                    if weight_type == "CEIL_2D":
                        d = math.ceil(d)
                    adj[i][j] = float(d)
                    adj[j][i] = float(d)
        elif weight_type == "ATT":
            # Pseudo-Euclidean distance defined in TSPLIB specification
            for i in range(n):
                for j in range(i + 1, n):
                    xd = coords[i][0] - coords[j][0]
                    yd = coords[i][1] - coords[j][1]
                    rij = math.sqrt((xd * xd + yd * yd) / 10.0)
                    tij = round(rij)
                    d = tij + 1 if tij < rij else tij
                    adj[i][j] = float(d)
                    adj[j][i] = float(d)
        elif weight_type == "GEO":
            # Geographical distance (latitude and longitude in degrees and minutes)
            def to_rad(coord):
                deg = int(coord)
                min_val = coord - deg
                return math.pi * (deg + 5.0 * min_val / 3.0) / 180.0

            rads = [(to_rad(c[0]), to_rad(c[1])) for c in coords]
            rrr = 6378.388
            for i in range(n):
                for j in range(i + 1, n):
                    q1 = math.cos(rads[i][1] - rads[j][1])
                    q2 = math.cos(rads[i][0] - rads[j][0])
                    q3 = math.cos(rads[i][0] + rads[j][0])
                    d = int(rrr * math.acos(0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)) + 1.0)
                    adj[i][j] = float(d)
                    adj[j][i] = float(d)
        else:
            # Fallback to standard Euclidean
            adj = build_adj_matrix(coords)

        return adj, coords, meta

    # 2. Parse EDGE_WEIGHT_SECTION (Explicit Matrix / Lower Row / Full Matrix)
    if weight_lines:
        tokens = []
        for wl in weight_lines:
            tokens.extend([float(x) for x in wl.replace(",", " ").split() if x.strip()])

        n = dimension or int(math.isqrt(len(tokens)))
        if n * n == len(tokens):  # Full matrix
            adj = [[0.0] * n for _ in range(n)]
            idx = 0
            for i in range(n):
                for j in range(n):
                    adj[i][j] = tokens[idx]
                    idx += 1
            return adj, None, meta

        # Triangular / general
        adj = [[0.0] * n for _ in range(n)]
        idx = 0
        for i in range(n):
            for j in range(i + 1):
                if idx < len(tokens):
                    adj[i][j] = tokens[idx]
                    adj[j][i] = tokens[idx]
                    idx += 1
        return adj, None, meta

    raise ValueError("Failed to locate NODE_COORD_SECTION or EDGE_WEIGHT_SECTION in TSPLIB file.")


def build_adj_matrix(coords: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Computes pairwise Euclidean distance matrix for a list of 2D coordinates.
    """
    n = len(coords)
    adj = [[0.0] * n for _ in range(n)]
    for i in range(n):
        x1, y1 = coords[i]
        for j in range(i + 1, n):
            x2, y2 = coords[j]
            d = math.hypot(x1 - x2, y1 - y2)
            adj[i][j] = d
            adj[j][i] = d
    return adj


def build_min_out_edges(adj: List[List[float]]) -> List[float]:
    """
    Finds the minimum outgoing edge weight for each vertex i to any other vertex j != i.
    """
    n = len(adj)
    min_out = [float("inf")] * n
    for i in range(n):
        for j in range(n):
            if i != j and adj[i][j] < min_out[i]:
                min_out[i] = adj[i][j]
    return min_out


def build_min_in_edges(adj: List[List[float]]) -> List[float]:
    """
    Finds the minimum incoming edge weight to each vertex j from any other vertex i != j.
    """
    n = len(adj)
    min_in = [float("inf")] * n
    for j in range(n):
        for i in range(n):
            if i != j and adj[i][j] < min_in[j]:
                min_in[j] = adj[i][j]
    return min_in


def compute_mst_cost(
    adj: List[List[float]],
    unvisited: Tuple[int, ...]
) -> float:
    """
    Computes the Minimum Spanning Tree (MST) weight on the induced subgraph of 'unvisited' vertices
    using Prim's Algorithm.
    Returns 0.0 if |unvisited| <= 1.
    """
    k = len(unvisited)
    if k <= 1:
        return 0.0

    nodes = list(unvisited)
    in_mst = [False] * k
    min_edge = [float("inf")] * k
    min_edge[0] = 0.0

    total_weight = 0.0

    for _ in range(k):
        u = -1
        u_dist = float("inf")
        for i in range(k):
            if not in_mst[i] and min_edge[i] < u_dist:
                u_dist = min_edge[i]
                u = i

        if u == -1 or u_dist == float("inf"):
            return float("inf")

        in_mst[u] = True
        total_weight += u_dist
        u_city = nodes[u]

        for v in range(k):
            if not in_mst[v]:
                v_city = nodes[v]
                w = adj[u_city][v_city]
                if w < min_edge[v]:
                    min_edge[v] = w

    return total_weight


def build_candidate_lists(adj: List[List[float]]) -> List[List[Tuple[int, float]]]:
    """
    Precomputes all outgoing neighbors for each city i, sorted by distance ascending.
    Used in DFS branching for zero-allocation traversal with greedy best-first order.
    """
    n = len(adj)
    candidates: List[List[Tuple[int, float]]] = []
    for i in range(n):
        neighbors = sorted(
            [(j, adj[i][j]) for j in range(n) if j != i and adj[i][j] < float("inf")],
            key=lambda x: x[1]
        )
        candidates.append(neighbors)
    return candidates


def compute_lagrangian_bound(
    adj: List[List[float]],
    best_known: float,
    max_iter: int = 80,
    lambda_init: float = 0.5,
) -> float:
    """
    Computes the Held-Karp Lagrangian Relaxation lower bound using subgradient optimization.
    Run ONCE at the root node before DFS starts to prune subtrees aggressively.
    """
    n = len(adj)
    if n < 4:
        return 0.0

    w = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                w[i][j] = adj[i][j]

    pi = [0.0] * n
    best_lb = 0.0
    step = lambda_init

    for iteration in range(max_iter):
        nodes = list(range(1, n))
        k = len(nodes)
        in_mst = [False] * k
        min_edge = [float("inf")] * k
        deg_mst = [0] * n
        min_edge[0] = 0.0
        mst_cost = 0.0
        feasible = True

        for _ in range(k):
            u = -1
            u_dist = float("inf")
            for i in range(k):
                if not in_mst[i] and min_edge[i] < u_dist:
                    u_dist = min_edge[i]
                    u = i
            if u == -1 or u_dist == float("inf"):
                feasible = False
                break
            in_mst[u] = True
            mst_cost += u_dist
            u_city = nodes[u]
            if u_dist > 0:
                deg_mst[u_city] += 1

            for v in range(k):
                if not in_mst[v]:
                    v_city = nodes[v]
                    modified_w = w[u_city][v_city] + pi[u_city] + pi[v_city]
                    if modified_w < min_edge[v]:
                        min_edge[v] = modified_w

        if not feasible:
            break

        edges_from_0 = sorted(
            w[0][j] + pi[0] + pi[j]
            for j in range(1, n)
            if w[0][j] < float("inf")
        )
        if len(edges_from_0) < 2:
            break
        one_tree_cost = mst_cost + edges_from_0[0] + edges_from_0[1]
        deg_mst[0] = 2

        lb = one_tree_cost - 2.0 * sum(pi)
        if lb > best_lb:
            best_lb = lb
            if best_lb >= best_known - 1e-6:
                break

        g = [deg_mst[i] - 2 for i in range(n)]
        g_norm_sq = sum(gi * gi for gi in g)
        if g_norm_sq < 1e-9:
            break

        gap = best_known - lb
        if gap <= 0:
            break
        step_size = lambda_init * gap / g_norm_sq

        for i in range(n):
            pi[i] += step_size * g[i]

        lambda_init = max(0.01, lambda_init * 0.99)

    return best_lb


def parse_edge_list(raw: str, directed: bool = False) -> List[List[float]]:
    """
    Parses sparse edge list formatted as:
      u  v  weight
      0  1  10.5
      0  2  30.0
      ...
    """
    lines = [x.strip() for x in raw.strip().split("\n") if x.strip() and not x.strip().startswith(("#", "//", "TYPE", "EDGE"))]
    edges = []
    max_node = -1

    for line in lines:
        parts = [p.strip() for p in line.replace(",", " ").split() if p.strip()]
        if len(parts) < 3:
            continue
        try:
            u, v, w = int(parts[0]), int(parts[1]), float(parts[2])
            edges.append((u, v, w))
            max_node = max(max_node, u, v)
        except ValueError:
            raise ValueError(f"Invalid edge list row format: '{line}'")

    n = max_node + 1
    if n < 3:
        raise ValueError(f"At least 3 cities required in edge list (found {n} cities).")

    adj = [[float("inf")] * n for _ in range(n)]
    for i in range(n):
        adj[i][i] = 0.0

    for u, v, w in edges:
        adj[u][v] = w
        if not directed:
            adj[v][u] = w

    return adj


def validate_adj_matrix(adj: List[List[float]]) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validates adjacency matrix properties.
    Returns: (is_valid, error_msg, warnings)
    """
    warnings = []
    n = len(adj)
    if n < 3:
        return False, f"Number of cities ({n}) is fewer than 3.", warnings

    for i in range(n):
        if len(adj[i]) != n:
            return False, f"Row {i} has length {len(adj[i])}, expected {n}.", warnings
        if adj[i][i] != 0.0:
            warnings.append(f"Diagonal [{i}][{i}] has value {adj[i][i]} instead of 0.0.")

    is_symmetric = True
    has_negative = False
    for i in range(n):
        for j in range(n):
            val = adj[i][j]
            if val < 0:
                has_negative = True
            if abs(adj[i][j] - adj[j][i]) > 1e-6:
                is_symmetric = False

    if has_negative:
        return False, "Distance matrix contains negative values (unsupported).", warnings

    if not is_symmetric:
        warnings.append("Asymmetric distance matrix detected (ATSP instance).")

    return True, None, warnings


def parse_unified_input(raw: str) -> Tuple[List[List[float]], Optional[List[Tuple[float, float]]]]:
    """
    Auto-detects and parses TSPLIB files, coordinate lists, NxN distance matrices, or edge lists.
    Returns: (adj_matrix, coords_or_None)
    """
    raw_clean = raw.strip()
    if not raw_clean:
        raise ValueError("Input string cannot be empty.")

    upper = raw_clean.upper()

    # 1. TSPLIB detection
    if "NODE_COORD_SECTION" in upper or "EDGE_WEIGHT_SECTION" in upper or "TYPE: TSP" in upper or "TYPE : TSP" in upper:
        adj, coords, _ = parse_tsplib_content(raw_clean)
        return adj, coords

    # 2. Check explicit headers
    if "TYPE: COORDINATES" in upper or "TYPE: COORDS" in upper or "JENIS: KOORDINAT" in upper:
        coords = parse_coords_input(raw_clean)
        return build_adj_matrix(coords), coords

    if "TYPE: MATRIX" in upper or "JENIS: MATRIKS" in upper:
        adj = parse_matrix_input(raw_clean)
        is_ok, err, _ = validate_adj_matrix(adj)
        if not is_ok:
            raise ValueError(err)
        return adj, None

    if "TYPE: EDGE_LIST" in upper or "JENIS: EDGE_LIST" in upper:
        adj = parse_edge_list(raw_clean)
        is_ok, err, _ = validate_adj_matrix(adj)
        if not is_ok:
            raise ValueError(err)
        return adj, None

    # 3. Auto-detection based on content rows
    data_lines = [
        line.strip()
        for line in raw_clean.split("\n")
        if line.strip() and not line.strip().startswith(("#", "//"))
    ]
    if not data_lines:
        raise ValueError("No numeric data found in input.")

    first_tokens = [p.strip() for p in data_lines[0].replace(",", " ").replace(";", " ").split() if p.strip()]

    if len(first_tokens) == 3:
        all_3 = True
        for dl in data_lines:
            tokens = [p.strip() for p in dl.replace(",", " ").replace(";", " ").split() if p.strip()]
            if len(tokens) != 3:
                all_3 = False
                break
        if all_3:
            try:
                adj = parse_edge_list(raw_clean)
                return adj, None
            except Exception:
                pass

    if len(first_tokens) == 2:
        try:
            coords = parse_coords_input(raw_clean)
            return build_adj_matrix(coords), coords
        except Exception:
            pass

    try:
        adj = parse_matrix_input(raw_clean)
        is_ok, err, _ = validate_adj_matrix(adj)
        if is_ok:
            return adj, None
    except Exception:
        pass

    coords = parse_coords_input(raw_clean)
    return build_adj_matrix(coords), coords

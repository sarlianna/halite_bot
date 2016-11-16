import logging

ACT_DIRECTIONS = list(range(1, 5))
log = logging.getLogger()


def get_nearby_pieces(gmap, location):
    """Returns a list of (location, Site) tuples."""
    nearby_sites = [gmap.getSite(location, d) for d in ACT_DIRECTIONS]
    nearby_locations = [gmap.getLocation(location, d) for d in ACT_DIRECTIONS]
    tuples = list(zip(nearby_locations, nearby_sites))
    return tuples


def get_nearby_owned_pieces(cid, gmap, location):
    """Returns a list of (location, Site) tuples with sites owned by cid."""
    tuples = get_nearby_pieces(gmap, location)
    neutral_tuples = [t for t in tuples if t[1].owner == cid]
    return neutral_tuples


def get_weakest_site(pieces):
    """Accepts a list of tuples of form (*, site).
    Returns a single (*, site) tuple where site has the lowest strength of all sites in the list."""
    weakest = min([(x, site) for x, site in pieces], key=lambda x: x[1].strength)
    return weakest


def get_total_strength(pieces):
    return sum([piece[1].strength for piece in pieces])


def get_farthest_piece(gmap, pieces, target):
    farthest = max([(gmap.getDistance(loc, target), (loc, piece)) for loc, piece in pieces], key=lambda x: x[0])
    return farthest[1]


def get_closest_piece(gmap, pieces, target):
    closest = min([(gmap.getDistance(loc, target), (loc, piece)) for loc, piece in pieces], key=lambda x: x[0])
    return closest[1]


def sort_pieces_by_distance(gmap, pieces, target, ascending=True):
    """Sorts pieces, doesn't return distance, only ordered pieces."""
    distances = [(gmap.getDistance(loc, target), (loc, piece)) for loc, piece in pieces]
    sort = list(sorted(distances, key=lambda x: x[0], reverse=not(ascending)))
    res = [r[1] for r in sort]
    return res


def find_allied_path(gmap, my_id, loc, target):
    # shitty non-working pathfinding.
    nearby_allied = get_nearby_owned_pieces(my_id, gmap, loc)
    if not nearby_allied:
        nearby = get_nearby_pieces(gmap, loc)
        zero_str = [n for n in nearby if n[1].strength == 0]
        if zero_str:
            nearby_allied = zero_str
        else:
            return random.choice(DIRECTIONS)
    best = get_closest_piece(gmap, nearby_allied, target)
    return get_direction(gmap, loc, best[0])


def get_direction(gmap, loc, target):
    if gmap.getDistance(loc, target) != 1:
        return None
    for d in ACT_DIRECTIONS:
        if gmap.getLocation(loc, d) == target:
            return d


def find_unallied_edges(gmap, my_id, pieces):
    existing_locs = []
    unique_edges = []
    log.debug(pieces)
    log.debug([piece[0] for piece in pieces])
    edges = sum([get_nearby_pieces(gmap, piece[0]) for piece in pieces], [])
    for loc, edge in edges:
        if edge.owner != my_id and loc not in existing_locs:
            existing_locs.append(loc)
            unique_edges.append((loc, edge))

    return unique_edges

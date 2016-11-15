# TODO:
# - seed 1907675159 against v.2 snapshot shows a huge weakness when fighthing enemies. (replay saved as bad_engage_loop)
# - wastefully combines past strength cap
# - singular target mentality becomes useless with large amounts of territory.
#     lots of pieces in the middle are running around to different places, but pieces on the edges are already strong enough to take the target.

from hlt import (
    Location,
    Move,
    DIRECTIONS,
    CARDINALS,
    STILL,
    NORTH,
    EAST,
    SOUTH,
    WEST,

)

from networking import (
    getFrame as get_frame,
    getInit as get_init,
    sendFrame as send_frame,
    sendInit as send_init,
)
import random
import logging
import functools
import traceback

ACT_DIRECTIONS = list(range(1, 5))
logging.basicConfig(filename="vdot1_garbage.log")
log = logging.getLogger()
log.setLevel(logging.DEBUG)

def init():
    my_id, game_map = get_init()
    data = {"piece_locs": [], "target_loc": None, "edges": []}
    for y in range(game_map.height):
        for x in range(game_map.width):
            location = Location(x, y)
            site = game_map.getSite(location)
            if site.owner == my_id:
                data["piece_locs"].append(location)

    nearby = get_nearby_owned_pieces(0, game_map, data["piece_locs"][0])
    data["edges"] = nearby
    data["target"] = get_weakest_site(nearby)
    data["target_loc"] = data["target"][0]

    send_init("worthless garbage NEET v.1")
    return my_id, game_map, data


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


def find_allied_path(gmap, my_id, loc, target):
    # shitty non-working pathfinding.
    nearby_allied = get_nearby_owned_pieces(my_id, gmap, loc)
    best = get_closest_piece(gmap, nearby_allied, target)
    return get_direction(gmap, loc, best[0])


def get_direction(gmap, loc, target):
    if gmap.getDistance(loc, target) != 1:
        return None
    for d in ACT_DIRECTIONS:
        if gmap.getLocation(loc, d) == target:
            return d


def take_turn(my_id, game_map, data):
    get_nearby_neutral_pieces = functools.partial(get_nearby_owned_pieces, 0)
    get_nearby_allied_pieces = functools.partial(get_nearby_owned_pieces, my_id)
    under_attack = False
    data["pieces"] = []
    data["edges"] = []

    def get_updated_pieces(my_id, game_map, data):
        def update_pieces():
            for loc in data["piece_locs"]:
                site = game_map.getSite(loc)
                if site.owner != my_id:
                    under_attack = True
                    data["piece_locs"].remove(loc)
                else:
                    data["pieces"].append((loc, site))

        def update_edges():
            existing_locs = []
            unique_edges = []
            edges = sum([get_nearby_pieces(game_map, piece[0]) for piece in data["pieces"]], [])
            for loc, edge in edges:
                if edge.owner != my_id and loc not in existing_locs:
                    existing_locs.append(loc)
                    unique_edges.append((loc, edge))
            data["edges"] = unique_edges

        def update_target():
            target = game_map.getSite(data["target_loc"])
            adjacent_allied = [p for p in get_nearby_pieces(game_map, data["target_loc"]) if p[1].owner == my_id]

            if target.owner == my_id or not adjacent_allied:
                data["target_loc"] = None
                data["target"] = None
            else:
                data["target"] = (data["target_loc"], target)

        update_pieces()
        update_edges()
        update_target()

        return data

    def return_or_find_target(my_id, game_map, data):
        if data["target"] is not None:
            return data["target"]
        new_target = get_weakest_site(data["edges"])
        data["target"] = new_target
        data["target_loc"] = data["target"][0]
        return new_target

    def attack_target_or_wait(my_id, game_map, data):
        moves = []
        log.debug("total strength this turn: {}".format(get_total_strength(data["pieces"])))
        if get_total_strength(data["pieces"]) > data["target"][1].strength:
            # attack
            adjacent_allied = [p for p in get_nearby_pieces(game_map, data["target"][0]) if p[1].owner == my_id]
            log.debug("adjacent allied: {}".format(adjacent_allied))
            adjacent_loc = [p[0] for p in adjacent_allied]
            non_adjacent_allied = [p for p in data["pieces"] if p[0] not in adjacent_loc]

            for l, s in non_adjacent_allied:
                if s.strength > 10:
                    nearest_adj = get_closest_piece(game_map, adjacent_allied, l)
                    moves.append(Move(l, find_allied_path(game_map, my_id, l, nearest_adj[0])))
                else:
                    moves.append(Move(l, STILL))

            if get_total_strength(adjacent_allied) > data["target"][1].strength:
                for l, s in adjacent_allied:
                    moves.append(Move(l, get_direction(game_map, l, data["target"][0])))
                    data["piece_locs"].append(data["target"][0])
            else:
                for l, s in adjacent_allied:
                    moves.append(Move(l, STILL))

        else:
            # wait
            for l, s in data["pieces"]:
                moves.append(Move(l, STILL))

        return moves

    data = get_updated_pieces(my_id, game_map, data)
    target = return_or_find_target(my_id, game_map, data)
    moves = attack_target_or_wait(my_id, game_map, data)
    log.debug("\n\ttarget:{}".format(target))
    log.debug("\n\tmoves:{}".format([(m.loc, m.direction) for m in moves]))
    send_frame(moves)

    return data


if __name__ == "__main__":
    try:
        mid, gmap, data = init()
        frame = 0
        while True:
            log.debug("frame:{}".format(frame))
            gmap = get_frame()
            data = take_turn(mid, gmap, data)
            frame += 1
    except Exception as e:
        ex = traceback.format_exc()
        log.debug(ex)
        # this makes the game env stop.
        print("fucked up.")

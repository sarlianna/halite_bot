"""A garbage bot by a garbage person."""
# TODO:
# FOLLOWING TWO PROBLEMS:
#   - wastefully combines past strength cap
#   - singular target mentality becomes useless with large amounts of territory.
#     lots of pieces in the middle are running around to different places, but pieces on the edges are already strong enough to take the target.
# SOLUTION:
#   - assign pieces to groups. Groups have a specific target.
#   - only enough total strength to barely take the target
#   - additional problems: avoiding collisions between groups. how?
#
# - seed 1907675159 against v.1 snapshot shows a huge weakness when fighthing enemies. (replay saved as bad_engage_loop)
#   - needs special case handling if target is owned by enemy / if it's strength 0 (should be basically the same)
#   - just needs to consider any nearby enemy's strength in addition.

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

from utils import (
    get_nearby_pieces,
    get_nearby_owned_pieces,
    get_weakest_site,
    get_total_strength,
    get_farthest_piece,
    get_closest_piece,
    sort_pieces_by_distance,
    find_allied_path,
    get_direction,
    find_unallied_edges,
    ACT_DIRECTIONS
)


logging.basicConfig(filename="garbage.log")
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def init():
    my_id, game_map = get_init()
    data = {"piece_locs": [], "target_locs": [], "targets": [], "edges": []}
    for y in range(game_map.height):
        for x in range(game_map.width):
            location = Location(x, y)
            site = game_map.getSite(location)
            if site.owner == my_id:
                data["piece_locs"].append(location)

    nearby = get_nearby_owned_pieces(0, game_map, data["piece_locs"][0])
    data["edges"] = nearby
    data["targets"].append(get_weakest_site(nearby))
    data["target_locs"].append(data["targets"][0][0])

    send_init("worthless garbage NEET")
    return my_id, game_map, data



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
                    log.debug("\tREMOVING LOC from piece_locs: {} ({})".format(loc, site))
                    log.debug("\t\treason: owner has changed")
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

        def update_targets():
            for loc in data["target_locs"]:
                target = game_map.getSite(loc)
                adjacent_allied = [p for p in get_nearby_pieces(game_map, loc) if p[1].owner == my_id]

                if target.owner != my_id and adjacent_allied:
                    data["targets"].append((loc, target))

        update_pieces()
        update_edges()
        update_targets()

        return data

    def generate_moves(my_id, game_map, data):
        moves = []

        def find_targets(my_id, game_map, data):
            """Updates data["targets"], data["target_locs"], and returns lists of pieces assigned to targets."""
            assigned_pieces = []
            remaining_pieces = data["pieces"]

            def assign_pieces_to_target(remaining_pieces, target):
                assigned_pieces = []
                closest_remaining = sort_pieces_by_distance(game_map, remaining_pieces, target[0])
                strength = 0
                index = 0
                for i in range(len(closest_remaining)):
                    strength += closest_remaining[i][1].strength
                    if strength > target[1].strength or i == len(closest_remaining) - 1:
                        index = i
                        break
                assigned_pieces.append((target, closest_remaining[:index]))
                remaining_pieces = closest_remaining[index:]
                return assigned_pieces

            if not data["targets"]:
                new_target = get_weakest_site(data["edges"])
                data["targets"].append(new_target)
                data["target_locs"].append(new_target[0])

            for target in data["targets"]:
                log.debug("remaining_pieces {}".format(remaining_pieces))
                if not remaining_pieces:
                    break
                assigned = assign_pieces_to_target(remaining_pieces, target)
                assigned_pieces.append(assigned)
                log.debug(assigned)
                for p in assigned[1]:
                    remaining_pieces.remove(p)

            # if there's still pieces, add new targets.
            log.debug("remaining_pieces {}".format(remaining_pieces))
            while remaining_pieces:
                possible_targets = find_unallied_edges(game_map, my_id, remaining_pieces)
                new_target = get_weakest_site(possible_targets)
                data["targets"].append(new_target)
                data["target_locs"].append(new_target[0])
                ap, remaining_pieces = assign_pieces_to_target(remaining_pieces, target)
                assigned_pieces.append(ap)
                log.debug("remaining_pieces {}".format(remaining_pieces))

            return assigned_pieces

        def _update_attacked_target(target):
            data["target_locs"].remove(target[0])
            data["piece_locs"].append(target[0])

        def attack_target_with_pieces(my_id, game_map, pieces, target):
            adjacent_allied = [p for p in get_nearby_pieces(game_map, target[0]) if p[1].owner == my_id]
            adjacent_loc = [p[0] for p in adjacent_allied]
            non_adjacent_allied = [p for p in pieces if p[0] not in adjacent_loc]

            if get_total_strength(adjacent_allied) > target[1].strength:
                for l, s in adjacent_allied:
                    moves.append(Move(l, get_direction(game_map, l, target[0])))
                    _update_attacked_target(target)

                if get_total_strength(non_adjacent_allied) < target[1].strength:
                    for l, s in non_adjacent_allied:
                        moves.append(Move(l, STILL))
                    return moves
            else:
                for l, s in adjacent_allied:
                    moves.append(Move(l, STILL))

            for l, s in non_adjacent_allied:
                # don't move 0-strength pieces, always a waste.
                if s.strength == 0:
                    moves.append(Move(l, STILL))
                    continue

                # back to target-seeking behavior
                nearest_adj = get_closest_piece(game_map, adjacent_allied, l)
                moves.append(Move(l, find_allied_path(game_map, my_id, l, nearest_adj[0])))

        def wait_with_pieces(pieces):
            log.debug("WAITED")
            for l, s in pieces:
                moves.append(Move(l, STILL))

        groups = find_targets(my_id, game_map, data)
        for target, pieces in groups:
            if get_total_strength(pieces) > target[1].strength:
                attack_target_with_pieces(my_id, game_map, pieces, target)
            else:
                wait_with_pieces(pieces)

        return moves

    data = get_updated_pieces(my_id, game_map, data)
    moves = generate_moves(my_id, game_map, data)
    log.debug("\n\ttarget:{}".format(target))
    log.debug("\n\tmoves:{}".format([(m.loc, m.direction) for m in moves]))
    send_frame(moves)

    return data


if __name__ == "__main__":
    log.debug("in main")
    try:
        mid, gmap, data = init()
        frame = 0
        while True:
            log.debug("frame:{}".format(frame))
            gmap = get_frame()
            data = take_turn(mid, gmap, data)
            log.debug("new data: {}".format(data))
            frame += 1
    except Exception as e:
        ex = traceback.format_exc()
        log.debug(ex)
        # this makes the game env stop.
        print("done fucked up.")
        print("done fucked up.")

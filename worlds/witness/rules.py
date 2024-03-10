"""
Defines the rules by which locations can be accessed,
depending on the items received
"""
from typing import TYPE_CHECKING, FrozenSet, Generator

from BaseClasses import CollectionState, Entrance
from .player_logic import WitnessPlayerLogic
from .locations import WitnessPlayerLocations
from . import StaticWitnessLogic, WitnessRegions
from worlds.generic.Rules import set_rule, CollectionRule

if TYPE_CHECKING:
    from . import WitnessWorld

laser_hexes = [
    "0x028A4",
    "0x00274",
    "0x032F9",
    "0x01539",
    "0x181B3",
    "0x0C2B2",
    "0x00509",
    "0x00BF6",
    "0x014BB",
    "0x012FB",
    "0x17C65",
]


def _has_laser(laser_hex: str, world: "WitnessWorld", player: int,
               redirect_required: bool) -> CollectionRule:
    if laser_hex == "0x012FB" and redirect_required:
        return lambda state: (
            _can_solve_panel(laser_hex, world, world.player, world.player_logic, world.locat)(state)
            and state.has("Desert Laser Redirection", player)
        )
    else:
        return _can_solve_panel(laser_hex, world, world.player, world.player_logic, world.locat)


def _has_lasers(amount: int, world: "WitnessWorld", redirect_required: bool) -> CollectionRule:
    laser_lambdas = []

    for laser_hex in laser_hexes:
        has_laser_lambda = _has_laser(laser_hex, world, world.player, redirect_required)

        laser_lambdas.append(has_laser_lambda)

    return lambda state: sum(laser_lambda(state) for laser_lambda in laser_lambdas) >= amount


def _can_solve_panel(panel: str, world: "WitnessWorld", player: int, player_logic: WitnessPlayerLogic,
                     locat: WitnessPlayerLocations) -> CollectionRule:
    """
    Determines whether a panel can be solved
    """

    panel_obj = player_logic.REFERENCE_LOGIC.ENTITIES_BY_HEX[panel]
    entity_name = panel_obj["checkName"]

    if entity_name + " Solved" in locat.EVENT_LOCATION_TABLE:
        return lambda state: state.has(player_logic.EVENT_ITEM_PAIRS[entity_name + " Solved"], player)
    else:
        return make_lambda(panel, world)


def _can_do_expert_pp2(state: CollectionState, world: "WitnessWorld") -> bool:
    """
    For Expert PP2, you need a way to access PP2 from the front, and a separate way from the back.
    This condition is quite complicated. We'll attempt to evaluate it as lazily as possible.
    """
    player = world.player
    regio = world.regio

    front_access = (
        any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Keep 2nd Pressure Plate", "Keep"])
        and state.can_reach("Keep", "Region", player)
    )

    # If we don't have front access, we can't do PP2.
    if not front_access:
        return False

    # Front access works. Now, we need to check for the many ways to access PP2 from the back.
    # All of those ways lead through the PP3 exit door from PP4. So we check this first.

    fourth_to_third = any(e.can_reach(state) for e in world.regio.two_way_entrance_register[
        "Keep 3rd Pressure Plate", "Keep 4th Pressure Plate"
    ])

    # If we can't get from PP4 to PP3, we can't do PP2.
    if not fourth_to_third:
        return False

    # We can go from PP4 to PP3. We now need to find a way to PP4.
    # The shadows shortcut is the simplest way.

    shadows_shortcut = (
        any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Pressure Plate", "Shadows"])
    )

    if shadows_shortcut:
        return True

    # We don't have the Shadows shortcut. This means we need to come in through the PP4 exit door instead.

    tower_to_pp4 = any(
        e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Pressure Plate", "Keep Tower"]
    )

    # If we don't have the PP4 exit door, we've run out of options.
    if not tower_to_pp4:
        return False

    # We have the PP4 exit door. If we can get to Keep Tower from behind, we can do PP2.
    # The simplest way would be the Tower Shortcut.

    tower_shortcut = any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep", "Keep Tower"])

    if tower_shortcut:
        return True

    # We don't have the Tower shortcut. At this point, there is one possibility remaining:
    # Getting to Keep Tower through the hedge mazes. This can be done in a multitude of ways.
    # No matter what, though, we would need Hedge Maze 4 Exit to Keep Tower.

    tower_access_from_hedges = any(
        e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Maze", "Keep Tower"]
    )

    if not tower_access_from_hedges:
        return False

    # We can reach Keep Tower from Hedge Maze 4. If we now have the Hedge 4 Shortcut, we are immediately good.

    hedge_4_shortcut = any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Maze", "Keep"])

    # If we have the hedge 4 shortcut, that works.
    if hedge_4_shortcut:
        return True

    # We don't have the hedge 4 shortcut. This means we would now need to come through Hedge Maze 3.

    hedge_3_to_4 = any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Maze", "Keep 3rd Maze"])

    if not hedge_3_to_4:
        return False

    # We can get to Hedge 4 from Hedge 3. If we have the Hedge 3 Shortcut, we're good.

    hedge_3_shortcut = any(
        e.can_reach(state) for e in regio.two_way_entrance_register["Keep 4th Maze", "Keep 3rd Maze"]
    )

    if hedge_3_shortcut:
        return True

    # We don't have Hedge 3 Shortcut. This means we would now need to come through Hedge Maze 2.

    hedge_2_to_3 = any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep 3rd Maze", "Keep 2nd Maze"])

    if not hedge_2_to_3:
        return False

    # We can get to Hedge 3 from Hedge 2. If we can get from Keep to Hedge 2, we're good.

    hedge_2_shortcut = any(e.can_reach(state) for e in regio.two_way_entrance_register["Keep 2nd Maze", "Keep"])

    return hedge_2_shortcut


def _can_do_theater_to_tunnels(state: CollectionState, world: "WitnessWorld") -> bool:
    # This evaluates the condition "direct_access or theater_from_town and tunnels_from_town" lazily using guards.

    direct_access = (
        any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Tunnels", "Windmill Interior"])
        and any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Theater", "Windmill Interior"])
    )

    if direct_access:
        return True

    theater_from_town = (
        any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Town", "Windmill Interior"])
        and any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Theater", "Windmill Interior"])
        or any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Town", "Theater"])
    )

    if not theater_from_town:
        return False

    tunnels_from_town = (
        any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Tunnels", "Windmill Interior"])
        and any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Town", "Windmill Interior"])
        or any(e.can_reach(state) for e in world.regio.two_way_entrance_register["Tunnels", "Town"])
    )

    return tunnels_from_town


def _has_item(item: str, world: "WitnessWorld", player: int,
              player_logic: WitnessPlayerLogic, locat: WitnessPlayerLocations) -> CollectionRule:
    if item in player_logic.REFERENCE_LOGIC.ALL_REGIONS_BY_NAME:
        region = world.get_region(item)
        return region.can_reach
    if item == "7 Lasers":
        laser_req = world.options.mountain_lasers.value
        return _has_lasers(laser_req, world, False)
    if item == "7 Lasers + Redirect":
        laser_req = world.options.mountain_lasers.value
        return _has_lasers(laser_req, world, True)
    if item == "11 Lasers":
        laser_req = world.options.challenge_lasers.value
        return _has_lasers(laser_req, world, False)
    if item == "11 Lasers + Redirect":
        laser_req = world.options.challenge_lasers.value
        return _has_lasers(laser_req, world, True)
    elif item == "PP2 Weirdness":
        return lambda state: _can_do_expert_pp2(state, world)
    elif item == "Theater to Tunnels":
        return lambda state: _can_do_theater_to_tunnels(state, world)
    if item in player_logic.USED_EVENT_NAMES_BY_HEX:
        return _can_solve_panel(item, world, player, player_logic, locat)

    prog_item = StaticWitnessLogic.get_parent_progressive_item(item)
    return lambda state: state.has(prog_item, player, player_logic.MULTI_AMOUNTS[item])


def _meets_item_requirements(requirements: FrozenSet[FrozenSet[str]],
                             world: "WitnessWorld") -> CollectionRule:
    """
    Checks whether item and panel requirements are met for
    a panel
    """

    lambda_conversion = [
        [_has_item(item, world, world.player, world.player_logic, world.locat) for item in subset]
        for subset in requirements
    ]

    return lambda state: any(
        all(condition(state) for condition in sub_requirement)
        for sub_requirement in lambda_conversion
    )


def make_lambda(entity_hex: str, world: "WitnessWorld") -> CollectionRule:
    """
    Lambdas are created in a for loop so values need to be captured
    """
    entity_req = world.player_logic.REQUIREMENTS_BY_HEX[entity_hex]

    return _meets_item_requirements(entity_req, world)


def set_rules(world: "WitnessWorld"):
    """
    Sets all rules for all locations
    """

    for location in world.locat.CHECK_LOCATION_TABLE:
        real_location = location

        if location in world.locat.EVENT_LOCATION_TABLE:
            real_location = location[:-7]

        associated_entity = world.player_logic.REFERENCE_LOGIC.ENTITIES_BY_NAME[real_location]
        entity_hex = associated_entity["entity_hex"]

        rule = make_lambda(entity_hex, world)

        location = world.multiworld.get_location(location, world.player)

        set_rule(location, rule)

    world.multiworld.completion_condition[world.player] = lambda state: state.has('Victory', world.player)

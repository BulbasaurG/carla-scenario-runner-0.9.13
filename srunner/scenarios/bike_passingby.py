#!/usr/bin/env python


from __future__ import print_function

import math
import py_trees
import carla

from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.scenarioatomics.atomic_behaviors import (ActorTransformSetter,
                                                                      ActorDestroy,
                                                                      AccelerateToVelocity,
                                                                      HandBrakeVehicle,
                                                                      KeepVelocity,
                                                                      StopVehicle)
from srunner.scenariomanager.scenarioatomics.atomic_criteria import CollisionTest
from srunner.scenariomanager.scenarioatomics.atomic_trigger_conditions import (InTriggerDistanceToLocationAlongRoute,
                                                                               InTimeToArrivalToVehicle,
                                                                               DriveDistance)
from srunner.scenariomanager.timer import TimeOut
from srunner.scenarios.basic_scenario import BasicScenario
from srunner.tools.scenario_helper import get_location_in_distance_from_wp


class PedestrianCrossing(BasicScenario):

    def __init__(self, world, ego_vehicles, config, randomize=False,
                 debug_mode=False, criteria_enable=True, adversary_type=False, timeout=60):
        """
        Setup all relevant parameters and create scenario
        """
        self._wmap = CarlaDataProvider.get_map()

        self._reference_waypoint = self._wmap.get_waypoint(config.trigger_points[0].location)
        # ego vehicle parameters
        self._ego_vehicle_distance_driven = 60
        # other vehicle parameters
        self._other_actor_target_velocity = 5
        self._other_actor_max_brake = 1.0
        self._time_to_reach = 10
        self._adversary_type = adversary_type  # flag to select either pedestrian (False) or cyclist (True)
        self._walker_yaw = 0
        self._num_lane_changes = 1
        self.transform = None
        self.transform2 = None
        self.timeout = timeout
        self._trigger_location = config.trigger_points[0].location
        # Total Number of attempts to relocate a vehicle before spawning
        self._number_of_attempts = 20
        # Number of attempts made so far
        self._spawn_attempted = 0
        self._pedestrian_start_distance = 40

        self._ego_route = CarlaDataProvider.get_ego_vehicle_route()

        super(PedestrianCrossing, self).__init__("PedestrianCrossing",
                                                 ego_vehicles,
                                                 config,
                                                 world,
                                                 debug_mode,
                                                 criteria_enable=criteria_enable)

    def _calculate_base_transform(self, _start_distance, waypoint):

        lane_width = waypoint.lane_width

        # Patches false junctions
        if self._reference_waypoint.is_junction:
            stop_at_junction = False
        else:
            stop_at_junction = True

        location, _ = get_location_in_distance_from_wp(waypoint, _start_distance, stop_at_junction)
        waypoint = self._wmap.get_waypoint(location)
        offset = {"orientation": 0, "position": 90, "z": 0.0, "k": 1.0}
        position_yaw = waypoint.transform.rotation.yaw + offset['position']
        orientation_yaw = waypoint.transform.rotation.yaw + offset['orientation']
        offset_location = carla.Location(
            offset['k'] * lane_width * math.cos(math.radians(position_yaw)), # TODO:x
            offset['k'] * (lane_width/2-1.5) * math.sin(math.radians(position_yaw))) # TODO: y
        location += offset_location
        location.z = self._trigger_location.z + offset['z']
        return carla.Transform(location, carla.Rotation(yaw=orientation_yaw)), orientation_yaw

    def _spawn_adversary(self, transform, orientation_yaw):

        self._time_to_reach *= self._num_lane_changes

        if self._adversary_type is False:
            self._walker_yaw = orientation_yaw
            self._other_actor_target_velocity = 3 + (0.4 * self._num_lane_changes)
            walker = CarlaDataProvider.request_new_actor('walker.*', transform)
            adversary = walker
        else:
            self._other_actor_target_velocity = self._other_actor_target_velocity * self._num_lane_changes
            first_vehicle = CarlaDataProvider.request_new_actor('vehicle.diamondback.century', transform)
            first_vehicle.set_simulate_physics(enabled=False)
            adversary = first_vehicle

        return adversary

    def _spawn_blocker(self, transform, orientation_yaw):
        """
        Spawn the blocker prop that blocks the vision from the egovehicle of the jaywalker
        :return:
        """
        # static object transform
        shift = 0.9
        x_ego = self._reference_waypoint.transform.location.x
        y_ego = self._reference_waypoint.transform.location.y
        x_cycle = transform.location.x
        y_cycle = transform.location.y
        x_static = x_ego + shift * (x_cycle - x_ego)
        y_static = y_ego + shift * (y_cycle - y_ego)

        spawn_point_wp = self.ego_vehicles[0].get_world().get_map().get_waypoint(transform.location)

        self.transform2 = carla.Transform(carla.Location(x_static, y_static,
                                                         spawn_point_wp.transform.location.z + 0.3),
                                          carla.Rotation(yaw=orientation_yaw + 180))

        static = CarlaDataProvider.request_new_actor('static.prop.vendingmachine', self.transform2)
        static.set_simulate_physics(enabled=False)

        return static

    def _initialize_actors(self, config):
        """
        Custom initialization
        """
        # cyclist transform
        _start_distance = self._pedestrian_start_distance
        # We start by getting and waypoint in the closest sidewalk.
        waypoint = self._reference_waypoint
        while True:
            wp_next = waypoint.get_right_lane()
            self._num_lane_changes += 1
            if wp_next is None or wp_next.lane_type == carla.LaneType.Biking: #TODO: Check if this is the correct lane type
                break
            elif wp_next.lane_type == carla.LaneType.Shoulder:
                # Filter Parkings considered as Shoulders
                if wp_next.lane_width > 2:
                    _start_distance += 1.5
                    waypoint = wp_next
                break
            else:
                _start_distance += 1.5
                waypoint = wp_next

        while True:  # We keep trying to spawn avoiding props

            try:
                self.transform, orientation_yaw = self._calculate_base_transform(_start_distance, waypoint)
                first_vehicle = self._spawn_adversary(self.transform, orientation_yaw)

                # blocker = self._spawn_blocker(self.transform, orientation_yaw)

                break
            except RuntimeError as r:
                # We keep retrying until we spawn
                print("Base transform is blocking objects ", self.transform)
                _start_distance += 0.4
                self._spawn_attempted += 1
                if self._spawn_attempted >= self._number_of_attempts:
                    raise r

        # Now that we found a possible position we just put the vehicle to the underground
        disp_transform = carla.Transform(
            carla.Location(self.transform.location.x,
                           self.transform.location.y,
                           self.transform.location.z - 500),
            self.transform.rotation)

        # prop_disp_transform = carla.Transform(
        #     carla.Location(self.transform2.location.x,
        #                    self.transform2.location.y,
        #                    self.transform2.location.z - 500),
        #     self.transform2.rotation)

        first_vehicle.set_transform(disp_transform)
        # blocker.set_transform(prop_disp_transform)
        first_vehicle.set_simulate_physics(enabled=False)
        # blocker.set_simulate_physics(enabled=False)
        self.other_actors.append(first_vehicle)
        # self.other_actors.append(blocker)

    def _create_behavior(self):

        root = py_trees.composites.Parallel(
            policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE, name="OccludedObjectCrossing")
        lane_width = self._reference_waypoint.lane_width
        lane_width = lane_width + (1.25 * lane_width * self._num_lane_changes)

        dist_to_trigger = self._pedestrian_start_distance / 2 + self._num_lane_changes
        # leaf nodes
        if self._ego_route is not None:
            start_condition = InTriggerDistanceToLocationAlongRoute(self.ego_vehicles[0],
                                                                    self._ego_route,
                                                                    self.transform.location,
                                                                    dist_to_trigger)
        else:
            start_condition = InTimeToArrivalToVehicle(self.ego_vehicles[0],
                                                       self.other_actors[0],
                                                       self._time_to_reach)

        actor_velocity = KeepVelocity(self.other_actors[0],
                                      self._other_actor_target_velocity,
                                      name="walker velocity")
        actor_drive = DriveDistance(self.other_actors[0],
                                    0.5 * lane_width,
                                    name="walker drive distance")
        actor_start_cross_lane = AccelerateToVelocity(self.other_actors[0],
                                                      1.0,
                                                      self._other_actor_target_velocity,
                                                      name="walker crossing lane accelerate velocity")
        actor_cross_lane = DriveDistance(self.other_actors[0],
                                         lane_width,
                                         name="walker drive distance for lane crossing ")
        actor_stop_crossed_lane = StopVehicle(self.other_actors[0],
                                              self._other_actor_max_brake,
                                              name="walker stop")
        ego_pass_machine = DriveDistance(self.ego_vehicles[0],
                                         5,
                                         name="ego vehicle passed prop")
        actor_remove = ActorDestroy(self.other_actors[0],
                                    name="Destroying walker")
        # static_remove = ActorDestroy(self.other_actors[1],
        #                              name="Destroying Prop")
        end_condition = DriveDistance(self.ego_vehicles[0],
                                      self._ego_vehicle_distance_driven,
                                      name="End condition ego drive distance")

        # non leaf nodes

        scenario_sequence = py_trees.composites.Sequence()
        keep_velocity_other = py_trees.composites.Parallel(
            policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE, name="keep velocity other")
        keep_velocity = py_trees.composites.Parallel(
            policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE, name="keep velocity")

        # building tree

        root.add_child(scenario_sequence)
        scenario_sequence.add_child(ActorTransformSetter(self.other_actors[0], self.transform,
                                                         name='TransformSetterTS3walker'))
        # scenario_sequence.add_child(ActorTransformSetter(self.other_actors[1], self.transform2,
        #                                                  name='TransformSetterTS3coca', physics=False))
        scenario_sequence.add_child(HandBrakeVehicle(self.other_actors[0], True))
        scenario_sequence.add_child(start_condition)
        scenario_sequence.add_child(HandBrakeVehicle(self.other_actors[0], False))
        scenario_sequence.add_child(keep_velocity)
        scenario_sequence.add_child(keep_velocity_other)
        # scenario_sequence.add_child(actor_stop_crossed_lane)
        # scenario_sequence.add_child(actor_remove)
        # scenario_sequence.add_child(static_remove)
        scenario_sequence.add_child(end_condition)

        keep_velocity.add_child(actor_velocity)
        keep_velocity.add_child(actor_drive)
        keep_velocity_other.add_child(actor_start_cross_lane)
        keep_velocity_other.add_child(actor_cross_lane)
        keep_velocity_other.add_child(ego_pass_machine)

        return root

    def _create_test_criteria(self):
        """
        A list of all test criteria will be created that is later used
        in parallel behavior tree.
        """
        criteria = []

        collision_criterion = CollisionTest(self.ego_vehicles[0])
        criteria.append(collision_criterion)

        return criteria

    def __del__(self):
        """
        Remove all actors upon deletion
        """
        self.remove_all_actors()
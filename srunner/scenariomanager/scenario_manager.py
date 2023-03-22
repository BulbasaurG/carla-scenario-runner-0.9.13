#!/usr/bin/env python

# Copyright (c) 2018-2020 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
This module provides the ScenarioManager implementation.
It must not be modified and is for reference only!
"""

from __future__ import print_function
import sys
import time

import py_trees

from srunner.autoagents.agent_wrapper import AgentWrapper
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.result_writer import ResultOutputProvider
from srunner.scenariomanager.timer import GameTime
from srunner.scenariomanager.watchdog import Watchdog
import numpy as np
import os
import pickle
import matplotlib.pyplot as plt

class ScenarioManager(object):
    """
    Basic scenario manager class. This class holds all functionality
    required to start, and analyze a scenario.

    The user must not modify this class.

    To use the ScenarioManager:
    1. Create an object via manager = ScenarioManager()
    2. Load a scenario via manager.load_scenario()
    3. Trigger the execution of the scenario manager.run_scenario()
       This function is designed to explicitly control start and end of
       the scenario execution
    4. Trigger a result evaluation with manager.analyze_scenario()
    5. If needed, cleanup with manager.stop_scenario()
    """

    def __init__(self, debug_mode=False, sync_mode=False, timeout=2.0):
        """
        Setups up the parameters, which will be filled at load_scenario()

        """
        self.scenario = None
        self.scenario_tree = None
        self.scenario_class = None
        self.ego_vehicles = None
        self.other_actors = None

        self._debug_mode = debug_mode
        self._agent = None
        self._sync_mode = sync_mode
        self._watchdog = None
        self._timeout = timeout

        self._running = False
        self._timestamp_last_run = 0.0
        self.scenario_duration_system = 0.0
        self.scenario_duration_game = 0.0
        self.start_system_time = None
        self.end_system_time = None

        # align carla lane type with waymo lane type
        self.lane_type = {
            'Driving':2, # surface street
            'Biking':3, # bike lane
            'Crosswalk':18, # crosswalk
        }

    def _reset(self):
        """
        Reset all parameters
        """
        self._running = False
        self._timestamp_last_run = 0.0
        self.scenario_duration_system = 0.0
        self.scenario_duration_game = 0.0
        self.start_system_time = None
        self.end_system_time = None
        GameTime.restart()

    def cleanup(self):
        """
        This function triggers a proper termination of a scenario
        """

        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog = None

        if self.scenario is not None:
            self.scenario.terminate()

        if self._agent is not None:
            self._agent.cleanup()
            self._agent = None

        CarlaDataProvider.cleanup()

    def load_scenario(self, scenario, agent=None):
        """
        Load a new scenario
        """
        self._reset()
        self._agent = AgentWrapper(agent) if agent else None
        if self._agent is not None:
            self._sync_mode = True
        self.scenario_class = scenario
        self.scenario = scenario.scenario
        self.scenario_tree = self.scenario.scenario_tree
        self.ego_vehicles = scenario.ego_vehicles
        self.other_actors = scenario.other_actors

        # To print the scenario tree uncomment the next line
        # py_trees.display.render_dot_tree(self.scenario_tree)

        if self._agent is not None:
            self._agent.setup_sensors(self.ego_vehicles[0], self._debug_mode)

    def _get_actor_type(self, type_id):
        # Unset = 0, Vehicle = 1, Pedestrian = 2, Cyclist = 3, Other = 4
        if "vehicle.diamondback.century" in type_id: # bicycle
            return 3
        if "vehicle" in type_id:
            return 1
        if "pedestrian" in type_id:
            return 2
        return 0

    def _save_to_waymo(self, recordWaymo, config, data_id:str):
        # toDo: round to cm or mm
        actor_state_keys = CarlaDataProvider._actor_state_keys
        actor_history = CarlaDataProvider._actor_history
        actor_type_map = CarlaDataProvider._actor_id_type_map
        result = {
            "scenario/id": np.array([config.name]),
        }

        NUM_AGENTS = 128
        NUM_RG_POINTS = 20000
        INIT_VALUE = -1.0
        INIT_VALUE_VALID = 0.0
        RG_RESOLUTION = 1  # meters between rg points

        num_steps = CarlaDataProvider._num_steps
        actor_ids = np.full((NUM_AGENTS,), INIT_VALUE)
        actor_types = np.full((NUM_AGENTS,), INIT_VALUE)

        # Initialize
        for key in actor_state_keys:
            if key == "state/valid":
                result[key] = np.full((NUM_AGENTS, num_steps), INIT_VALUE_VALID)
            else:
                result[key] = np.full((NUM_AGENTS, num_steps), INIT_VALUE)

        for i, (actor_id, history) in enumerate(actor_history.items()):
            actor_ids[i] = actor_id
            actor_types[i] = self._get_actor_type(actor_type_map[actor_id])
            # with open("test.txt", "a") as f:
            #     f.write(f"Start\n")
            for key in actor_state_keys:
                # with open("test.txt", "a") as f:
                #     if len(result[key][i]) != len(history[key]):
                #         f.write(f"actor_id:{actor_id}\nactor_type:{actor_type_map[actor_id]}\n \
                #                 key:{key}\nlen(history):{len(history[key])}\nlen(result):{len(result[key][i])}\ntime_step:{num_steps}.\n")
                result[key][i] = history[key]
            # with open("test.txt", "a") as f:
            #     f.write(f"End\n")

        rg_xyz = np.full((NUM_RG_POINTS, 3), INIT_VALUE)
        rg_dir = np.full((NUM_RG_POINTS, 3), INIT_VALUE)
        rg_type = np.full((NUM_RG_POINTS, 1), INIT_VALUE, dtype=np.int32)
        rg_valid = np.full((NUM_RG_POINTS, 1), INIT_VALUE_VALID, dtype=np.int32)
        rg_id = np.full((NUM_RG_POINTS, 1), INIT_VALUE, dtype=np.int32)
        # roadgraph things
        waypoints = CarlaDataProvider._map.generate_waypoints(RG_RESOLUTION)
        crosswalks = CarlaDataProvider._map.get_crosswalks()

        for i, wp in enumerate(waypoints):
            rg_xyz[i,:] = np.array([wp.transform.location.x, -wp.transform.location.y, wp.transform.location.z])
            forward_vec = wp.transform.rotation.get_forward_vector()
            rg_dir[i,:] = np.array([forward_vec.x, -forward_vec.y, forward_vec.z])
            rg_type[i] = self.lane_type[wp.lane_type.name]  # ToDo
            rg_valid[i] = [1]
            rg_id[i] = wp.lane_id # ToDos
        rg_id = np.array(rg_id, dtype=np.int32)
        rg_type = np.array(rg_type, dtype=np.int32)
        rg_valid = np.array(rg_valid, dtype=np.int32)
        lg_wp = len(waypoints)

        def generate_cw_id(id):
            while id in rg_id:
                id+=1
            return id
        first_cw = crosswalks[0]
        flag=1
        for i, cw in enumerate(crosswalks):
            rg_xyz[i+lg_wp+1,:] = np.array([[cw.x, -cw.y, cw.z]])
            rg_dir[i+lg_wp+1,:] = np.array([[1, 1, 1]])  # dummy value
            rg_type[i+lg_wp+1] = self.lane_type['Crosswalk']
            rg_valid[i+lg_wp+1] = [1]
            if i==0:
                cw_id = generate_cw_id(i)
            elif first_cw.distance(cw)==0:
                flag=0
            elif not flag:
                flag=1
                cw_id = generate_cw_id(i)
                first_cw = cw
            rg_id[i+lg_wp+1] = cw_id

        result["roadgraph_samples/xyz"] = rg_xyz
        result["roadgraph_samples/dir"] = rg_dir
        result["roadgraph_samples/type"] = rg_type
        result["roadgraph_samples/valid"] = rg_valid
        result["roadgraph_samples/id"] = rg_id

        result["state/id"] = actor_ids
        result["state/type"] = actor_types

        filename = config.name.split("_")[0]+"-"+data_id+"-of-00010"
        filepath = "{}/{}/{}.pkl".format(os.getenv('SCENARIO_RUNNER_ROOT', "./"), recordWaymo, filename)
        self._save_plot(result, filename, recordWaymo)

        with open(filepath, "wb") as f:
            pickle.dump(result, f)
        print("Saved data to ", filepath)
    
    def _save_plot(self, data, figname, recordWaymo):
        # save a simple plot to see whether the actor is moving
        figpath = "{}/{}/{}.jpg".format(os.getenv('SCENARIO_RUNNER_ROOT', "./"), recordWaymo, figname)
        car_ind = np.where(data['state/type']==1)[0]
        ped_ind = np.where(data['state/type']==2)[0]
        cyc_ind = np.where(data['state/type']==3)[0]
        for i, car in enumerate(car_ind):
            plt.plot(data["state/x"][car].squeeze(),data["state/y"][car].squeeze(),label=f"car_{i}")
        for i, ped in enumerate(ped_ind):
            plt.plot(data["state/x"][ped].squeeze(),data["state/y"][ped].squeeze(),label=f"ped_{i}")
        for i, cyc in enumerate(cyc_ind):
            plt.plot(data["state/x"][cyc].squeeze(),data["state/y"][cyc].squeeze(),label=f"cyc_{i}")
        plt.legend()
        plt.savefig(figpath)
        print("Saved plot to ", figpath)

    def run_scenario(self, recordWaymo, config, data_id: str):
        """
        Trigger the start of the scenario and wait for it to finish/fail
        """
        print("ScenarioManager: Running scenario {}".format(self.scenario_tree.name))
        self.start_system_time = time.time()
        start_game_time = GameTime.get_time()

        self._watchdog = Watchdog(float(self._timeout))
        self._watchdog.start()
        self._running = True

        while self._running:
            timestamp = None
            world = CarlaDataProvider.get_world()
            if world:
                snapshot = world.get_snapshot()
                if snapshot:
                    timestamp = snapshot.timestamp
            if timestamp:
                self._tick_scenario(timestamp)

        # Save data to waymo format
        if recordWaymo:
            self._save_to_waymo(recordWaymo, config, data_id)
        self.cleanup()

        self.end_system_time = time.time()
        end_game_time = GameTime.get_time()

        self.scenario_duration_system = self.end_system_time - \
                                        self.start_system_time
        self.scenario_duration_game = end_game_time - start_game_time

        if self.scenario_tree.status == py_trees.common.Status.FAILURE:
            print("ScenarioManager: Terminated due to failure")

    def _tick_scenario(self, timestamp):
        """
        Run next tick of scenario and the agent.
        If running synchornously, it also handles the ticking of the world.
        """

        if self._timestamp_last_run < timestamp.elapsed_seconds and self._running:
            self._timestamp_last_run = timestamp.elapsed_seconds

            self._watchdog.update()

            if self._debug_mode:
                print("\n--------- Tick ---------\n")

            # Update game time and actor information
            GameTime.on_carla_tick(timestamp)
            CarlaDataProvider.on_carla_tick()

            if self._agent is not None:
                ego_action = self._agent()  # pylint: disable=not-callable

            if self._agent is not None:
                self.ego_vehicles[0].apply_control(ego_action)

            # Tick scenario
            self.scenario_tree.tick_once()

            if self._debug_mode:
                print("\n")
                py_trees.display.print_ascii_tree(self.scenario_tree, show_status=True)
                sys.stdout.flush()

            if self.scenario_tree.status != py_trees.common.Status.RUNNING:
                self._running = False

        if self._sync_mode and self._running and self._watchdog.get_status():
            CarlaDataProvider.get_world().tick()

    def get_running_status(self):
        """
        returns:
           bool:  False if watchdog exception occured, True otherwise
        """
        return self._watchdog.get_status()

    def stop_scenario(self):
        """
        This function is used by the overall signal handler to terminate the scenario execution
        """
        self._running = False

    def analyze_scenario(self, stdout, filename, junit, json):
        """
        This function is intended to be called from outside and provide
        the final statistics about the scenario (human-readable, in form of a junit
        report, etc.)
        """

        failure = False
        timeout = False
        result = "SUCCESS"

        if self.scenario.test_criteria is None:
            print("Nothing to analyze, this scenario has no criteria")
            return True

        for criterion in self.scenario.get_criteria():
            if (not criterion.optional and
                    criterion.test_status != "SUCCESS" and
                    criterion.test_status != "ACCEPTABLE"):
                failure = True
                result = "FAILURE"
            elif criterion.test_status == "ACCEPTABLE":
                result = "ACCEPTABLE"

        if self.scenario.timeout_node.timeout and not failure:
            timeout = True
            result = "TIMEOUT"

        output = ResultOutputProvider(self, result, stdout, filename, junit, json)
        output.write()

        return failure or timeout

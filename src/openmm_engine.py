# src/openmm_engine.py
# Contains the OpenMMEngine for wrapping OpenMM functionalities

import asyncio
import io # Moved import io to the top
from typing import Dict, Any, Optional, Callable
import logging # Added for logging
from src.utils.logging_config import get_logger # Added for logging

# Attempt to import OpenMM and its unit system
try:
    import openmm as mm
    import openmm.app as app
    import openmm.unit as unit
    OPENMM_AVAILABLE = True
except ImportError:
    OPENMM_AVAILABLE = False
    # Mock objects for type hinting and basic structure if OpenMM is not installed
    # This allows the rest of the code to be parsable.
    # print("Warning: OpenMM not found. OpenMMEngine will use mock objects.") # Replaced by logger
    # Initial log before logger is fully set up in __init__
    logging.getLogger(__name__).warning("OpenMM not found during import. OpenMMEngine will use mock objects if instantiated.")
    class MockSystem: pass
    class MockSimulation:
        def __init__(self, topology, system, integrator, platform=None): pass
        def minimizeEnergy(self, tolerance=None, maxIterations=0): pass
        def step(self, steps: int): pass
        class MockContext:
            def getState(self, getPositions=False, getVelocities=False, getForces=False, getEnergy=False, getParameters=False, enforcePeriodicBox=False):
                class MockState:
                    def getPotentialEnergy(self): return 0.0 * unit.kilojoules_per_mole
                    def getKineticEnergy(self): return 0.0 * unit.kilojoules_per_mole
                    def getPositions(self, asNumpy=False): return []
                    def getVelocities(self, asNumpy=False): return []
                    def getForces(self, asNumpy=False): return []
                return MockState()
            def setPositions(self, positions): pass
            def setVelocitiesToTemperature(self, temperature, randomSeed=None): pass
        context = MockContext()
        reporters = []
    class MockPDBFile:
        def __init__(self, file_path_or_content): self.topology = None; self.positions = None
    class MockForceField:
        def __init__(self, *forcefield_files): pass
        def createSystem(self, topology, nonbondedMethod=None, nonbondedCutoff=None, constraints=None, rigidWater=True, removeCMMotion=True, hydrogenMass=None, switchDistance=None): return MockSystem()
    class MockLangevinMiddleIntegrator:
        def __init__(self, temperature, frictionCoeff, stepSize): pass
    class MockPlatform:
        @staticmethod
        def getPlatformByName(name: str): return MockPlatform()
    class MockDCDReporter:
        def __init__(self, file, reportInterval): pass
    class MockStateDataReporter:
        def __init__(self, file, reportInterval, **kwargs): pass

    # Reassign to mocks if OpenMM is not available
    mm = locals().get('mm', object()) # type: ignore
    app = locals().get('app', object()) # type: ignore
    unit = locals().get('unit', object()) # type: ignore
    if not OPENMM_AVAILABLE:
        app.PDBFile = MockPDBFile # type: ignore
        app.ForceField = MockForceField # type: ignore
        mm.LangevinMiddleIntegrator = MockLangevinMiddleIntegrator # type: ignore
        mm.Platform = MockPlatform # type: ignore
        app.DCDReporter = MockDCDReporter # type: ignore
        app.StateDataReporter = MockStateDataReporter # type: ignore
        mm.System = MockSystem # type: ignore
        mm.Simulation = MockSimulation # type: ignore


class OpenMMEngine:
    """
    Wraps OpenMM functionalities for setting up and running simulations.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        if not OPENMM_AVAILABLE:
            self.logger.critical("OpenMM Python libraries are not installed. This engine will not function correctly.")
            # raise ImportError("OpenMM libraries are required for OpenMMEngine.")
        else:
            self.logger.info("OpenMMEngine initialized with OpenMM available.")

    async def setup_system(
        self,
        pdb_file_content: Optional[str] = None,
        pdb_file_path: Optional[str] = None,
        forcefield_files: list[str] = ["amber14-all.xml", "amber14/tip3pfb.xml"],
        nonbonded_method_str: str = "PME",
        nonbonded_cutoff_nm: float = 1.0,
        constraints_str: str = "HBonds",
        rigid_water: bool = True,
        remove_cm_motion: bool = True,
        # **kwargs: Any # For other system parameters
    ) -> tuple[Any, Any]: # Returns topology, system
        """
        Sets up the OpenMM system from PDB and force field.
        Returns a tuple of (topology, system).
        """
        if not OPENMM_AVAILABLE: return (None, MockSystem())

        if not pdb_file_content and not pdb_file_path:
            raise ValueError("Either pdb_file_content or pdb_file_path must be provided.")

        # pdb_source will be either the file path or the string content.
        # app.PDBFile can handle a file-like object (from io.StringIO for content)
        # or a file path.
        pdb_source = pdb_file_path if pdb_file_path else pdb_file_content

        def load_pdb():
            if isinstance(pdb_source, str) and ("\n" in pdb_source or pdb_source.endswith(".pdb")): # Basic check
                 if not pdb_file_path: # if content was given
                    return app.PDBFile(io.StringIO(pdb_source))
                 else: # if path was given
                    return app.PDBFile(pdb_source) # type: ignore
            else:
                raise ValueError("Invalid PDB source provided.")
        
        pdb_obj = await asyncio.to_thread(load_pdb)

        def load_forcefield():
            return app.ForceField(*forcefield_files)
        
        forcefield = await asyncio.to_thread(load_forcefield)

        # Map string representations to OpenMM app objects
        nonbonded_method_map = {
            "NoCutoff": app.NoCutoff,
            "CutoffNonPeriodic": app.CutoffNonPeriodic,
            "CutoffPeriodic": app.CutoffPeriodic,
            "Ewald": app.Ewald,
            "PME": app.PME,
        }
        constraints_map = {
            "None": None, # Or app.HBonds if None means no constraints explicitly
            "HBonds": app.HBonds,
            "AllBonds": app.AllBonds,
            "HAngles": app.HAngles,
        }

        def create_system_sync():
            return forcefield.createSystem(
                pdb_obj.topology,
                nonbondedMethod=nonbonded_method_map.get(nonbonded_method_str, app.PME),
                nonbondedCutoff=nonbonded_cutoff_nm * unit.nanometers,
                constraints=constraints_map.get(constraints_str, app.HBonds),
                rigidWater=rigid_water,
                removeCMMotion=remove_cm_motion
            )

        system = await asyncio.to_thread(create_system_sync)
        self.logger.info("OpenMM System created.")
        return pdb_obj.topology, pdb_obj.positions, system # Return topology, positions, and system

    async def create_simulation(
        self,
        topology: Any, # mm.app.Topology
        system: Any,   # mm.System
        integrator_config: Dict[str, Any],
        platform_name: Optional[str] = None,
        platform_properties: Optional[Dict[str, str]] = None
    ) -> Any: # mm.Simulation
        """
        Creates an OpenMM Simulation object.
        integrator_config: e.g., {"type": "LangevinMiddle", "temperature_K": 300, "friction_coeff_ps": 1.0, "step_size_ps": 0.002}
        """
        if not OPENMM_AVAILABLE: return MockSimulation(None, None, None)

        integrator_type = integrator_config.get("type", "LangevinMiddle")

        def create_integrator_sync():
            if integrator_type == "LangevinMiddle":
                return mm.LangevinMiddleIntegrator(
                    integrator_config.get("temperature_K", 300) * unit.kelvin,
                    integrator_config.get("friction_coeff_ps", 1.0) / unit.picosecond,
                    integrator_config.get("step_size_ps", 0.002) * unit.picoseconds
                )
            elif integrator_type == "Verlet":
                return mm.VerletIntegrator(
                    integrator_config.get("step_size_ps", 0.002) * unit.picoseconds
                )
            elif integrator_type == "Brownian":
                return mm.BrownianIntegrator(
                    integrator_config.get("temperature_K", 300) * unit.kelvin,
                    integrator_config.get("friction_coeff_ps", 1.0) / unit.picosecond,
                    integrator_config.get("step_size_ps", 0.002) * unit.picoseconds
                )
            # Other integrators like NoseHooverIntegrator can be added here as needed.
            else:
                raise ValueError(f"Unsupported integrator type: {integrator_type}")
        
        integrator = await asyncio.to_thread(create_integrator_sync)

        def get_platform_sync():
            if platform_name:
                try:
                    platform_obj = mm.Platform.getPlatformByName(platform_name)
                    if platform_properties:
                        for key, value in platform_properties.items():
                            platform_obj.setPropertyDefaultValue(key, value)
                    return platform_obj
                except Exception as e:
                    self.logger.warning(f"Could not get platform '{platform_name}': {e}. Using default.")
            return None # Use default platform

        platform = await asyncio.to_thread(get_platform_sync)

        def create_simulation_obj_sync():
            return app.Simulation(topology, system, integrator, platform)

        simulation = await asyncio.to_thread(create_simulation_obj_sync)
        platform_in_use = simulation.context.getPlatform() # Get actual platform used
        self.logger.info(f"OpenMM Simulation created with integrator {integrator_type} on platform {platform_in_use.getName()}.")
        return simulation

    async def configure_reporters(self, simulation: Any, output_config: Optional[Dict[str, Any]] = None):
        """Configures and adds reporters to the simulation object."""
        if not OPENMM_AVAILABLE or output_config is None:
            return

        # Clear existing reporters if any, or decide on append/replace strategy
        simulation.reporters.clear()

        dcd_cfg = output_config.get("dcd_reporter")
        if dcd_cfg and dcd_cfg.get("file") and dcd_cfg.get("reportInterval"):
            try:
                simulation.reporters.append(
                    app.DCDReporter(dcd_cfg["file"], int(dcd_cfg["reportInterval"]))
                )
                self.logger.info(f"Added DCDReporter to {dcd_cfg['file']} every {dcd_cfg['reportInterval']} steps.")
            except Exception as e:
                self.logger.error(f"Failed to add DCDReporter for file {dcd_cfg.get('file')}: {e}", exc_info=True)

        xtc_cfg = output_config.get("xtc_reporter")
        if xtc_cfg and xtc_cfg.get("file") and xtc_cfg.get("reportInterval"):
            try:
                simulation.reporters.append(
                    app.XTCReporter(xtc_cfg["file"], int(xtc_cfg["reportInterval"]), append=xtc_cfg.get("append", False))
                )
                self.logger.info(f"Added XTCReporter to {xtc_cfg['file']} every {xtc_cfg['reportInterval']} steps.")
            except Exception as e:
                self.logger.error(f"Failed to add XTCReporter for file {xtc_cfg.get('file')}: {e}", exc_info=True)

        sdr_cfg = output_config.get("state_data_reporter")
        if sdr_cfg and sdr_cfg.get("reportInterval"):
            try:
                output_target_file = sdr_cfg.get("file", "stdout")
                output_stream_or_file: Any
                if output_target_file.lower() == "stdout":
                    import sys
                    output_stream_or_file = sys.stdout
                elif output_target_file.lower() == "stderr":
                    import sys
                    output_stream_or_file = sys.stderr
                else:
                    output_stream_or_file = output_target_file # Pass filename directly

                simulation.reporters.append(
                    app.StateDataReporter(
                        output_stream_or_file,
                        int(sdr_cfg["reportInterval"]),
                        step=sdr_cfg.get("step", True),
                        time=sdr_cfg.get("time", True),
                        potentialEnergy=sdr_cfg.get("potentialEnergy", True),
                        kineticEnergy=sdr_cfg.get("kineticEnergy", False),
                        totalEnergy=sdr_cfg.get("totalEnergy", False),
                        temperature=sdr_cfg.get("temperature", True),
                        volume=sdr_cfg.get("volume", False),
                        density=sdr_cfg.get("density", False),
                        progress=sdr_cfg.get("progress", True),
                        remainingTime=sdr_cfg.get("remainingTime", True),
                        speed=sdr_cfg.get("speed", True),
                        elapsedTime=sdr_cfg.get("elapsedTime", False),
                        separator=sdr_cfg.get("separator", "\t"),
                        systemMass=sdr_cfg.get("systemMass", None),
                        totalSteps=sdr_cfg.get("totalSteps", None)
                    )
                )
                self.logger.info(f"Added StateDataReporter to {output_target_file} every {sdr_cfg['reportInterval']} steps.")
            except Exception as e:
                self.logger.error(f"Failed to add StateDataReporter (target: {sdr_cfg.get('file', 'stdout')}): {e}", exc_info=True)

        checkpoint_cfg = output_config.get("checkpoint_reporter")
        if checkpoint_cfg and checkpoint_cfg.get("file") and checkpoint_cfg.get("reportInterval"):
            try:
                simulation.reporters.append(
                    app.CheckpointReporter(
                        checkpoint_cfg["file"],
                        int(checkpoint_cfg["reportInterval"]),
                        writeState=checkpoint_cfg.get("writeState", True)
                    )
                )
                self.logger.info(f"Added CheckpointReporter to {checkpoint_cfg['file']} every {checkpoint_cfg['reportInterval']} steps.")
            except Exception as e:
                self.logger.error(f"Failed to add CheckpointReporter for file {checkpoint_cfg.get('file')}: {e}", exc_info=True)
        # PDBReporter can be added here if PDB format trajectory output is required.

    async def minimize_energy(self, simulation: Any, tolerance_kj_mol_nm: Optional[float] = None, max_iterations: int = 0):
        """Performs energy minimization."""
        if not OPENMM_AVAILABLE: return
        self.logger.info("Minimizing energy...")

        def minimize_sync():
            if tolerance_kj_mol_nm is not None:
                simulation.minimizeEnergy(tolerance=tolerance_kj_mol_nm * unit.kilojoules_per_mole / unit.nanometer, maxIterations=max_iterations)
            else:
                simulation.minimizeEnergy(maxIterations=max_iterations) # Use OpenMM's default tolerance
        
        await asyncio.to_thread(minimize_sync)
        self.logger.info("Energy minimization complete.")

    async def run_simulation_steps(
        self,
        simulation: Any, # mm.Simulation
        steps: int
    ):
        """
        Runs the simulation for a given number of steps.
        Note: Progress reporting for fine-grained steps should be handled
        by TaskManager by calling this method in smaller chunks if needed,
        or via OpenMM reporters.
        """
        if not OPENMM_AVAILABLE: return
        self.logger.info(f"Running simulation for {steps} steps...")

        def step_sync():
            simulation.step(steps)
        
        await asyncio.to_thread(step_sync)
        
        # Note: simulation.currentStep is updated by the step call.
        # TaskManager can query this or maintain its own count if calling in chunks.
        current_sim_step_info = simulation.currentStep if OPENMM_AVAILABLE and hasattr(simulation, 'currentStep') else 'N/A'
        self.logger.info(f"Simulation run for {steps} steps complete. Current sim step: {current_sim_step_info}")


    async def get_current_state_info(self, simulation: Any, get_positions=True, get_energy=True, get_forces=False) -> Dict[str, Any]:
        """Gets current state information from the simulation."""
        if not OPENMM_AVAILABLE: return {}

        def get_state_sync():
            state = simulation.context.getState(
                getPositions=get_positions,
                getEnergy=get_energy,
                getForces=get_forces,
                # Consider adding getVelocities if needed by any use case
                # getVelocities=get_velocities
            )
            info_dict = {}
            if get_positions:
                # Ensure positions are serializable (e.g., list of lists)
                pos_numpy = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
                info_dict["positions"] = pos_numpy.tolist() if hasattr(pos_numpy, "tolist") else pos_numpy
            if get_energy:
                info_dict["potential_energy_kj_mol"] = state.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)
                info_dict["kinetic_energy_kj_mol"] = state.getKineticEnergy().value_in_unit(unit.kilojoules_per_mole)
            if get_forces:
                # Ensure forces are serializable
                forces_numpy = state.getForces(asNumpy=True).value_in_unit(unit.kilojoules_per_mole / unit.nanometer)
                info_dict["forces_kj_mol_nm"] = forces_numpy.tolist() if hasattr(forces_numpy, "tolist") else forces_numpy
            # if get_velocities:
            #     vel_numpy = state.getVelocities(asNumpy=True).value_in_unit(unit.nanometer/unit.picosecond)
            #     info_dict["velocities_nm_ps"] = vel_numpy.tolist() if hasattr(vel_numpy, "tolist") else vel_numpy
            return info_dict

        return await asyncio.to_thread(get_state_sync)

    async def save_checkpoint(self, simulation: Any, filename: str):
        """Saves the simulation state to a checkpoint file."""
        if not OPENMM_AVAILABLE: return
        
        def save_checkpoint_sync():
            simulation.saveCheckpoint(filename)
        
        await asyncio.to_thread(save_checkpoint_sync)
        self.logger.info(f"Simulation checkpoint saved to {filename}")

    async def load_checkpoint(self, simulation: Any, filename: str):
        """Loads the simulation state from a checkpoint file."""
        if not OPENMM_AVAILABLE: return

        def load_checkpoint_sync():
            simulation.loadCheckpoint(filename)

        await asyncio.to_thread(load_checkpoint_sync)
        self.logger.info(f"Simulation checkpoint loaded from {filename}")

    async def set_initial_positions(self, simulation: Any, positions: Any):
        """Sets the initial positions for the simulation."""
        if not OPENMM_AVAILABLE: return
        
        def set_positions_sync():
            simulation.context.setPositions(positions)

        await asyncio.to_thread(set_positions_sync)
        self.logger.info("Initial positions set for the simulation.")

    async def set_velocities_to_temperature(self, simulation: Any, temperature_kelvin: float):
        """Sets particle velocities to a given temperature."""
        if not OPENMM_AVAILABLE: return

        def set_velocities_sync():
            simulation.context.setVelocitiesToTemperature(temperature_kelvin * unit.kelvin)
        
        await asyncio.to_thread(set_velocities_sync)
        self.logger.info(f"Velocities set to {temperature_kelvin}K.")

    # async def export_trajectory(self, simulation_or_data: Any, format_type: str, filename: str):
    #     """Exports trajectory data. This might be handled by reporters directly."""
    #     # This is usually done via reporters (DCDReporter, XTCReporter, PDBReporter)
    #     # If direct export is needed from a set of frames, custom logic would be required.
    #     self.logger.info(f"Trajectory export to {format_type} at {filename} is typically handled by reporters.")
    #     pass

    async def cleanup_simulation(self, simulation: Any): # Added self
        """
        Performs cleanup for a simulation instance.
        Based on OpenMM documentation and common usage, standard reporters (DCDReporter,
        StateDataReporter, CheckpointReporter, etc.) manage their own file handles
        when initialized with filenames, and these are typically closed upon
        garbage collection of the reporter or simulation object.
        Explicitly closing internal file attributes (e.g., `_out`) is not
        recommended as it's an internal detail and can be fragile.
        This method is a placeholder if other specific cleanup actions are identified.
        """
        if not OPENMM_AVAILABLE:
            self.logger.debug("OpenMM not available, skipping simulation cleanup logic.")
            return

        self.logger.info(f"Initiating cleanup for OpenMM Simulation object of type: {type(simulation)}.")

        if hasattr(simulation, 'reporters'):
            self.logger.debug(f"Simulation has {len(simulation.reporters)} reporters.")
            # No explicit close needed for standard app.reporters as per research.
            # If custom reporters with explicit close() methods were used, they could be handled here.
            # for reporter in simulation.reporters:
            #     if hasattr(reporter, 'close') and callable(reporter.close):
            #         try:
            #             self.logger.debug(f"Calling close() on reporter: {type(reporter)}")
            #             reporter.close()
            #         except Exception as e:
            #             self.logger.error(f"Error closing reporter {type(reporter)}: {e}", exc_info=True)
            #     elif hasattr(reporter, '_out') and hasattr(reporter._out, 'close') and not reporter._out.closed:
            #         # This is discouraged as _out is an internal detail.
            #         try:
            #             self.logger.debug(f"Closing internal _out for reporter: {type(reporter)}")
            #             reporter._out.close()
            #         except Exception as e:
            #             self.logger.error(f"Error closing internal _out for reporter {type(reporter)}: {e}", exc_info=True)


        # The OpenMM Simulation object and its Context are managed by Python's garbage collector.
        # No explicit del simulation.context or similar is standard practice here.
        self.logger.info("Simulation cleanup: Standard OpenMM objects are managed by garbage collection. No explicit file closing for standard reporters is performed by this engine.")
        # If other resources were managed directly by this engine for a simulation, they would be cleaned here.
        pass

# Example usage (for testing this module directly)
async def _test_engine():
    # Setup basic logging for the test
    from src.utils.logging_config import setup_logging
    setup_logging()
    test_logger = get_logger(__name__ + "._test_engine")

    if not OPENMM_AVAILABLE:
        test_logger.warning("Skipping OpenMMEngine test as OpenMM is not available.")
        return

    engine = OpenMMEngine()
    # Create a dummy PDB file content for testing
    dummy_pdb_content = """
ATOM      1  N   ALA A   1       8.360  -0.600   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       7.000   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       6.000  -0.800   0.800  1.00  0.00           C
ATOM      4  O   ALA A   1       6.200  -1.900   1.200  1.00  0.00           O
ATOM      5  CB  ALA A   1       6.800   1.000  -1.000  1.00  0.00           C
ATOM      6  H   ALA A   1       8.900  -1.200   0.500  1.00  0.00           H
"""
    try:
        test_logger.info("Starting OpenMMEngine test sequence...")
        topology, positions, system = await engine.setup_system(pdb_file_content=dummy_pdb_content, forcefield_files=['amber14-all.xml']) # Use a minimal general FF

        integrator_cfg = {"type": "LangevinMiddle", "temperature_K": 300, "friction_coeff_ps": 1.0, "step_size_ps": 0.001}
        test_logger.info(f"Using integrator config: {integrator_cfg}")
        # Try with CPU platform first for broader compatibility in tests
        simulation = await engine.create_simulation(topology, system, integrator_cfg, platform_name="CPU")
        
        # Directly call engine's method for setting positions
        await engine.set_initial_positions(simulation, positions)

        output_cfg = {
            "dcd_reporter": {"file": "test_output.dcd", "reportInterval": 10},
            "state_data_reporter": {"file": "stdout", "reportInterval": 10, "step": True, "potentialEnergy": True, "temperature": True}
        }
        test_logger.info(f"Using output config: {output_cfg}")
        await engine.configure_reporters(simulation, output_cfg)

        await engine.minimize_energy(simulation, max_iterations=10)
        state_after_min = await engine.get_current_state_info(simulation)
        test_logger.info(f"State after minimization: {state_after_min}")

        await engine.run_simulation_steps(simulation, 100) # Run 100 steps
        state_after_run = await engine.get_current_state_info(simulation)
        test_logger.info(f"State after 100 steps: {state_after_run}")

        await engine.save_checkpoint(simulation, "test_checkpoint.chk")
        # Modify state or re-initialize to test loading
        # Directly call engine's method for setting velocities
        await engine.set_velocities_to_temperature(simulation, 100.0) # 100 Kelvin
        
        await engine.load_checkpoint(simulation, "test_checkpoint.chk")
        state_after_load = await engine.get_current_state_info(simulation) # Should be similar to after save
        test_logger.info(f"State after loading checkpoint: {state_after_load}")
        test_logger.info("OpenMMEngine test sequence completed.")

    except Exception as e:
        test_logger.error(f"Error during OpenMMEngine test: {e}", exc_info=True)
    finally:
        # Clean up test files
        test_logger.info("Cleaning up test files...")
        import os
        if os.path.exists("test_output.dcd"): os.remove("test_output.dcd")
        if os.path.exists("test_checkpoint.chk"): os.remove("test_checkpoint.chk")

if __name__ == "__main__":
    asyncio.run(_test_engine())
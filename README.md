# OpenMM MCP Server

[English](README.md) | [中文](README_CN.md)

---

### 🧬 OpenMM & Abacus MCP Server

A comprehensive Model Context Protocol (MCP) server for molecular dynamics simulations using OpenMM and DFT calculations with Abacus. This server provides a natural language interface for complex molecular simulations through LLM integration.

#### ✨ Features

- **Complete OpenMM Integration**: Support for all OpenMM features including advanced integrators, barostats, and constraints
- **DFT Calculations**: Abacus DFT engine integration for quantum mechanical calculations
- **Pre-configured Templates**: Ready-to-use setups for protein simulations, membrane systems, and more
- **Advanced Sampling**: Metadynamics, free energy calculations, and enhanced sampling methods
- **GPU Acceleration**: CUDA and OpenCL platform support for high-performance computing
- **Task Management**: Asynchronous task execution with persistence and monitoring
- **Natural Language Interface**: Interact with complex simulations using simple English commands

#### 🚀 Quick Start

##### Installation

```bash
# Clone the repository
git clone <repository_url>
cd openmm-mcp-server

# Install dependencies
pip install -r requirements.txt

# Optional: Install OpenMM for actual simulations
conda install -c conda-forge openmm

# Test installation
python test_mcp_server.py
```

##### Roo Code Integration

Add to your Roo Code MCP settings:

```json
{
  "mcpServers": {
    "openmm-server": {
      "command": "python",
      "args": ["run_openmm_server.py"],
      "cwd": "F:\\develop\\openmm-mcp-server",
      "alwaysAllow": [
        "create_md_simulation",
        "create_advanced_md_simulation",
        "setup_protein_simulation",
        "setup_membrane_simulation",
        "create_dft_calculation",
        "control_simulation",
        "get_task_status",
        "list_all_tasks",
        "analyze_results"
      ]
    }
  }
}
```

**Important**: Replace the path with your actual project path!

#### 🛠️ Available Tools

##### Basic Tools
- `create_md_simulation` - Create simple MD simulations
- `create_dft_calculation` - Create DFT calculations
- `control_simulation` - Control simulation execution (start/stop/pause)
- `get_task_status` - Check task status
- `list_all_tasks` - List all tasks
- `analyze_results` - Analyze simulation results

##### Advanced Tools
- `create_advanced_md_simulation` - Full OpenMM feature support (50+ parameters)
- `setup_protein_simulation` - Pre-configured protein simulation templates
- `setup_membrane_simulation` - Membrane protein simulation setup

#### 💬 Usage Examples

##### Simple Water Simulation
```
"Run a molecular dynamics simulation of a water molecule at 300K for 10000 steps"
```

##### Advanced Protein Simulation
```
"Set up a protein production simulation for 100 nanoseconds at physiological temperature 310K, using Amber19 force field with TIP3P-FB water model, 0.15M salt concentration, and GPU acceleration"
```

##### Membrane Protein Simulation
```
"Create a POPC membrane protein simulation for 50 nanoseconds with surface tension control"
```

#### 📊 OpenMM Parameters Reference

##### Integrators
- `LangevinMiddle` - Langevin middle integrator (recommended)
- `Verlet` - Verlet integrator (NVE ensemble)
- `Brownian` - Brownian dynamics
- `VariableLangevin` - Variable step size Langevin
- `VariableVerlet` - Variable step size Verlet
- `NoseHoover` - Nose-Hoover thermostat

##### Force Fields
- **Amber14**: `["amber14-all.xml", "amber14/tip3pfb.xml"]`
- **Amber19**: `["amber19-all.xml", "amber19/tip3pfb.xml"]`
- **CHARMM36**: `["charmm36_2024.xml", "charmm36/water.xml"]`

##### Water Models
- `tip3p` - TIP3P water model
- `tip3pfb` - TIP3P-FB water model (recommended)
- `tip4pew` - TIP4P-Ew water model
- `spce` - SPC/E water model

##### Platforms
- `CUDA` - NVIDIA GPU (fastest)
- `OpenCL` - General GPU
- `CPU` - CPU computation
- `Reference` - Reference implementation

##### Nonbonded Methods
- `PME` - Particle Mesh Ewald (recommended for periodic systems)
- `NoCutoff` - No cutoff (small systems)
- `CutoffNonPeriodic` - Non-periodic cutoff
- `CutoffPeriodic` - Periodic cutoff
- `Ewald` - Traditional Ewald summation

##### Constraints
- `None` - No constraints
- `HBonds` - Hydrogen bond constraints (recommended)
- `AllBonds` - All bond constraints
- `HAngles` - Hydrogen angle constraints

##### Barostats
- `MonteCarloBarostat` - Isotropic pressure control
- `MonteCarloAnisotropicBarostat` - Anisotropic pressure control
- `MonteCarloMembraneBarostat` - Membrane system pressure control

##### Precision
- `mixed` - Mixed precision (recommended)
- `single` - Single precision
- `double` - Double precision

#### 🔧 Configuration

Environment variables:
```bash
export TASK_DATA_DIR="./simulation_data"
export MAX_CONCURRENT_TASKS=4
export DEFAULT_OPENMM_PLATFORM="CUDA"
export LOG_LEVEL="INFO"
export LOG_FILE="./mcp_server.log"
```

#### 📁 Project Structure

```
openmm-mcp-server/
├── run_openmm_server.py      # Startup script
├── test_mcp_server.py        # Test script
├── requirements.txt          # Dependencies
├── README.md                 # English documentation
├── README_CN.md              # Chinese documentation
├── src/
│   ├── server_new.py         # Main server
│   ├── advanced_md_tools.py  # Advanced MD tools
│   ├── task_manager.py       # Task management
│   ├── openmm_engine.py      # OpenMM engine
│   ├── abacus_engine.py      # Abacus DFT engine
│   ├── config.py             # Configuration management
│   ├── tools/                # MCP tool implementations
│   ├── resources/            # MCP resource implementations
│   └── utils/                # Utility functions
├── tests/                    # Test files
├── examples/                 # Example code
├── docs/                     # Documentation
└── task_data/                # Task data directory (auto-created)
```

#### 📚 Additional Documentation

- [Installation Guide](INSTALL.md) - Detailed installation instructions
- [Usage Guide](USAGE_GUIDE.md) - Comprehensive usage examples
- [Roo Code Integration](ROO_CODE_INTEGRATION.md) - Detailed integration guide
- [OpenMM Parameters](OPENMM_PARAMETERS.md) - Complete parameter reference
- [Project Analysis](PROJECT_ANALYSIS.md) - Technical analysis and improvements

#### 🔍 Troubleshooting

##### Common Issues

1. **"OpenMM not found" warning**
   - This is normal, server will run in mock mode
   - For actual simulations, install OpenMM: `conda install -c conda-forge openmm`

2. **"command not found" error**
   - Check if Python is in PATH
   - Verify project path is correct
   - Try using absolute paths

3. **Permission errors**
   - Ensure read/write permissions for project directory
   - Check if task_data directory is writable

##### Verify Configuration

```bash
# Test server startup
python run_openmm_server.py

# Test MCP functionality
python test_mcp_server.py
```

#### 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

#### 🆘 Support

If you encounter any issues:
1. Run the test script: `python test_mcp_server.py`
2. Review the documentation
3. Check log files (if configured)
4. Submit an issue on GitHub

#### 📄 License

See LICENSE file for details.

---

Happy simulating! 🎉
# SimReady Foundation

## Portable annotation checks in the Palatial pin

Grasp segments may intersect a visible surface or lie inside a verified closed
mesh, as they can inside a primitive solid. Mesh bounds alone do not establish
containment: open shells, declared holes and nested cavity shells retain their
empty space. This annotation check does not qualify a physical robot grasp.
With OpenUSD and pytest installed, run `python -m pytest -q tests` for the portable
regressions; the geometry tests do not require Omniverse or asset downloads.

## Getting the repository

This repository uses **Git LFS** to track binary and USD asset files (`.usda`, `.usdc`, `.usd`, `.usdz`, images, and others). You must have Git LFS installed before cloning, otherwise those files will check out as tiny pointer files instead of the real content.

### 1. Install Git LFS (once per machine)

```bash
# macOS (Homebrew)
brew install git-lfs

# Ubuntu / Debian
sudo apt-get install git-lfs

# Windows (winget)
winget install GitHub.GitLFS
```

After installing, run the one-time setup:

```bash
git lfs install
```

### 2. Clone the repository

```bash
git clone https://github.com/NVIDIA/simready-foundation.git
cd simready-foundation
```

Git LFS files are fetched automatically during clone when `git lfs install` has been run. If you already cloned without LFS, pull the real file contents with:

```bash
git lfs pull
```

### 3. Verify LFS files

You can confirm that LFS-tracked files were downloaded correctly:

```bash
git lfs ls-files
```

If any files still show as pointer files, re-run `git lfs pull`.

## Environment setup

### 4. Install Python

The product requires Python 3.12 or later.

- **Windows:** Download from [Python Release Python 3.12.0](https://www.python.org/downloads/release/python-3120/) and run the installer. Check **"Add Python to PATH"** during installation.
- **Ubuntu / Debian:** `sudo apt-get install python3.12`

Verify the installation:

```bash
python --version
```

### 5. Create a virtual environment

```bash
python -m venv myenv

# Activate — Windows
myenv\Scripts\activate

# Activate — macOS / Linux
source myenv/bin/activate
```

Or use Conda if you prefer.

### 6. Install dependencies

Install the core USD libraries and the SimReady Foundation dependencies for the validator sample:

```bash
cd nv_core/validator_sample/
pip install -r requirements.txt
```

This installs `omniverse-asset-validator`, `omniverse-usd-profiles`, and `usd-core` (the Python bindings for working with USD assets).

## About SimReady Foundation

SimReady Foundation defines guidelines and requirements for **OpenUSD content** so that assets work reliably across rendering, simulation, robotics, and AI training workflows within NVIDIA Omniverse.

The framework is built around a layered hierarchy:

| Layer | Purpose | Example |
|-------|---------|---------|
| **Requirement** | A single, testable rule an asset must satisfy | *"The stage must define a default prim"* (SAMP.001) |
| **Capability** | A category that groups related requirements | *Sample* (`SAMP`), *Visualization/Geometry* (`VG`), *Units* (`UN`) |
| **Feature** | A set of requirements that together describe a queryable property of an asset | *Minimal Placeable Visual*, *RBD Physics*, *Driven Joints* |
| **Profile** | A bundle of features that defines what an asset must satisfy for a given use case | *Prop-Robotics-Neutral*, *Robot-Body-Isaac* |

> [!IMPORTANT]
> The current validators provided in `nv_core/sr_specs` will not function as they require many more dependencies than this repo provides by itself. Those dependencies will be made available / removed in future releases.

### Profiles

Profiles are the top-level contracts between asset creators and consumers. Each profile targets a specific simulation scenario and lists the features (and their versions) that an asset must pass. Production profiles in `nv_core/sr_specs/` include:

| Profile | Description |
|---------|-------------|
| **Prop-Robotics-Neutral** | Neutral-format props suitable for robotics pipelines |
| **Prop-Robotics-Physx** | Props with PhysX rigid-body physics |
| **Robot-Body-Neutral** | Neutral robot body with physics |
| **Robot-Body-Runnable** | PhysX robot body, runnable in simulation |

### Use cases

- **Static validation** — check USD assets against a profile's requirements using the Omniverse Asset Validator or the `validate_asset.py` script in this sample.
- **Asset transformation** — convert assets between profiles (e.g. Neutral to PhysX to Isaac).
- **CI / CD** — automate validation in Jenkins or local runners.

### Where the specs live

The full SimReady specifications—capabilities, features, profiles, and guides—are in `nv_core/sr_specs/docs/`. 


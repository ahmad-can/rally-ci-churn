# Rally CI Churn

This repository is now a small Rally benchmark project rather than a single
task file. It provides:

- a local Python package with Rally plugins under `src/rally_ci_churn/`
- a Sunbeam-oriented bootstrap path via `scripts/setup_uv.sh`
- autonomous VM benchmark tasks under `tasks/`
- guest-side workload logic packaged with the plugin, not pushed over SSH

The primary VM benchmark path is autonomous:

1. Rally boots a VM with `cloud-init`.
2. The guest runs the workload itself and uploads artifacts to Swift itself.
3. The guest powers itself off.
4. Rally waits for `SHUTOFF`, parses the console result, and deletes the VM.

No floating IPs or SSH are required for the main benchmark path.

## Current scenario

- `CIChurn.boot_autonomous_vm`
  - no-FIP, no-SSH autonomous runner lifecycle
  - configurable timeout
  - `timeout_seconds: 0` means infinite wait
  - `timeout_mode: fail|soft`

The primary task template is:

- `tasks/autonomous_vm_waves.yaml.j2`

The primary example args file is:

- `args/autonomous_vm.example.yaml`

## Fast start

This assumes:

- your `clouds.yaml` contains `sunbeam` and `sunbeam-admin`
- `sunbeam-admin` can list images, flavors, and networks
- Swift is enabled
- you want the autonomous VM scenario

Bootstrap:

```bash
./scripts/setup_uv.sh /path/to/clouds.yaml
source .venv/bin/activate
source adminrc
```

Create or select a Rally deployment:

```bash
rally db create
rally deployment create --fromenv --name sunbeam
```

Validate and run:

```bash
rally task validate tasks/autonomous_vm_waves.yaml.j2 \
  --task-args-file args/sunbeam.local.yaml

rally task start tasks/autonomous_vm_waves.yaml.j2 \
  --task-args-file args/sunbeam.local.yaml
```

## Bootstrap behavior

`scripts/setup_uv.sh` is intentionally thin. It:

- creates `.venv`
- installs Rally, `rally-openstack`, and this local package
- delegates cloud discovery and args generation to
  `python -m rally_ci_churn.bootstrap.sunbeam`

The Sunbeam bootstrap currently discovers:

- image and flavor
- external network name and ID
- DNS nameservers from the Sunbeam project subnet
- Swift auth details from `sunbeam`
- admin RC details from `sunbeam-admin`

It writes:

- `args/sunbeam.local.yaml`
- `adminrc`

## Project layout

- `src/rally_ci_churn/plugins/`: Rally scenario plugins
- `src/rally_ci_churn/guest/`: packaged autonomous guest workload runners
- `src/rally_ci_churn/results.py`: shared result parsing/output shaping
- `src/rally_ci_churn/bootstrap/`: Sunbeam-oriented discovery and args generation
- `tasks/`: Rally task templates
- `scripts/setup_uv.sh`: thin local bootstrap wrapper

## Existing helper scripts

These remain useful but are not the primary benchmark path:

- `scripts/prepare_build_image.sh`
- `scripts/install_build_profile.sh`
- `scripts/cleanup_swift_container.py`

# ubuntu-stress-ng

## What it is

`ubuntu-stress-ng` is the pre-baked image used for `stress_ng` autonomous VM
benchmarks.

## When to use it

Use this image for:

- `stress-ng` preset runs
- autonomous VM runs with `workload_profile: stress_ng`

## Build

```bash
./scripts/build_imagecraft_vm.sh images/ubuntu-stress-ng
```

## Upload to Glance

```bash
openstack image create ubuntu-stress-ng \
  --file images/ubuntu-stress-ng/disk.img \
  --disk-format raw \
  --container-format bare \
  --property hw_firmware_type=uefi \
  --public
```

## Recommended flavor

Recommended starting flavor:

- `m1.stress-ng`
  - `2 vCPU`
  - `2048 MB RAM`
  - `5 GB disk`

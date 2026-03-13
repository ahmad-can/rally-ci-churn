# ubuntu-fio

## What it is

`ubuntu-fio` is the pre-baked image used by `CIChurn.fio_distributed` for both
the controller VM and the worker VMs.

## When to use it

Use this image for:

- `fio-distributed` preset runs
- any direct use of `tasks/fio_distributed.yaml.j2`

## Build

```bash
./scripts/build_imagecraft_vm.sh images/ubuntu-fio
```

## Upload to Glance

```bash
openstack image create ubuntu-fio \
  --file images/ubuntu-fio/disk.img \
  --disk-format raw \
  --container-format bare \
  --public

openstack image set ubuntu-fio \
  --property hw_firmware_type=uefi
```

## Recommended flavor

Recommended starting flavor:

- `m1.fio`
  - `2 vCPU`
  - `2048 MB RAM`
  - `5 GB disk`

This is the flavor used in the current Sunbeam-oriented fio runs.

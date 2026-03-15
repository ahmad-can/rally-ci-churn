# Images

This directory contains Imagecraft-based benchmark images and their local build
artifacts.

## Image index

- [ubuntu-fio/README.md](./images/ubuntu-fio/README.md)
  - distributed fio controller and worker image
- [ubuntu-netbench/README.md](./images/ubuntu-netbench/README.md)
  - network benchmark controller/server/client image
- [ubuntu-mixed-benchmark/README.md](./images/ubuntu-mixed-benchmark/README.md)
  - unified image for the mixed pressure scenario
- [ubuntu-stress-ng/README.md](./images/ubuntu-stress-ng/README.md)
  - stress-ng autonomous workload image

## Shared build path

Preferred build flow:

```bash
./scripts/build_imagecraft_vm.sh images/<image-name>
```

This keeps the destructive Imagecraft build inside a temporary LXD VM instead
of running it on the host directly.

# Scope

## What this repo is

This repository is a small Rally benchmark project for OpenStack, with current
focus on Sunbeam-based deployments.

It covers:

- autonomous CI-runner churn with guest-managed lifecycle
- bursty and quota-edge VM launch behavior
- distributed fio benchmarking across worker VMs and attached Cinder volumes
- pre-baked benchmark images built with Imagecraft

## What this repo is not

It is not:

- a general OpenStack deployment guide
- a generic monitoring stack
- a replacement for full performance lab tooling
- a generic image factory for arbitrary workloads

## Supported operating model

The intended operator flow is:

1. bootstrap with `scripts/setup_uv.sh`
2. select a generated preset args file
3. run a Rally task template
4. inspect Rally outputs and local artifacts

The intended cloud focus today is Sunbeam. Other OpenStack clouds may work, but
the bootstrap and docs are intentionally optimized for Sunbeam first.

## Main constraints

- autonomous VM scenarios avoid floating IPs and SSH by default
- distributed fio deliberately uses one controller floating IP and SSH
- custom images are optional for most VM churn scenarios, but required for
  `stress-ng` and fio
- benchmark raw data may live outside the Rally DB, with Rally storing concise
  summaries and artifact pointers

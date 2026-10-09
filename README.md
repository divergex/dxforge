# <img src="docs/_static/forge.png" alt="dxforge icon, an anvil" width="64" height="64" /> dxforge

**dxforge** is the orchestration suite within the Divergex ecosystem, designed to serve service meshes, secure communication, and containerized
infrastructure management for high-performance quantitative research and trading systems.

It is basically just a multi-tenant scheduling serverless platform, but self-hosted on your own infrastructure.

## Main Usage

### Orchestration

The main purpose of dxforge is to use it to orchestrate and schedule processes. Suppose you have a small prop trading setup, for a retailer or family
member, or even a small desk at a trading firm.

We believe that everyone should own their own trading setup, and dxforge is the tool to help you start with that. At some point, you will want a more
robust syste, to organize your strategies (or strategy! dxforge is aimed to both the small and large investors).

### **Service Discovery**

Moved to [dxcore](https://www.github.com/divergex/dxcore).

### **Containerization**

- Different users have different needs, and dxforge aims to allows you to run your services either in isolated containers or directly on your host
  machine. This should ensure that dependencies and configurations between strategies do not conflict depending on your needs.
- Works with Docker and (in future also Kubernetes and Podman) to deploy, manage, and scale services.

## Features

These are our main objectives/requiisites for all future features

- **Scalability**: Easily scale services up and down based or number of strategies.
- **Fault Tolerance**: Incorporate resiliency features like retries, fallbacks, and circuit breakers.
- **Interoperability**: Full integration with (but still decoupled to) other components of the divergex ecosystem, including `cadlag` and `dxlib`.

## Installation

### Prerequisites

- Python 3.12+
- Docker with the `compose` plugin

### Self-hosting an instance

The compose file, the container bootstrap scripts, and the container image reference ship inside the package:

```bash
pip install dxforge
  forge init ~/<your-stack>k              # renders docker-compose.yml, bootstrap/, .env.example, secrets/
forge up --dir ~/dxforge-stack          # starts Postgres, MinIO, OpenBao and the registry
forge bootstrap --dir ~/dxforge-stack   # bootstraps credentials, service accounts and migrations
forge run api --dir ~/dxforge-stack
```

`forge init` writes the published image tag matching the installed `dxforge` version into `docker-compose.yml`; re-run it with `--force` after
upgrading. Commands resolve the stack directory from `--dir`, then `$FORGE_STACK_DIR`, then the working directory.

Root secrets are generated once into `<stack>/secrets` and never rewritten. `forge down --volumes --dir <stack>` erases all stack data and
credentials. The images above the dxforge one (Postgres, MinIO, OpenBao, registry) are pinned by digest; re-resolve a pin with

```bash
docker buildx imagetools inspect <image>:<tag> --format '{{.Manifest.Digest}}'
```

### Development

```bash
git clone https://github.com/divergex/dxforge.git
cd dxforge
python -m venv .venv && source .venv/bin/activate
pip install -e .
make setup        # forge init .stack --force && forge bootstrap --dir .stack
```

`make reset` tears the stack down and deletes its volumes and generated secrets. The compose file is generated, so `forge init .stack --force`
re-renders it after template changes.

## Usage

Once set up, you can configure your services to interact via **dxforge** for service discovery, mesh registration, and secure communication. To enable
these features:

1. **Service Registration**: Register services with the built-in discovery mechanism.
2. **Inter-Service Communication**: Utilize the provided protocols and channels for secure messaging.
3. **Scaling**: Leverage Kubernetes or Docker Swarm to scale services automatically based on load.

Start the api and access it at `http://localhost:8000` with

```
forge run api
```

## Contributing

If you'd like to contribute to the development of **dxforge**, see the [CONTRIBUTING](CONTRIBUTING.md) guidelines for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

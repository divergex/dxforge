# <img src="docs/_static/forge.png" alt="dxforge icon, an anvil" width="64" height="64" /> dxforge

**dxforge** is the orchestration suite within the Divergex ecosystem,
designed to enable seamless service discovery, secure communication,
and containerized infrastructure management for high-performance
quantitative research and trading systems.

It is basically just a multi-tenant scheduling serverless platform,
but self-hosted on your own infrastructure.

## Main Usage

### Orchestration

The main purpose of dxforge is to use it to orchestrate and schedule of processes.
Suppose you have a small prop trading setup, for a retailer or family member, or even a small desk at a trading firm.

We believe that everyone should be able to run their own trading infrastructure,
and dxforge is the tool to help you start with that.
At some point, you will want a more robust setup to organize your strategies
(or strategy! dxforge is aimed to both the small and large investors).

### **Service Discovery**

Moved to [dxlib](https://www.github.com/divergex/dxlib).

### **Containerization**

- Different users have different needs, and dxforge aims to allows you to run your services in isolated containers, on host or on isolated processes,
ensuring that dependencies and configurations do not conflict depending on your needs.
- Works with Docker and (in future also Kubernetes and Podman) to deploy, manage, and scale services.

## Features

We aim mainly to have dxforge provide the following for all levels of users,
and are our main requiisites for all future features

- **Scalability**: Easily scale services up and down based or num of strategies.
- **Fault Tolerance**: Incorporate resiliency features like retries, fallbacks, and circuit breakers.
- **Interoperability**: At some point support full integration with other components of the divergex ecosystem,
including `cadlag` and `dxlib`.

## Installation

### Prerequisites

- Python 3.x
- Or `git` if you want to clone the repository directly.

### Getting Started

Installing with `pip`:

```bash
pip install dxforge  # TODO
```

Cloning the repository:

```bash
git clone https://github.com/divergex/dxforge.git
cd dxforge
```

Create an environment and install locally with

```bash
conda create -n dxforge python=3.12
conda activate dxforge
pip install -e .
```

You should now be able to run tests and also the CLI with

```
forge --help
```

## Usage

Once set up, you can configure your services to interact via **dxforge** for service discovery, mesh registration, and
secure communication. To enable these features:

1. **Service Registration**: Register services with the built-in discovery mechanism.
2. **Inter-Service Communication**: Utilize the provided protocols and channels for secure messaging.
3. **Scaling**: Leverage Kubernetes or Docker Swarm to scale services automatically based on load.

Start the api and access it at `http://localhost:8000` with

```
forge api run
```

## Contributing

If you'd like to contribute to the development of **dxforge**, see the [CONTRIBUTING](CONTRIBUTING.md) guidelines for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

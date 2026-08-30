# <img src="docs/_static/forge.png" alt="dxforge icon, an anvil" width="64" height="64" /> dxforge

**dxforge** is the orchestration suite within the Divergex ecosystem, designed to enable seamless service discovery,
secure communication, and containerized infrastructure management for high-performance quantitative research and trading
systems.

It is basically just a multi-tenant scheduling algorithm/platform.

## Main Usage

### Orchestration

The main purpose of dxforge is to use it to orchestrate and schedule of processes.
Suppose you have a small prop trading setup, for a retailer or family member, or even a small desk at a trading firm.
We believe that everyone should be able to run their own trading infrastructure, and dxforge is the tool to help you start with that.
At some point, you will want a more robust setup to organize your strategies (or strategy! dxforge is aimed to both the small and large trader).

### 1. **Service Discovery**

- Automatically lets instances register themselves and identify allowed feeds and order executors, as well as other services you might run in parallel.
- Improve flexibility and reduce manual configuration with a reusable service discovery mechanism.
- Supports decentralized service registration to improve dev experience, resource utilization and fault tolerance by reducing single points of failure.

### 2. **Containerization**

- Different users have different needs, and dxforge aims to allows you to run your services in isolated containers, on host or on isolated processes,
ensuring that dependencies and configurations do not conflict depending on your needs.
- Works with Docker and (in future also Kubernetes and Podman) to deploy, manage, and scale services.

### 4. **Cross-Service Communication**

> Technically this part is managed by `dxlib` instead, but dxforge is aimed to integrate well with it.

## Features

We aim mainly to have dxforge provide the following for all levels of users, from small retail to large institutional trading:

- **Scalability**: Easily scale services up and down based or num of strategies.
- **Fault Tolerance**: Incorporate resiliency features like retries, fallbacks, and circuit breakers.
- **Interoperability**: At some point support fu8ll integration with other components of the divergex ecosystem, including `cadlag` and
  `dxlib`.

## Installation

### Prerequisites

- Python 3.x
- Or `git` if you want to clone the repository directly.

### Getting Started

Installing with `pip`:

```bash
pip install dxforge
```

Cloning the repository:

```bash
git clone https://github.com/divergex/dxforge.git
cd dxforge
```

Build the Docker containers:

```bash
docker-compose build
```

Run the services:

```bash
docker-compose up
```

You can now interact with your services as needed.

## Usage

Once set up, you can configure your services to interact via **dxforge** for service discovery, mesh registration, and
secure communication. To enable these features:

1. **Service Registration**: Register services with the built-in discovery mechanism.
2. **Inter-Service Communication**: Utilize the provided protocols and channels for secure messaging.
3. **Scaling**: Leverage Kubernetes or Docker Swarm to scale services automatically based on load.

> TODO: Use either the CLI or access the web ui at `http://localhost:7000` to manage your services.

## Contributing

If you'd like to contribute to the development of **dxforge**, see the [CONTRIBUTING](CONTRIBUTING.md) guidelines for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

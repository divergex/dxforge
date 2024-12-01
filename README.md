# dxforge

![Divergex Logo](https://github.com/divergex/dxforge/blob/main/docs/assets/forge.png)

**dxforge** is the orchestration suite within the Divergex ecosystem, designed to enable seamless service discovery,
secure communication, and containerized infrastructure management for high-performance quantitative research and trading
systems. It is built to coordinate the interactions between services, facilitating scalability, security, and efficient
deployment of microservices across various environments.

## Main Functionalities

### 1. **Service Discovery**

- Automatically identifies and registers services in the ecosystem.
- Allows for dynamic discovery of available services, improving flexibility and reducing manual configuration.
- Supports decentralized service registration for efficient resource utilization and fault tolerance.

### 2. **Mesh Registration**

- Ensures that services within the ecosystem are properly registered within a service mesh.
- Provides routing capabilities, load balancing, and service-to-service communication.

### 3. **Containerization and Orchestration**

- Leverages containerization for isolating services, ensuring consistent environments across development, testing, and
  production.
- Works with Docker and Kubernetes to deploy, manage, and scale services.
- Automates the orchestration of services, ensuring that dependencies and service states are managed efficiently.

### 4. **Cross-Service Communication**

- Provides tools and libraries to support communication between services through APIs, RPC calls, and message queues.
- Integrates with FastAPI, gRPC, and other protocols to enable high-performance interactions between microservices.

## Features

- **Scalability**: Easily scale services up and down based on demand.
- **Fault Tolerance**: Incorporates resiliency features like retries, fallbacks, and circuit breakers.
- **Interoperability**: Supports integration with other components of the Divergex ecosystem, including `dxcore` and
  `dxlib`.

## Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.x (for CLI and development)

### Getting Started

Clone the repository:

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

Use either the CLI or access the web ui at `http://localhost:7000` to manage your services.

## Contributing

If you'd like to contribute to the development of **dxforge**, please follow the steps below:

1. Fork the repository.
2. Create a new feature branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Submit a pull request.

We welcome contributions to improve the functionality and performance of **dxforge**!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

This README gives a clear, concise overview of the project and its key features. It can be expanded with additional
technical details, like specific configurations, environment variables, or advanced usage examples, depending on how you
want to communicate the project's setup and usage to your audience.
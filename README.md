# RLink

<div align="center">
    <img src="./assets/logo.png" alt="项目Logo" width="150"/>
</div>

RLink is a lightweight, high-performance communication layer specifically designed for distributed reinforcement learning systems. It enables seamless data exchange between actors (environment interaction) and learners (model training), decoupling sampling from training to scale your RL experiments efficiently.

### ✨ Key Features

🚀 Low-Latency Communication – Optimized for fast transfer of trajectories, actions, observations, and model parameters

📈 Scalability – Supports many-to-one and one-to-many communication patterns for flexible scaling

🔌 Easy Integration – Simple API to connect existing RL frameworks and training pipelines

🌍 Language-Agnostic Design – Currently supports Python with plans for C++/Rust backends

🛡️ Fault-Tolerant – Optional reliability features to handle intermittent connection drops

### 🎯 Why RLink?

Building distributed RL systems often involves complex communication infrastructure. RLink simplifies this by providing a dedicated, optimized layer that:

- Decouples sampling and training processes

- Accelerates experimentation across multiple processes or machines

- Reduces infrastructure overhead

- Enables seamless scaling of actors and learners

### 📊 Architecture Overview

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     |                 |
│   RL Actors     │────▶│    RLink        │────▶│   RL Learners   │
│  (Sampling)     │◀────│  Communication  │◀────│   (Training)    │
│                 │     │     Layer       │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```
<div align="center">
    <img src="./assets/arch.png" alt="arch" width="700"/>
</div>


### 🚀 Quick Start

Installation
```
pip install rlinks
```
Basic Usage

As a actor
```python
from rlinks.actor import RLinkActor

actor = RLinkActor("http://learner-ip:8443")

# Send data to learner.
data = {
        "image_0": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        "action": np.random.randint((50, 14)).astype(np.float32),
        "index": 0,
}

for i in range(4):
    data["index"] = i
    actor.put(data)

# Get model from learner.
models = actor.get_remote_model()

```

As as Learner

```bash
# To start the leaner, you can either run it directly in a terminal or daemonize it to run in the background.
rlinks learner --gpu-num 8 --port 8443

rlinks learner --help
```

```python
from rlinks.dataset import RLinkDataset

class YourDataset:
    def __init__(self):
        self._rl_dataset = RLinkDataset(gpu_id=torch.cuda.current_device())

    def __getitem__(self,idx):
        data = self._rl_dataset.__getitem__(idx)
```

```python
from rlinks.learner import RLinkSyncModel

RLinkSyncModel.sync("your model path")
```

### 📚 Use Cases
Distributed RL Training – Scale to hundreds of parallel environments

Multi-Agent Systems – Coordinate communication between agents

Federated RL – Train across distributed data sources

Hybrid Cloud/Edge Training – Deploy actors and learners across different infrastructure

### 🔄 Communication Patterns

|Pattern	|Description	|Use Case|
|---------|-------------|--------|
|Many-to-One |	Multiple actors → Single learner	|Centralized training |
|One-to-Many |  Single learner → Multiple actors	|Parameter distribution |
|Bidirectional |	Two-way communication|	Advanced coordination |

### 🛠️ Integration with Popular Frameworks

### 📈 Performance Benchmarks

### 🔮 Roadmap

### 🤝 Contributing

We welcome contributions! Please see our Contributing Guidelines for details. [CONTRIBUTING](./CONTRIBUTING.md)

### 📄 License

RLink is released under the MIT License. See LICENSE for details [LICENSE](./LICENSE).

📞 Support & Community

📖 Documentation

🐛 Issue Tracker

💬 Discord Community

🐦 Twitter Updates

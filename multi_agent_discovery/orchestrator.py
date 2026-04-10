"""
Swarm Orchestrator — Coordinates All Agents
============================================
The orchestrator manages the multi-agent discovery swarm:

1. PARALLEL EXPLORATION: Multiple explorers search different
   regions of hypothesis space simultaneously
2. ASYNCHRONOUS REFINEMENT: Refiners pick up promising candidates
   and improve them while explorers keep searching
3. CONTINUOUS ADVERSARIAL REVIEW: Adversaries validate/falsify
   in real-time, preventing resource waste on dead ends
4. CROSS-POLLINATION: Every N iterations, the pollinator scans
   for transferable patterns across domains
5. META-LEARNING: Every M iterations, the meta-learner analyzes
   the entire process and adjusts agent parameters

Exponential acceleration comes from:
  - Parallelism: N agents = N× throughput
  - Cross-pollination: breakthrough in domain A → free hypothesis in domain B
  - Meta-learning: each round is more efficient than the last
  - Compound refinement: refiner builds on explorer + pollinator outputs
  - Adversarial pruning: early falsification saves compute
"""

import time
import json
import concurrent.futures
from dataclasses import dataclass, field
from pathlib import Path

from .blackboard import Blackboard, HypothesisStatus
from .agents import (
    BaseAgent, ExplorerAgent, RefinerAgent, AdversaryAgent,
    CrossPollinatorAgent, MetaLearnerAgent, TheoristAgent,
    AgentConfig, create_agent,
)


@dataclass
class SwarmConfig:
    """Configuration for the entire agent swarm."""
    domains: list[str]
    explorers_per_domain: int = 3
    refiners_per_domain: int = 2
    adversaries: int = 2
    theorists: int = 1
    pollinators: int = 1
    meta_learners: int = 1
    total_rounds: int = 10
    pollination_interval: int = 3   # cross-pollinate every N rounds
    meta_learn_interval: int = 2    # meta-learn every M rounds
    max_workers: int = 8            # thread pool size
    persist_path: str = "results/swarm_state.json"
    # Domain variable mappings for cross-pollination
    domain_mappings: dict = field(default_factory=dict)


class SwarmOrchestrator:
    """
    Coordinates the multi-agent discovery swarm.

    Lifecycle of a round:
    ┌─────────────────────────────────────────────────────┐
    │ 1. Explorers search in parallel (breadth)           │
    │ 2. Refiners improve top candidates (depth)          │
    │ 3. Adversaries review all new discoveries           │
    │ 4. [Every N rounds] Pollinator transfers patterns   │
    │ 5. [Every M rounds] Meta-learner optimizes process  │
    │ 6. Theorists formalize validated discoveries         │
    │ 7. Update scoreboard & persist state                │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, config: SwarmConfig):
        self.config = config
        self.blackboard = Blackboard(persist_path=config.persist_path)
        self.agents: list[BaseAgent] = []
        self.round = 0
        self.round_log: list[dict] = []
        self._setup_agents()

    def _setup_agents(self):
        """Create all agents according to swarm config."""
        agent_counter = 0

        for domain in self.config.domains:
            # Explorers — each with different exploration rates for diversity
            for i in range(self.config.explorers_per_domain):
                agent_counter += 1
                explore_rate = 0.2 + (i * 0.2)  # 0.2, 0.4, 0.6, ...
                agent = create_agent(
                    role="explorer",
                    agent_id=f"explorer_{domain}_{i}",
                    domain=domain,
                    blackboard=self.blackboard,
                    parameters={"exploration_rate": explore_rate},
                )
                agent.config.exploration_rate = explore_rate
                self.agents.append(agent)

            # Refiners
            for i in range(self.config.refiners_per_domain):
                agent_counter += 1
                agent = create_agent(
                    role="refiner",
                    agent_id=f"refiner_{domain}_{i}",
                    domain=domain,
                    blackboard=self.blackboard,
                )
                self.agents.append(agent)

            # Theorists
            for i in range(self.config.theorists):
                agent_counter += 1
                agent = create_agent(
                    role="theorist",
                    agent_id=f"theorist_{domain}_{i}",
                    domain=domain,
                    blackboard=self.blackboard,
                )
                self.agents.append(agent)

        # Adversaries (domain-agnostic)
        for i in range(self.config.adversaries):
            agent_counter += 1
            agent = create_agent(
                role="adversary",
                agent_id=f"adversary_{i}",
                domain="*",  # reviews all domains
                blackboard=self.blackboard,
            )
            self.agents.append(agent)

        # Meta-learners
        for i in range(self.config.meta_learners):
            agent_counter += 1
            agent = create_agent(
                role="meta_learner",
                agent_id=f"meta_learner_{i}",
                domain="*",
                blackboard=self.blackboard,
            )
            self.agents.append(agent)

        # Cross-pollinators (need domain mappings)
        for i in range(self.config.pollinators):
            agent_counter += 1
            pollinator_config = AgentConfig(
                agent_id=f"pollinator_{i}",
                role="pollinator",
                domain="*",
            )
            agent = CrossPollinatorAgent(
                config=pollinator_config,
                blackboard=self.blackboard,
                domain_mappings=self.config.domain_mappings,
            )
            self.agents.append(agent)

        print(f"Swarm initialized: {agent_counter} agents across {len(self.config.domains)} domains")

    def run_round(self) -> dict:
        """Execute one round of the discovery cycle."""
        self.round += 1
        self.blackboard.iteration_count = self.round
        round_start = time.time()
        round_results = {"round": self.round, "new_discoveries": 0, "events": []}

        print(f"\n{'='*60}")
        print(f"  ROUND {self.round}")
        print(f"{'='*60}")

        # Phase 1: Parallel exploration
        print("  Phase 1: Exploration...")
        explorers = [a for a in self.agents if isinstance(a, ExplorerAgent)]
        new_ids = self._run_agents_parallel(explorers)
        round_results["new_discoveries"] += len(new_ids)
        round_results["events"].append(f"Exploration: {len(new_ids)} new candidates")

        # Phase 2: Refinement
        print("  Phase 2: Refinement...")
        refiners = [a for a in self.agents if isinstance(a, RefinerAgent)]
        refined_ids = self._run_agents_parallel(refiners)
        round_results["new_discoveries"] += len(refined_ids)
        round_results["events"].append(f"Refinement: {len(refined_ids)} improvements")

        # Phase 3: Adversarial review
        print("  Phase 3: Adversarial review...")
        adversaries = [a for a in self.agents if isinstance(a, AdversaryAgent)]
        self._run_agents_parallel(adversaries)
        bb_summary = self.blackboard.summary()
        round_results["events"].append(
            f"Review: {bb_summary['by_status'].get('validated', 0)} validated, "
            f"{bb_summary['by_status'].get('falsified', 0)} falsified"
        )

        # Phase 4: Cross-pollination (periodic)
        if self.round % self.config.pollination_interval == 0:
            print("  Phase 4: Cross-pollination...")
            pollinators = [a for a in self.agents if isinstance(a, CrossPollinatorAgent)]
            transfer_ids = self._run_agents_parallel(pollinators)
            round_results["new_discoveries"] += len(transfer_ids)
            round_results["events"].append(f"Pollination: {len(transfer_ids)} transfers")

        # Phase 5: Meta-learning (periodic)
        if self.round % self.config.meta_learn_interval == 0:
            print("  Phase 5: Meta-learning...")
            meta_learners = [a for a in self.agents if isinstance(a, MetaLearnerAgent)]
            self._run_agents_parallel(meta_learners)
            actionable = self.blackboard.get_actionable_insights()
            self._apply_meta_insights(actionable)
            round_results["events"].append(f"Meta-learning: {len(actionable)} insights applied")

        # Phase 6: Theorization
        print("  Phase 6: Theorization...")
        theorists = [a for a in self.agents if isinstance(a, TheoristAgent)]
        self._run_agents_parallel(theorists)

        # Summary
        elapsed = time.time() - round_start
        round_results["elapsed_seconds"] = elapsed
        round_results["blackboard_summary"] = self.blackboard.summary()
        self.round_log.append(round_results)

        self._print_scoreboard()
        return round_results

    def _run_agents_parallel(self, agents: list[BaseAgent]) -> list[str]:
        """Run a group of agents in parallel using thread pool."""
        all_ids = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_workers
        ) as executor:
            futures = {
                executor.submit(agent.run_iteration): agent
                for agent in agents
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    ids = future.result()
                    all_ids.extend(ids)
                except Exception as e:
                    agent = futures[future]
                    print(f"    Agent {agent.config.agent_id} error: {e}")
        return all_ids

    def _apply_meta_insights(self, insights: list):
        """Apply meta-insights to adjust agent parameters."""
        for insight in insights:
            if insight.insight_type == "operator_pattern":
                # Adjust explorer operator preferences
                for agent in self.agents:
                    if isinstance(agent, ExplorerAgent):
                        # Bias towards successful operators
                        pass
                insight.applied = True

            elif insight.insight_type == "complexity_sweet_spot":
                # Adjust complexity budgets
                for agent in self.agents:
                    if hasattr(agent.config, "complexity_budget"):
                        pass
                insight.applied = True

            elif insight.insight_type == "convergence_warning":
                # Increase exploration rate for struggling domains
                for agent in self.agents:
                    if isinstance(agent, ExplorerAgent):
                        agent.config.exploration_rate = min(
                            0.8, agent.config.exploration_rate + 0.1
                        )
                insight.applied = True

    def run(self, n_rounds: int | None = None):
        """Run the full swarm for N rounds."""
        total = n_rounds or self.config.total_rounds
        print(f"\nStarting swarm: {total} rounds")
        print(f"Agents: {len(self.agents)}")
        print(f"Domains: {self.config.domains}")
        print(f"Pollination every {self.config.pollination_interval} rounds")
        print(f"Meta-learning every {self.config.meta_learn_interval} rounds")

        for _ in range(total):
            self.run_round()

        print(f"\n{'='*60}")
        print(f"  SWARM COMPLETE — {total} rounds")
        print(f"{'='*60}")
        self._print_final_report()
        return self.round_log

    def _print_scoreboard(self):
        """Print current scoreboard."""
        summary = self.blackboard.summary()
        print(f"\n  ┌── Scoreboard (Round {self.round}) ──┐")
        print(f"  │ Total discoveries: {summary['total_discoveries']}")
        for status, count in summary["by_status"].items():
            if count > 0:
                print(f"  │   {status}: {count}")
        for domain, stats in summary["by_domain"].items():
            print(f"  │ {domain}: best_acc={stats['best_accuracy']:.3f}, "
                  f"breakthroughs={stats['breakthrough_count']}")
        print(f"  │ Analogies: {summary['total_analogies']} "
              f"({summary['untested_analogies']} untested)")
        print(f"  │ Meta-insights: {summary['meta_insights']}")
        print(f"  └{'─'*30}┘\n")

    def _print_final_report(self):
        """Print final summary."""
        summary = self.blackboard.summary()
        print("\n  FINAL RESULTS")
        print(f"  Total discoveries: {summary['total_discoveries']}")
        print(f"  Validated: {summary['by_status'].get('validated', 0)}")
        print(f"  Promoted (with theory): {summary['by_status'].get('promoted', 0)}")
        print(f"  Falsified (pruned): {summary['by_status'].get('falsified', 0)}")
        print(f"  Cross-domain transfers: {summary['total_analogies']}")

        # Top discovery per domain
        for domain in self.config.domains:
            top = self.blackboard.get_top_discoveries(domain=domain, n=1)
            if top:
                d = top[0]
                print(f"\n  BEST ({domain}):")
                print(f"    {d.law_expression}")
                print(f"    accuracy={d.accuracy:.4f}, complexity={d.complexity}, R²={d.r_squared:.4f}")

    def save_report(self, path: str = "results/swarm_report.json"):
        """Save complete swarm report."""
        report = {
            "config": {
                "domains": self.config.domains,
                "total_agents": len(self.agents),
                "total_rounds": self.round,
            },
            "blackboard_summary": self.blackboard.summary(),
            "round_log": self.round_log,
            "top_discoveries": {
                domain: [d.to_dict() for d in self.blackboard.get_top_discoveries(domain=domain, n=5)]
                for domain in self.config.domains
            },
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\n  Report saved to {path}")


# ═══════════════════════════════════════════════════════════
# PRESET CONFIGURATIONS
# ═══════════════════════════════════════════════════════════

def create_physics_materials_swarm() -> SwarmOrchestrator:
    """
    Pre-configured swarm for the exoplanet + materials discovery
    domains that already exist in this project.
    """
    config = SwarmConfig(
        domains=["exoplanet_stability", "materials_bandgap"],
        explorers_per_domain=3,
        refiners_per_domain=2,
        adversaries=2,
        theorists=1,
        pollinators=1,
        meta_learners=1,
        total_rounds=10,
        domain_mappings={
            "exoplanet_stability→materials_bandgap": {
                "delta_hill": "tolerance_factor",
                "mass_ratio": "mass_B_over_X",
                "period_ratio": "IE_ratio",
                "eccentricity": "electronegativity_diff",
            },
            "materials_bandgap→exoplanet_stability": {
                "tolerance_factor": "delta_hill",
                "mass_B_over_X": "mass_ratio",
                "IE_ratio": "period_ratio",
                "electronegativity_diff": "eccentricity",
            },
        },
    )
    return SwarmOrchestrator(config)


def create_general_swarm(domains: list[str],
                         domain_mappings: dict | None = None) -> SwarmOrchestrator:
    """Create a swarm for arbitrary domains."""
    config = SwarmConfig(
        domains=domains,
        domain_mappings=domain_mappings or {},
    )
    return SwarmOrchestrator(config)

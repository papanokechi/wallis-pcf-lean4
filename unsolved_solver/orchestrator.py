"""
Orchestrator — Multi-Agent Coordinator
========================================
Manages the agent swarm, executing phases per round:
  1. Explorers generate candidates (parallel across domains)
  2. Pattern miners extract structure
  3. Adversaries challenge findings
  4. Refiners improve top discoveries
  5. Formalizers generate proof sketches
  6. [Periodic] Pollinators transfer cross-domain insights
  7. [Periodic] Meta-learners adapt strategies

Implements self-improving iteration with exponential search space reduction.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from unsolved_solver.blackboard import Blackboard, Discovery
from unsolved_solver.agents import (
    AGENT_REGISTRY, BaseAgent, ExplorerAgent, PatternMinerAgent,
    AdversaryAgent, RefinerAgent, FormalizerAgent, MetaLearnerAgent,
    PollinatorAgent
)


class Orchestrator:
    """Coordinates multi-agent problem solving across all three conjectures."""

    DOMAINS = ['collatz', 'erdos_straus', 'hadamard']

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.blackboard = Blackboard()
        self.agents: Dict[str, BaseAgent] = {}
        self.round_num = 0
        self.start_time = 0.0
        self.results_log: List[Dict[str, Any]] = []

        self._create_agents()

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            'max_rounds': 5,
            'max_workers': 4,
            'domains': ['collatz', 'erdos_straus', 'hadamard'],
            'pollinate_every': 2,
            'meta_learn_every': 2,
            'formalize_every': 2,
            'agents_per_type': {
                'explorer': 1,
                'pattern_miner': 1,
                'adversary': 1,
                'refiner': 1,
                'formalizer': 1,
                'meta_learner': 1,
                'pollinator': 1,
            },
            'verbose': True,
        }

    def _create_agents(self):
        """Instantiate the agent swarm."""
        for agent_type, count in self.config.get('agents_per_type', {}).items():
            cls = AGENT_REGISTRY.get(agent_type)
            if cls is None:
                continue
            for i in range(count):
                aid = f"{agent_type}_{i}"
                self.agents[aid] = cls(aid, self.blackboard, self.config)

    def run(self) -> Dict[str, Any]:
        """Execute the full self-iterative solving loop."""
        self.start_time = time.time()
        max_rounds = self.config.get('max_rounds', 5)
        domains = self.config.get('domains', self.DOMAINS)

        if self.config.get('verbose'):
            print("=" * 72)
            print("  Self-Iterative Collaborative AI Problem Solver")
            print("  Targets: Collatz · Erdős–Straus · Hadamard")
            print("=" * 72)
            print(f"  Agents: {len(self.agents)} | Domains: {len(domains)} | Rounds: {max_rounds}")
            print("=" * 72)

        for rnd in range(1, max_rounds + 1):
            self.round_num = rnd
            round_start = time.time()

            if self.config.get('verbose'):
                print(f"\n{'─' * 60}")
                print(f"  Round {rnd}/{max_rounds}")
                print(f"{'─' * 60}")

            round_discoveries = []

            # Phase 1: Exploration — all domains in parallel
            phase1 = self._run_phase('explorer', domains, rnd)
            round_discoveries.extend(phase1)

            # Phase 2: Pattern Mining
            phase2 = self._run_phase('pattern_miner', domains, rnd)
            round_discoveries.extend(phase2)

            # Phase 3: Adversarial Review
            phase3 = self._run_phase('adversary', domains, rnd)
            round_discoveries.extend(phase3)

            # Phase 4: Refinement
            phase4 = self._run_phase('refiner', domains, rnd)
            round_discoveries.extend(phase4)

            # Phase 5: Formalization (periodic)
            if rnd % self.config.get('formalize_every', 2) == 0:
                phase5 = self._run_phase('formalizer', domains, rnd)
                round_discoveries.extend(phase5)

            # Phase 6: Cross-pollination (periodic)
            if rnd % self.config.get('pollinate_every', 2) == 0:
                phase6 = self._run_phase('pollinator', domains, rnd)
                round_discoveries.extend(phase6)

            # Phase 7: Meta-learning (periodic)
            if rnd % self.config.get('meta_learn_every', 2) == 0:
                phase7 = self._run_phase('meta_learner', domains, rnd)
                round_discoveries.extend(phase7)

            round_time = time.time() - round_start

            # Log round summary
            summary = {
                'round': rnd,
                'discoveries': len(round_discoveries),
                'time': round_time,
                'stats': self.blackboard.get_stats(),
            }
            self.blackboard.log_round(rnd, summary)
            self.results_log.append(summary)

            if self.config.get('verbose'):
                self._print_round_summary(rnd, round_discoveries, round_time)

        total_time = time.time() - self.start_time

        # Final report
        final = self._generate_final_report(total_time)
        if self.config.get('verbose'):
            self._print_final_report(final)

        return final

    def _run_phase(self, agent_type: str, domains: List[str],
                    round_num: int) -> List[Discovery]:
        """Run all agents of a given type across all domains."""
        discoveries = []
        agents_of_type = [a for a in self.agents.values()
                          if a.agent_type == agent_type]

        if not agents_of_type:
            return discoveries

        max_workers = min(self.config.get('max_workers', 4),
                          len(agents_of_type) * len(domains))

        if max_workers <= 1:
            # Sequential execution
            for agent in agents_of_type:
                for domain in domains:
                    try:
                        results = agent.run(round_num, domain)
                        discoveries.extend(results)
                    except Exception as e:
                        if self.config.get('verbose'):
                            print(f"    ⚠ {agent.agent_id}/{domain}: {e}")
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for agent in agents_of_type:
                    for domain in domains:
                        future = executor.submit(agent.run, round_num, domain)
                        futures[future] = (agent.agent_id, domain)

                for future in as_completed(futures):
                    aid, domain = futures[future]
                    try:
                        results = future.result()
                        discoveries.extend(results)
                    except Exception as e:
                        if self.config.get('verbose'):
                            print(f"    ⚠ {aid}/{domain}: {e}")

        return discoveries

    def _print_round_summary(self, rnd: int, discoveries: List[Discovery],
                               elapsed: float):
        stats = self.blackboard.get_stats()
        print(f"  ✓ Round {rnd} complete: {len(discoveries)} new discoveries "
              f"({elapsed:.1f}s)")
        print(f"    Total: {stats['total_discoveries']} discoveries "
              f"| Validated: {stats.get('total_validated', 0)} "
              f"| Falsified: {stats.get('total_falsified', 0)}")

        for domain in self.DOMAINS:
            ds = self.blackboard.get_domain_summary(domain)
            if ds['count'] > 0:
                top = ds.get('top_3', [])
                top_str = ', '.join(f"{t[1]}({t[2]:.2f})" for t in top[:2])
                print(f"    {domain:15s}: {ds['count']:3d} items, "
                      f"avg conf={ds['avg_confidence']:.2f}, top=[{top_str}]")

    def _generate_final_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive final report."""
        stats = self.blackboard.get_stats()
        top_discoveries = self.blackboard.get_top_discoveries(20)

        # Per-domain summaries
        domain_reports = {}
        for domain in self.DOMAINS:
            summary = self.blackboard.get_domain_summary(domain)
            proof_sketches = self.blackboard.query(domain=domain,
                                                    category='proof_sketch', limit=10)
            breakthroughs = self.blackboard.query(domain=domain,
                                                   min_confidence=0.8, limit=10)
            domain_reports[domain] = {
                'summary': summary,
                'proof_sketches': [d.to_dict() for d in proof_sketches],
                'breakthroughs': [d.to_dict() for d in breakthroughs],
            }

        # Agent performance
        agent_stats = {}
        for aid, agent in self.agents.items():
            agent_stats[aid] = {
                'type': agent.agent_type,
                'rounds': agent.stats['rounds'],
                'discoveries': agent.stats['discoveries'],
                'time_spent': round(agent.stats['time_spent'], 2),
            }

        return {
            'total_time': round(total_time, 2),
            'rounds_completed': self.round_num,
            'global_stats': stats,
            'domain_reports': domain_reports,
            'agent_stats': agent_stats,
            'top_discoveries': [d.to_dict() for d in top_discoveries],
            'results_log': self.results_log,
            'preregistration_hash': self.blackboard.compute_preregistration_hash(),
        }

    def _print_final_report(self, report: Dict):
        print("\n" + "=" * 72)
        print("  FINAL REPORT")
        print("=" * 72)
        print(f"  Total time: {report['total_time']:.1f}s")
        print(f"  Rounds: {report['rounds_completed']}")
        print(f"  Total discoveries: {report['global_stats']['total_discoveries']}")
        print(f"  Validated: {report['global_stats'].get('total_validated', 0)}")
        print(f"  Falsified: {report['global_stats'].get('total_falsified', 0)}")
        print(f"  Pre-registration hash: {report['preregistration_hash'][:16]}...")

        for domain in self.DOMAINS:
            dr = report['domain_reports'].get(domain, {})
            summary = dr.get('summary', {})
            print(f"\n  {'─' * 50}")
            print(f"  {domain.upper().replace('_', '–')}")
            print(f"  {'─' * 50}")
            print(f"    Discoveries: {summary.get('count', 0)}")
            print(f"    Max confidence: {summary.get('max_confidence', 0):.3f}")
            print(f"    Proof sketches: {len(dr.get('proof_sketches', []))}")
            print(f"    Breakthroughs: {len(dr.get('breakthroughs', []))}")

            # Show top discoveries
            for bd in dr.get('breakthroughs', [])[:3]:
                print(f"    ★ [{bd['category']}] conf={bd['confidence']:.2f}: "
                      f"{bd['content'].get('description', bd['content'].get('type', ''))[:60]}")

        print("\n" + "=" * 72)

"""
NEXUS-OMEGA (APEX-1) - Scientific Self-Improvement Optimizer
Implements single-variable mutation testing against mathematical performance baselines.
Persists accepted mutations to the parameter learning ledger.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("APEX1.Optimizer")


class ScientificOptimizer:
    """
    Implements the autonomous self-improvement loop using the scientific method:
    1. Observe failure metric.
    2. Generate single-variable hypothesis mutation.
    3. Test mutated parameter against baseline score.
    4. Commit if improvement; revert otherwise.
    5. Persist all experiments to the parameter_learning_ledger.
    """

    # Default operational parameter baseline
    DEFAULT_PARAMETERS = {
        "temperature": 0.4,
        "retry_limit": 3,
        "search_depth": 5,
        "chunk_size": 512,
        "max_tokens": 2048,
        "scraper_timeout": 10,
        "backoff_factor": 1.5,
    }

    # Performance thresholds
    THRESHOLDS = {
        "compile_rate": 1.0,       # C ∈ [0, 1]
        "sharpe_ratio": 1.0,       # S >= 1.0
        "latency_ms": 200.0,       # L <= 200ms
        "success_rate": 0.85,      # >= 85%
    }

    def __init__(self, memory_store=None):
        self.parameters = self.DEFAULT_PARAMETERS.copy()
        self.baseline_score: float = 0.75
        self.total_experiments: int = 0
        self.adoptions: int = 0
        self._memory = memory_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_mutation(self, failing_metric: str) -> Dict[str, Any]:
        """
        Produce a single-variable mutation hypothesis based on the failing metric.
        Only one parameter is altered per experiment cycle.
        """
        logger.info(f"[Optimizer] Generating mutation for metric: {failing_metric}")
        mutated = self.parameters.copy()

        # Mutation rulebook — one rule per metric
        mutation_map = {
            "low_accuracy": {
                "variable": "temperature",
                "new_value": max(0.05, round(self.parameters["temperature"] - 0.1, 2)),
                "hypothesis": "Reducing temperature decreases hallucination variance and improves factual accuracy.",
            },
            "high_latency": {
                "variable": "max_tokens",
                "new_value": max(512, self.parameters["max_tokens"] - 256),
                "hypothesis": "Reducing max_tokens cap lowers generation time and brings latency within threshold.",
            },
            "low_coverage": {
                "variable": "search_depth",
                "new_value": self.parameters["search_depth"] + 2,
                "hypothesis": "Increasing search depth expands contextual coverage and recall.",
            },
            "scraper_failure": {
                "variable": "scraper_timeout",
                "new_value": self.parameters["scraper_timeout"] + 5,
                "hypothesis": "Extending scraper timeout reduces network-induced failures on slow targets.",
            },
            "retry_exhaustion": {
                "variable": "retry_limit",
                "new_value": self.parameters["retry_limit"] + 1,
                "hypothesis": "Adding one retry cycle improves success rate on transient provider errors.",
            },
        }

        rule = mutation_map.get(failing_metric, {
            "variable": "backoff_factor",
            "new_value": round(min(5.0, self.parameters["backoff_factor"] + 0.5), 2),
            "hypothesis": "Increasing backoff factor reduces rate-limit collisions.",
        })

        variable = rule["variable"]
        new_value = rule["new_value"]
        mutated[variable] = new_value

        self.total_experiments += 1
        return {
            "experiment_id": self.total_experiments,
            "tested_variable": variable,
            "previous_value": self.parameters[variable],
            "mutated_value": new_value,
            "mutated_parameters": mutated,
            "hypothesis": rule["hypothesis"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def evaluate_and_commit(
        self,
        experiment: Dict[str, Any],
        observed_score: float,
        agent_id: Optional[str] = None,
    ) -> bool:
        """
        Compare observed_score against baseline.
        Adopt mutation if score improves; revert otherwise.
        Persist outcome to ledger.
        """
        variable = experiment["tested_variable"]
        adopted = observed_score > self.baseline_score

        if adopted:
            self.parameters[variable] = experiment["mutated_value"]
            old_baseline = self.baseline_score
            self.baseline_score = observed_score
            self.adoptions += 1
            logger.info(
                f"[Optimizer] ✓ Hypothesis confirmed. Score {old_baseline:.4f} → {observed_score:.4f}. "
                f"Adopting {variable}={experiment['mutated_value']}"
            )
        else:
            logger.info(
                f"[Optimizer] ✗ Hypothesis rejected. Observed {observed_score:.4f} ≤ baseline {self.baseline_score:.4f}. "
                f"Reverting {variable} to {experiment['previous_value']}"
            )

        # Persist to persistent ledger (Postgres or SQLite fallback)
        if self._memory:
            try:
                await self._memory.persist_ledger_entry(experiment, observed_score, adopted, self.baseline_score, agent_id)
            except Exception as exc:
                logger.error(f"Ledger persistence error: {exc}")

        return adopted

    def compute_composite_score(
        self,
        compile_rate: float = 1.0,
        latency_ms: float = 150.0,
        sharpe_ratio: float = 1.2,
        success: bool = True,
    ) -> float:
        """
        Mathematical composite benchmark function:
        Scores performance against compile_rate, latency_ms, and sharpe_ratio.
        """
        c_score = max(0.0, min(1.0, compile_rate))
        l_score = max(0.0, min(1.0, self.THRESHOLDS["latency_ms"] / max(1.0, latency_ms)))
        s_score = max(0.0, min(1.0, sharpe_ratio / self.THRESHOLDS["sharpe_ratio"]))

        composite = 0.4 * c_score + 0.3 * l_score + 0.3 * s_score
        if not success:
            composite *= 0.5
        return round(composite, 4)

    def get_current_parameters(self) -> Dict[str, Any]:
        """Return the current production parameter set."""
        return self.parameters.copy()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_experiments": self.total_experiments,
            "adoptions": self.adoptions,
            "rejection_rate": round(
                1.0 - (self.adoptions / self.total_experiments) if self.total_experiments > 0 else 0.0,
                4,
            ),
            "current_baseline_score": self.baseline_score,
            "active_parameters": self.parameters,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _persist_ledger_entry(
        self,
        experiment: Dict[str, Any],
        observed_score: float,
        is_adopted: bool,
        agent_id: Optional[str],
    ):
        try:
            if not self._memory or not getattr(self._memory, '_pool', None): return
            async with self._memory._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO parameter_learning_ledger
                        (agent_id, metric_name, variable_mutated, previous_value, mutated_value,
                         baseline_score, observed_score, hypothesis, is_adopted)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    agent_id,
                    "composite_performance",
                    experiment["tested_variable"],
                    str(experiment["previous_value"]),
                    str(experiment["mutated_value"]),
                    self.baseline_score,
                    observed_score,
                    experiment["hypothesis"],
                    is_adopted,
                )
        except Exception as exc:
            logger.error(f"Ledger persistence error: {exc}")

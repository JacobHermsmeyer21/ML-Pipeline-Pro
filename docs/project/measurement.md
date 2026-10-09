# Measurement criteria

These research targets are separate from [course acceptance](course-requirements.md).
No improvement percentage is established by planning or functional test counts.

Treat all supplied resume percentages as hypotheses until measured. Establish baselines before optimizations and preserve benchmark scripts, environment details, raw results, and limitations.

| Claim to evaluate | Metric and experiment |
| --- | --- |
| 10x faster retrieval | Baseline median and p95 query latency divided by optimized latency on the same dataset, hardware, queries, and cache conditions |
| 30% less tuning time | Reduction in elapsed time to a fixed validation-quality threshold, across multiple seeds with equal resource budgets |
| 40% less debugging time | Reduction in time to correctly diagnose and resolve comparable seeded faults, with sample size and unresolved tasks reported |
| 25% higher coding efficiency | Define efficiency first; measure correct completed integration tasks per hour and report defects and review time |
| 50% higher model throughput | Increase in successful completed model workflows per hour under fixed compute, task mix, and quality requirements |

For reduction metrics, use `(baseline - assisted) / baseline`. For throughput improvements, use `(assisted - baseline) / baseline`. Report spread across runs and confidence intervals where sample sizes support them. Record failures, compute/resource usage, and known operating costs alongside speed; label unknown costs. State how human tasks were assigned to control for learning effects.

Only write resume bullets in the past tense after the relevant capability exists. Attach measured quantitative claims to their benchmark conditions. Until then, describe the platform as planned or in development.

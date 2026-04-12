# Cost Model — DataForSEO API

Reference document for pricing ContentFlow. Last updated: 2026-03-29.

## How DataForSEO bills

**Per task, not per keyword.** A single task can contain up to 1,000 keywords.

| Queue | Price/task | Latency | Use case |
|-------|-----------|---------|----------|
| Standard | $0.05 | 5-30s (async) | Scheduled pipelines, batch jobs |
| Live | $0.075 | 1-3s (sync) | Interactive, real-time needs |

All ContentFlow scheduled jobs use **Standard queue** by default.

## Cost per pipeline

### ingest_seo (keyword discovery)

| Step | API endpoint | Tasks | Cost (Standard) |
|------|-------------|-------|-----------------|
| keyword_ideas | Labs > Keyword Ideas | **1** (all seeds batched) | $0.05 |
| keyword_suggestions | Labs > Keyword Suggestions | N (1 per seed, max 3) | $0.15 |
| **Total per run** | | ~4 tasks | **$0.20** |

### enrich_ideas (batch enrichment)

| Step | API endpoint | Tasks | Cost (Standard) |
|------|-------------|-------|-----------------|
| keyword_overview | Labs > Keyword Overview | **1** (up to 1,000 keywords) | $0.05 |
| **Total per run** | | 1 task | **$0.05** |

### ingest_competitors (gap analysis)

| Step | API endpoint | Tasks | Cost (Standard) |
|------|-------------|-------|-----------------|
| domain_intersection | Labs > Domain Intersection | 1 | $0.05 |
| ranked_keywords | Labs > Ranked Keywords | N (1 per competitor, max 3) | $0.15 |
| **Total per run** | | ~4 tasks | **$0.20** |

### track_serp (position tracking)

| Step | API endpoint | Tasks | Cost (Standard) |
|------|-------------|-------|-----------------|
| SERP organic | SERP > Google Organic | N (1 per published article) | N x $0.05 |
| **Total per run** | | N tasks | **$0.05 x N articles** |

Example: 50 articles = $2.50/run.

## Scaling projections

### Per project (typical weekly schedule)

| Pipeline | Frequency | Cost/run | Cost/month |
|----------|-----------|----------|------------|
| ingest_seo | 1x/week | $0.20 | $0.80 |
| enrich_ideas | 1x/week | $0.05 | $0.20 |
| ingest_competitors | 1x/week | $0.20 | $0.80 |
| track_serp (20 articles) | 1x/week | $1.00 | $4.00 |
| **Total per project** | | | **~$5.80/month** |

### Platform scale

| Users (projects) | Monthly DFS cost | Per-user cost |
|-------------------|-----------------|---------------|
| 10 | ~$58 | $5.80 |
| 100 | ~$580 | $5.80 |
| 1,000 | ~$5,800 | $5.80 |

Cost scales **linearly** with number of projects. No volume discounts from DFS (as of March 2026).

Track_serp is the biggest variable: scales with number of published articles per project.

## How to query actual costs

```python
from status.cost_tracker import get_cost_summary, get_cost_per_project

# Total costs over last 30 days
summary = get_cost_summary()
print(f"Total: ${summary['total_cost']}")
print(f"Tasks: {summary['total_api_tasks']}")

# Per project (for pricing decisions)
for p in get_cost_per_project():
    print(f"{p['project_id']}: ${p['total_cost']} ({p['total_job_runs']} runs)")

# Filter by project and date range
summary = get_cost_summary(
    project_id="proj-123",
    since="2026-03-01",
    until="2026-03-31",
)
```

Data is persisted in `data/status/status.db` table `api_cost_log`, populated automatically by the scheduler after each DFS job.

## Optimizations in place

1. **Keyword batching** — keyword_ideas sends all seeds in 1 task (not N)
2. **Suggestion batching** — keyword_suggestions sends all seeds in 1 POST
3. **SERP batch submit** — all SERP tasks submitted in 1 POST via Standard queue
4. **Standard queue default** — all scheduled jobs use $0.05/task, not $0.075
5. **Cost tracking** — every DFS job logs estimated cost to SQLite

## Pricing implications

To break even on DFS costs at ~$5.80/project/month:

| Pricing model | Break-even |
|--------------|------------|
| $9/month | 62% margin |
| $19/month | 69% margin |
| $49/month | 88% margin |

DFS API cost is a **small fraction** of total COGS (LLM calls for content generation dominate). This doc covers DFS only.

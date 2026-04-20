# AGENTS.md

This file provides guidance for AI agents working in the contentflow codebase. It documents commands, patterns, conventions, and gotchas specific to this multi-component automation system.

---

## Project Overview

This is a **multi-component intelligent automation system** with three major subsystems:

1. **Python SEO Robots** - Multi-agent CrewAI system for SEO optimization (FastAPI backend)
2. **Next.js Chatbot** - AI chatbot with artifact generation, topical mesh integration
3. **Astro Website** - Static site for content deployment

The system uses a **hybrid stack**:
- **Backend**: Python 3.11 (CrewAI, PydanticAI, FastAPI, STORM, advertools)
- **Frontend**: Next.js 16 + React 19 RC (TypeScript strict mode)
- **Website**: Astro 4.x
- **Environment**: Flox for declarative dependencies + Doppler for secrets management

---

## Essential Commands

### Python Development (SEO Robots & API)

#### Environment Setup
```bash
# Activate Flox environment (provides Python, system libs, etc.)
flox activate

# Install Python dependencies
pip install -r requirements.txt

# Sync .env to Doppler (one-time setup)
./sync_env_to_doppler.sh

# Run with Doppler (recommended)
doppler run -- python main.py
doppler run -- uvicorn api.main:app --reload --port 8000
```

#### Running SEO Agents
```bash
# Main entry point
python main.py

# FastAPI server (REST API + WebSocket)
uvicorn api.main:app --reload --port 8000
# Docs: http://localhost:8000/docs (Swagger)
# ReDoc: http://localhost:8000/redoc

# Run individual tests
python test_research_analyst.py
python test_topical_mesh.py
python test_storm_integration.py

# Run with proper library paths (if numpy/pandas issues)
./run_seo_tools.sh python test_advertools.py
```

#### Testing
```bash
# No pytest.ini found - tests are individual Python scripts
python test_research_analyst.py
python test_seo_system.py
python test_existing_mesh.py
python test_topical_mesh_simple.py
```

### Next.js Chatbot (chatbot/ directory)

```bash
cd chatbot

# Development
pnpm install              # Install dependencies
pnpm dev                  # Start dev server (localhost:3000, turbo mode)
pnpm build                # Build for production (runs DB migrations first)
pnpm start                # Production server

# Database (Drizzle ORM + Neon PostgreSQL)
pnpm db:generate          # Generate types from schema
pnpm db:migrate           # Run migrations
pnpm db:studio            # Open Drizzle Studio (localhost:5555)
pnpm db:push              # Push schema to database
pnpm db:pull              # Pull schema from database

# Code Quality (Ultracite - Biome-based linter)
pnpm lint                 # Check with Ultracite
pnpm format               # Auto-fix formatting & a11y issues

# Testing (Playwright e2e)
pnpm test                 # Run Playwright tests
```

### Astro Website (website/ directory)

```bash
cd website

pnpm install              # Install dependencies
pnpm dev                  # Dev server
pnpm start                # Alias for dev
pnpm build                # Build static site
pnpm preview              # Preview production build
```

### Deployment

```bash
# Railway (Python API)
# Uses railway.toml config
# Deploy: git push (auto-deploy on main branch)

# Render (Python API)
# Uses render.yaml config
# Health check: /health endpoint

# PM2 (manual server management)
pm2 start ecosystem.config.cjs
pm2 status
pm2 logs contentflow
pm2 restart contentflow
```

---

## Production DB (Turso / libSQL) — Critical Gotcha

- Turso uses **SQLite (libSQL/Hrana)**, not MySQL/Postgres.
- Any backend change that depends on **new tables/columns/indexes** must ship with a **schema migration** (or at minimum an idempotent `CREATE TABLE IF NOT EXISTS ...` on startup).
- Symptom when you forget: runtime errors like `SQLite error: no such table: UserSettings`, which can cascade into 502s and app flows (onboarding/project selection) that appear "stuck" or reset on every login.

**Rule of thumb**
- New table (simple): add `ensure_*_table()` and call it during FastAPI startup (idempotent).
- Column/constraint/backfill: add a versioned SQL migration and apply it as part of the deploy.

### Secrets Management (Doppler)

```bash
# Initial setup
doppler login
doppler setup              # Select project: contentflow, config: dev

# View secrets
doppler secrets

# Set secrets interactively
doppler secrets set API_KEY

# Upload from .env
doppler secrets upload .env

# Run commands with Doppler
doppler run -- python main.py
doppler run -- uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Git Workflow

**CRITICAL**: This repository uses `main` branch (NOT `master`).

```bash
# Checkout main branch
git checkout main
git pull origin main

# Current status (from git snapshot at conversation start)
# Modified files:
#   - chatbot/app/(chat)/api/chat/route.ts
#   - chatbot/drizzle.config.ts
#   - chatbot/package.json
#   - chatbot/pnpm-lock.yaml
# Untracked files:
#   - Multiple .md documentation files
#   - chatbot/app/dashboard/
#   - chatbot/components/dashboard/
#   - ecosystem.config.cjs
#   - website/src/content/
```

---

## Code Organization & Structure

### Root Structure

```
/root/contentflow_lab/
├── agents/                    # CrewAI SEO agents (active implementation)
│   ├── seo/
│   │   ├── research_analyst.py
│   │   ├── content_strategist.py
│   │   ├── copywriter.py
│   │   ├── editor.py
│   │   ├── marketing_strategist.py
│   │   ├── technical_seo.py
│   │   ├── topical_mesh_architect.py
│   │   ├── tools/              # @tool decorated functions
│   │   ├── schemas/            # Pydantic validation schemas
│   │   └── config/
│   ├── seo_research_tools.py
│   └── seo_topic_agent.py
├── api/                       # FastAPI backend
│   ├── main.py                # Server entry point
│   ├── routers/               # REST endpoints
│   │   ├── health.py
│   │   ├── mesh.py
│   │   └── research.py
│   ├── models/                # Pydantic models
│   └── dependencies/          # DI container for agents
├── utils/
│   ├── llm_config.py          # OpenRouter LLM configuration
│   ├── llm_simple.py
│   └── reporting.py
├── chatbot/                   # Next.js 16 AI chatbot
│   ├── app/                   # App Router (Next.js 16)
│   │   ├── (chat)/
│   │   ├── (auth)/
│   │   └── dashboard/         # SEO dashboard integration
│   ├── components/            # React components
│   │   ├── dashboard/         # Dashboard-specific
│   │   └── ui/                # shadcn/ui components
│   ├── lib/
│   │   ├── ai/                # Vercel AI SDK integration
│   │   │   ├── models.ts
│   │   │   ├── providers.ts
│   │   │   ├── tools/
│   │   │   └── prompts.ts
│   │   └── db/                # Drizzle ORM
│   │       ├── schema.ts
│   │       ├── queries.ts
│   │       └── migrations/
│   ├── artifacts/             # Artifact renderers
│   └── .cursor/rules/         # Ultracite linter rules
├── website/                   # Astro static site
│   └── src/
│       ├── content/           # Blog & docs content
│       │   ├── blog/
│       │   ├── docs/
│       │   └── use-cases/
│       ├── components/
│       ├── layouts/
│       └── pages/
├── docs/                      # Architecture docs
├── robots/                    # Agent specification docs
├── workflows/                 # Integrated workflows
├── examples/                  # Usage examples
├── data/                      # Generated data
├── main.py                    # Python entry point
├── requirements.txt           # Python dependencies
└── test_*.py                  # Test scripts
```

### Agent Architecture Pattern

**SEO Agents** follow this structure:
```python
agents/seo/
├── {agent_name}.py            # Agent class definition
├── tools/
│   ├── {domain}_tools.py      # @tool decorated functions
│   └── __init__.py
├── schemas/
│   ├── {domain}_schemas.py    # Pydantic models
│   └── __init__.py
└── config/
    ├── {agent}_config.py      # Configuration
    └── __init__.py
```

**CrewAI Agent Definition Pattern**:
```python
from crewai import Agent, Task
from agents.seo.tools.research_tools import analyze_serp_tool

agent = Agent(
    role="SEO Research Analyst",
    goal="Conduct comprehensive competitive intelligence...",
    backstory="You are an expert SEO analyst with 10+ years...",
    tools=[analyze_serp_tool, monitor_trends_tool],
    llm=self.llm,
    verbose=True,
    allow_delegation=False
)
```

**Tool Pattern**:
```python
from crewai.tools import tool

@tool
def analyze_serp_tool(keyword: str, location: str = "United States") -> dict:
    """
    Analyze SERP results for a keyword.
    
    Args:
        keyword: Target keyword to analyze
        location: Geographic location
        
    Returns:
        Comprehensive SERP analysis
    """
    analyzer = SERPAnalyzer()
    return analyzer.analyze_serp(keyword, location)
```

---

## Naming Conventions

### Python (SEO Agents)

- **Modules**: `snake_case` (e.g., `research_analyst.py`, `research_tools.py`)
- **Classes**: `PascalCase` (e.g., `ResearchAnalystAgent`, `SERPAnalyzer`)
- **Functions**: `snake_case` (e.g., `analyze_serp`, `create_analysis_task`)
- **Tool Functions**: `{verb}_{noun}_tool` (e.g., `analyze_serp_tool`, `monitor_trends_tool`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODEL`, `API_BASE_URL`)
- **Private Methods**: `_leading_underscore` (e.g., `_initialize_llm`, `_search_google`)

### TypeScript (Chatbot)

- **Components**: `PascalCase` (e.g., `ChatHeader`, `ArtifactMessages`)
- **Functions**: `camelCase` (e.g., `saveChatModelAsCookie`, `generateTitleFromUserMessage`)
- **Server Actions**: `verb + Noun` (e.g., `deleteTrailingMessages`, `voteMessage`)
- **Database Queries**: `verb + By + FilterField` (e.g., `getMessageById`, `getChatsByUserId`)
- **Hooks**: `use + PascalCase` (e.g., `useArtifact`, `useAutoResume`)
- **Files**: `kebab-case` for routes, `PascalCase` for components

**Type Imports** (Ultracite requirement):
```typescript
// ✅ Correct
import type { User } from '@/lib/types';
import { config } from '@/lib/config';

// ❌ Wrong
import { User, config } from '@/lib/types';
```

---

## Testing Approach

### Python Tests

**Pattern**: Individual test scripts (no pytest framework detected)

```bash
# Tests are executable Python scripts
python test_research_analyst.py
python test_topical_mesh.py
python test_storm_integration.py
```

**Test Script Pattern**:
```python
"""
Test script for Research Analyst Agent.
Validates SERP analysis, trend monitoring, and keyword gap identification.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_serp_analysis():
    print("\n" + "="*60)
    print("TEST 1: SERP Analysis")
    print("="*60)
    
    analyzer = SERPAnalyzer()
    result = analyzer.analyze_serp("python tutorial")
    
    if 'error' in result:
        print(f"\n❌ ERROR: {result['error']}")
        return False
    
    print("\n✅ SERP Analysis: PASSED")
    return True

if __name__ == "__main__":
    test_serp_analysis()
```

### TypeScript Tests (Chatbot)

**Framework**: Playwright e2e tests

```bash
cd chatbot
pnpm test  # Sets PLAYWRIGHT=True env var
```

**Test Files**:
```
chatbot/tests/
├── e2e/
│   ├── artifacts.test.ts
│   ├── chat.test.ts
│   ├── reasoning.test.ts
│   └── session.test.ts
├── routes/
│   ├── chat.test.ts
│   └── document.test.ts
├── fixtures.ts
└── helpers.ts
```

---

## Important Patterns & Conventions

### 1. LLM Configuration (OpenRouter Integration)

**Pattern**: Use centralized `utils/llm_config.py` for all LLM access

```python
from utils.llm_config import LLMConfig, get_balanced_llm

# Recommended: Use tier-based selection
llm = LLMConfig.get_llm("balanced")  # Claude 3.5 Sonnet
llm = LLMConfig.get_llm("fast")      # Llama 3 70B
llm = LLMConfig.get_llm("premium")   # Claude 3 Opus

# Or: Use convenience functions
llm = get_balanced_llm(temperature=0.7)
```

**Available Tiers**:
- `"fast"` - meta-llama/llama-3-70b-instruct ($0.59/$0.79 per 1M tokens)
- `"cheap"` - mistralai/mixtral-8x7b-instruct ($0.24/$0.24)
- `"balanced"` - anthropic/claude-3.5-sonnet ($3/$15) **[DEFAULT]**
- `"premium"` - anthropic/claude-3-opus ($15/$75)
- `"best"` - openai/gpt-4-turbo ($10/$30)
- `"groq-fast"` - groq/llama-3-70b-8192 (fallback)

**Why OpenRouter**: 50-90% cheaper than direct APIs, single API key for all providers.

### 2. Pydantic Schema Validation

**Pattern**: All structured data uses Pydantic models

**Python Agents**:
```python
# Define schema
from pydantic import BaseModel, Field

class SERPAnalysis(BaseModel):
    keyword: str
    search_intent: str
    competitive_score: int = Field(ge=0, le=10)
    top_competitors: list[dict]

# Use in agent
result = SERPAnalysis(**data)  # Validates automatically
```

**Next.js (Zod)**:
```typescript
import { z } from 'zod';

const messageSchema = z.object({
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string(),
  parts: z.array(z.object({
    type: z.string(),
    content: z.any()
  }))
});
```

### 3. Flox Environment Management

**Pattern**: Use Flox for system dependencies, venv for Python packages

```bash
# Flox provides: Python 3.11, gcc, zlib, system libraries
flox activate

# Python packages installed via pip in venv
source venv/bin/activate
pip install -r requirements.txt

# Library path issues (numpy/pandas)
# Use wrapper script:
./run_seo_tools.sh python test_advertools.py
```

**Why**: Flox ensures consistent system dependencies across environments without Docker.

### 4. Doppler Secrets Management

**Pattern**: Never commit secrets, always use Doppler

```bash
# Setup (one-time)
doppler login
doppler setup  # Select: contentflow / dev

# Use in development
doppler run -- python main.py
doppler run -- uvicorn api.main:app --reload

# Migration from .env
./sync_env_to_doppler.sh
```

**Required Secrets**:
- `OPENROUTER_API_KEY` (recommended - 50-90% cheaper)
- `GROQ_API_KEY` (fallback)
- `EXA_API_KEY` (newsletter, research)
- `FIRECRAWL_API_KEY` (article crawler)
- `YDC_API_KEY` (You.com for STORM)
- `SERP_API_KEY` (SERP analysis)
- Optional: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

### 5. FastAPI Server Pattern

**Entry Point**: `api/main.py`

```python
# Lifespan events (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load agents into memory
    print("🚀 Starting SEO Robots API...")
    yield
    # Shutdown: Cleanup
    print("👋 Shutting down...")

app = FastAPI(
    title="SEO Robots API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(health_router)
app.include_router(mesh_router)
app.include_router(research_router)
```

**Dependency Injection Pattern**:
```python
# api/dependencies/agents.py
_mesh_architect = None

def get_mesh_architect() -> TopicalMeshArchitect:
    global _mesh_architect
    if _mesh_architect is None:
        _mesh_architect = TopicalMeshArchitect()
    return _mesh_architect

# Use in routes
from fastapi import Depends

@router.post("/analyze")
async def analyze_mesh(
    architect: TopicalMeshArchitect = Depends(get_mesh_architect)
):
    result = architect.analyze(...)
    return result
```

### 6. Next.js Artifact Pattern (Chatbot)

**Pattern**: AI generates UI components via structured streaming

```typescript
// Artifact metadata streamed first
{
  kind: 'code' | 'text' | 'image' | 'sheet',
  id: string,
  title: string
}

// Then content streamed incrementally
{
  type: 'codeDelta' | 'textDelta' | 'imageDelta' | 'sheetDelta',
  content: string
}
```

**Routing** (`components/artifact.tsx`):
```typescript
switch (artifact.kind) {
  case 'code':
    return <CodeArtifact {...props} />;
  case 'text':
    return <TextArtifact {...props} />;
  case 'image':
    return <ImageArtifact {...props} />;
  case 'sheet':
    return <SheetArtifact {...props} />;
}
```

### 7. Ultracite Linting (Chatbot Only)

**Critical Rules** (from `.cursor/rules/ultracite.mdc`):

#### Accessibility
- ✅ Always include `type` attribute for buttons
- ✅ Use semantic HTML (`<button>`, `<nav>`, `<main>`) instead of `<div role="button">`
- ✅ Include `alt` text for images (don't say "image" or "picture")
- ✅ Accompany `onClick` with keyboard handlers (`onKeyUp`/`onKeyDown`)
- ❌ No positive `tabIndex` values
- ❌ No `aria-hidden` on focusable elements

#### Code Quality
- ✅ Use `for...of` instead of `Array.forEach`
- ✅ Use arrow functions instead of function expressions
- ✅ Use `import type` for type-only imports
- ✅ Use `as const` for literal arrays/objects
- ❌ No enums (use `as const` objects)
- ❌ No `arguments` object
- ❌ No unnecessary boolean casts

#### React/JSX
- ✅ Use shorthand boolean props: `<Component enabled />` not `<Component enabled={true} />`
- ❌ Don't pass `children` as props
- ❌ No JSX spread props

**Pattern**:
```typescript
// ✅ Correct
import type { User } from '@/lib/types';
const ROLES = ['admin', 'user'] as const;
type Role = typeof ROLES[number];

// ❌ Wrong
import { User } from '@/lib/types';
enum Role { Admin = 'admin', User = 'user' }
```

---

## Important Gotchas & Non-Obvious Patterns

### 1. Git Branch: Use `main` NOT `master`

The CLAUDE.md file incorrectly references `master` branch. **The actual branch is `main`**.

```bash
# ❌ Wrong (from CLAUDE.md)
git checkout master

# ✅ Correct
git checkout main
```

### 2. Python Path Management

**Problem**: Agents in `agents/` need to import from root.

**Solution**: Add project root to sys.path
```python
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now can import from root
from utils.llm_config import LLMConfig
```

### 3. Library Path Issues (Flox + numpy/pandas)

**Problem**: numpy/pandas can't find `libstdc++.so.6` or `libz.so.1`

**Solution**: Use wrapper script `run_seo_tools.sh`
```bash
# ❌ May fail
python test_advertools.py

# ✅ Correct
./run_seo_tools.sh python test_advertools.py
```

**What it does**: Sets `LD_LIBRARY_PATH` to include Flox-provided system libraries.

### 4. Next.js Message Hydration (Chatbot)

**Problem**: Message shape inconsistency causes hydration errors.

**Solution**: Always use `generateUUID()` for message IDs
```typescript
import { generateUUID } from '@/lib/utils';

const message = {
  id: generateUUID(),  // ✅ Not Math.random() or Date.now()
  role: 'user',
  content: '...'
};
```

### 5. Streaming Data Parts (Chatbot)

**Problem**: Custom UI streams must be declared in `CustomUIDataTypes`.

**Solution**: Add to `lib/types.ts`
```typescript
export type CustomUIDataTypes = {
  textDelta: {
    type: 'textDelta';
    content: string;
  };
  // Add new types here
  myCustomDelta: {
    type: 'myCustomDelta';
    content: MyCustomData;
  };
};
```

### 6. CrewAI Agent Tool Functions

**Pattern**: Must be decorated with `@tool` from `crewai.tools`

```python
from crewai.tools import tool

# ✅ Correct
@tool
def analyze_serp_tool(keyword: str) -> dict:
    """Docstring required for tool description."""
    return SERPAnalyzer().analyze_serp(keyword)

# ❌ Wrong - no @tool decorator
def analyze_serp(keyword: str) -> dict:
    return SERPAnalyzer().analyze_serp(keyword)
```

### 7. Doppler vs .env Files

**Production Pattern**: Always use Doppler, never commit .env

**Development**:
```bash
# Option 1: Doppler (recommended)
doppler run -- python main.py

# Option 2: .env (local only, not committed)
python main.py  # Loads .env via python-dotenv

# Migration path
./sync_env_to_doppler.sh
rm .env  # Delete after migration
```

### 8. FastAPI CORS Configuration

**Problem**: Next.js frontend can't call API endpoints.

**Solution**: Configure CORS middleware
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js dev
        "https://*.vercel.app",       # Vercel preview/prod
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 9. Pydantic vs Zod Schema Mismatch

**Problem**: Python API returns Pydantic models, TypeScript expects Zod shapes.

**Pattern**: Use `InferSelectModel` for DB types, manual typing for API responses
```typescript
// Drizzle DB types
import type { InferSelectModel } from 'drizzle-orm';
type Message = InferSelectModel<typeof messages>;

// API response types (manually defined)
type SERPAnalysis = {
  keyword: string;
  search_intent: string;
  competitive_score: number;
};
```

### 10. STORM Integration Requires You.com API

**Critical**: STORM research agent requires `YDC_API_KEY` (You.com Developer API)

```bash
# Get API key: https://api.you.com
doppler secrets set YDC_API_KEY=your_key_here

# STORM won't work without this
python test_storm_integration.py
```

### 11. Topical Mesh Visualization

**Pattern**: NetworkX + matplotlib for graph-based SEO analysis

```python
from agents.seo_topic_agent import SEOTopicAgent

agent = SEOTopicAgent()
mesh = agent.build_topical_mesh(main_topic="Digital Marketing")

# Generates:
# - Network graph (NetworkX)
# - Authority scores (PageRank)
# - Community detection (Louvain)
# - Visualization (matplotlib)
```

### 12. Multi-Agent Workflow Orchestration

**Pattern**: Sequential workflow with hierarchical collaboration

```python
from crewai import Crew

crew = Crew(
    agents=[
        research_analyst,
        content_strategist,
        copywriter,
        technical_seo,
        marketing_strategist,
        editor  # Final harmonization
    ],
    tasks=[task1, task2, task3, ...],
    verbose=True
)

result = crew.kickoff()  # Agents collaborate sequentially
```

---

## Documentation References

### Architecture & Planning
- `docs/plan.md` - Overall vision, strategic objectives, integration specs
- `AGENTS.md` - Detailed agent specifications, workflows, quality metrics (this file)
- `docs/phases.md` - Development roadmap (6 phases)
- `docs/agents/robot-seo.md` - SEO robot framework
- `CLAUDE.md` - High-level architecture overview (NOTE: References wrong git branch)

### Integration Guides
- `docs/DOPPLER_INTEGRATION.md` - Doppler secrets setup
- `docs/DOPPLER_VS_ENV.md` - Why use Doppler
- `docs/FLOX_ARCHITECTURE.md` - Flox environment management
- `docs/GROQ_SETUP.md` - Groq API setup
- `docs/OPENROUTER_MIGRATION.md` - OpenRouter integration
- `docs/STORM_API_EXPLAINED.md` - STORM research agent
- `docs/RENDER_MCP_GUIDE.md` - Render deployment with MCP server

### Implementation Status
- `DEPLOYMENT_STATUS.md` - Current deployment state
- `IMPLEMENTATION_PROGRESS.md` - Feature completion tracking
- `PHASE_1_COMPLETE.md` - Infrastructure complete
- `RESEARCH_ANALYST_COMPLETE.md` - Research agent status
- `TOPICAL_MESH_COMPLETE.md` - Topical mesh status

### Chatbot-Specific
- `chatbot/docs/START-HERE.md` - Chatbot onboarding
- `chatbot/docs/architecture/README.md` - System architecture
- `chatbot/.github/copilot-instructions.md` - Comprehensive chatbot guide
- `chatbot/DASHBOARD_GUIDE.md` - SEO dashboard integration
- `chatbot/DATABASE_ARCHITECTURE.md` - DB schema & patterns

---

## Quick Reference

### Most Common Workflows

**Start Python API Server**:
```bash
doppler run -- uvicorn api.main:app --reload --port 8000
```

**Start Next.js Chatbot**:
```bash
cd chatbot && pnpm dev
```

**Run SEO Agent Test**:
```bash
doppler run -- ./run_seo_tools.sh python test_research_analyst.py
```

**Add New Secret**:
```bash
doppler secrets set NEW_SECRET_KEY
```

**Database Migration (Chatbot)**:
```bash
cd chatbot && pnpm db:migrate
```

**Check Code Quality (Chatbot)**:
```bash
cd chatbot && pnpm lint
```

### When Things Break

1. **Import errors in Python**: Add project root to `sys.path`
2. **numpy/pandas library errors**: Use `./run_seo_tools.sh`
3. **Doppler not configured**: Run `doppler setup`
4. **Next.js hydration errors**: Check message ID generation (`generateUUID()`)
5. **CORS errors**: Check FastAPI middleware config
6. **LLM errors**: Verify API keys in Doppler (`doppler secrets`)
7. **TypeScript errors (chatbot)**: Run `pnpm lint` and fix Ultracite issues

---

## Environment Variables Pattern

### Python (via Doppler)
```bash
# Core LLM
OPENROUTER_API_KEY=sk-or-...        # Recommended (50-90% cheaper)
GROQ_API_KEY=gsk_...                # Fallback/fast inference
OPENAI_API_KEY=sk-...               # Optional
ANTHROPIC_API_KEY=sk-ant-...        # Optional

# SEO & Research
SERP_API_KEY=...                    # SerpApi for SERP analysis
EXA_API_KEY=...                     # Exa AI for research
FIRECRAWL_API_KEY=...               # Firecrawl for crawling
YDC_API_KEY=...                     # You.com for STORM

# Email (Newsletter)
SENDGRID_API_KEY=...                # Email delivery

# Optional
APP_URL=https://contentflow.com        # For OpenRouter headers
```

### Next.js (chatbot/.env.local)
```bash
# Database
POSTGRES_URL=postgresql://...       # Neon PostgreSQL

# Auth
AUTH_SECRET=...                     # Next-Auth secret
AUTH_URL=http://localhost:3000      # Auth callback URL

# AI Models (Vercel AI Gateway)
XAI_API_KEY=...                     # xAI Grok models

# Storage
BLOB_READ_WRITE_TOKEN=...           # Vercel Blob
REDIS_URL=redis://...               # Redis for caching

# Optional
DOPPLER_TOKEN=...                   # If using Doppler
```

---

## Agent-Specific Context

### For Agents Working on Python SEO System

1. **Always use Doppler**: `doppler run -- python ...`
2. **Use OpenRouter**: Cheaper LLM access via `utils/llm_config.py`
3. **Follow CrewAI patterns**: `@tool` decorators, Agent + Task + Crew
4. **Validate with Pydantic**: All structured data needs schema validation
5. **Test individually**: `python test_research_analyst.py` (no pytest suite)
6. **Add to sys.path**: Import from root requires `sys.path.insert(0, str(project_root))`

#### SEO Tools — Link Validation

**`LocalLinkChecker`** (`agents/seo/tools/local_link_checker.py`)

Validates internal markdown links directly against the local filesystem — no HTTP, no deployed site needed.

| Parameter | Type | Description |
|---|---|---|
| `repo_path` | `str` | Absolute path to locally cloned repo |
| `content_dir` | `str` | Content directory relative to repo root (default: `"src/content"`) |

Returns: `{ success, source, files_analyzed, broken_links[], broken_links_count, valid_links_count, skipped_count, stats }`

**Link resolution strategy:**
- Fragment-only (`#section`) → skipped (unverifiable without rendered HTML)
- External (`http://`, `https://`, `mailto:`) → skipped (out of scope)
- Root-relative (`/foo/bar`) → resolved from `content_root`
- Relative (`../foo/bar`, `./foo`) → resolved from `source_file.parent`
- For each candidate: tries exact path, then `+ .md`, then `/ index.md`, then `.mdx` / `.astro`

**Integration in `SiteCrawler.detect_broken_links()`:**
- Pass `local_repo_path` to get local-first results (faster + pre-deploy)
- Omit `local_repo_path` to use HTTP crawl fallback (original behaviour)
- Result field `source` = `"local_filesystem"` or `"http_crawl"` to distinguish

**Quick test:**
```bash
cd /home/claude/contentflow_lab
python -c "
from agents.seo.tools.local_link_checker import LocalLinkChecker
checker = LocalLinkChecker()
result = checker.check_local_links('/home/claude/GoCharbon', 'src/content')
print(result)
"
```

### For Agents Working on Next.js Chatbot

1. **Strict TypeScript**: `tsconfig.json` has `strict: true`
2. **Follow Ultracite**: Run `pnpm lint` before committing
3. **Use type imports**: `import type { User }` not `import { User }`
4. **DB migrations first**: `pnpm db:migrate` before `pnpm build`
5. **Message shape matters**: Use `generateUUID()`, maintain `parts[]` structure
6. **Server Actions pattern**: `verb + Noun` naming (e.g., `deleteTrailingMessages`)
7. **Test with Playwright**: `pnpm test` for e2e validation

### For Agents Working on Astro Website

1. **Content-first**: Blog posts in `src/content/blog/`, docs in `src/content/docs/`
2. **Markdown-based**: Articles generated by SEO robots output to here
3. **Component-driven**: Astro components in `src/components/`
4. **Static build**: `pnpm build` generates static HTML

---

## Performance & Cost Optimization

### LLM Cost Tiers (via OpenRouter)

| Tier | Model | Cost (per 1M tokens) | Use Case |
|------|-------|---------------------|----------|
| cheap | Mixtral 8x7B | $0.24/$0.24 | Research, analysis, drafts |
| fast | Llama 3 70B | $0.59/$0.79 | Fast iteration, testing |
| balanced | Claude 3.5 Sonnet | $3/$15 | Content generation, editing |
| premium | Claude 3 Opus | $15/$75 | Complex reasoning |
| best | GPT-4 Turbo | $10/$30 | Final editing |

**Pattern**: Use cheaper models for research/analysis, balanced for content, premium for final QA.

```python
# Research phase: Use fast/cheap
llm = LLMConfig.get_llm("fast", temperature=0.3)

# Content generation: Use balanced
llm = LLMConfig.get_llm("balanced", temperature=0.7)

# Final editing: Use premium
llm = LLMConfig.get_llm("premium", temperature=0.5)
```

### Deployment Platforms

| Platform | Use Case | Config File |
|----------|----------|-------------|
| Railway | FastAPI backend | `railway.toml` |
| Render | FastAPI backend (EU region) | `render.yaml` |
| Vercel | Next.js chatbot | Auto-detected |
| GitHub Pages | Astro static site | `.github/workflows/` |

---

## Final Notes

1. **This is a hybrid system**: Python backend + TypeScript frontend + Astro website
2. **Different linting rules**: Python (none enforced), TypeScript (Ultracite - very strict)
3. **Secrets management**: Always use Doppler, never commit `.env`
4. **LLM strategy**: OpenRouter for cost optimization (50-90% savings)
5. **Multi-agent coordination**: SEO robots use CrewAI sequential workflow
6. **Testing**: Python uses individual test scripts, TypeScript uses Playwright
7. **Git branch**: `main` (NOT `master`, despite what CLAUDE.md says)
8. **Environment**: Flox for system deps, venv for Python packages, pnpm for Node.js

**When unsure**:
1. Check existing patterns in similar files
2. Read relevant docs in `docs/` or `chatbot/docs/`
3. Run tests to validate (`python test_*.py` or `pnpm test`)
4. Follow the tier-appropriate LLM (cheap → balanced → premium)
5. Use Doppler for all secrets

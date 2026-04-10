/**
 * Web server for the Multi-Agent Research Hub UI.
 *
 * Run:
 *   npx tsx examples/ui/server.ts
 *
 * Then open http://localhost:3847 in your browser.
 * Uses SSE (Server-Sent Events) for real-time streaming of agent progress.
 */

import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { OpenMultiAgent } from '../../src/index.js'
import type { AgentConfig, OrchestratorEvent, Task } from '../../src/types.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const WORKSPACE = resolve(__dirname, '..', '..', '..')
const PORT = 3847
const TOKEN_FILE = resolve(process.env['HOME'] ?? process.env['USERPROFILE'] ?? '.', '.copilot-github-token')

// ---------------------------------------------------------------------------
// Provider detection
// ---------------------------------------------------------------------------

type ProviderChoice = { provider: 'anthropic' | 'openai' | 'copilot'; model: string }

function detectProvider(): ProviderChoice {
  if (process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_API_KEY.includes('REPLACE'))
    return { provider: 'anthropic', model: 'claude-sonnet-4-6' }
  if (process.env.OPENAI_API_KEY)
    return { provider: 'openai', model: 'gpt-4o' }
  return { provider: 'copilot', model: 'gpt-4o' }
}

// ---------------------------------------------------------------------------
// Agent definitions (same as multi-agent-research.ts)
// ---------------------------------------------------------------------------

function makeAgent(name: string, systemPrompt: string, tools: string[], maxTurns: number, provider: string, model: string): AgentConfig {
  return { name, model, provider: provider as AgentConfig['provider'], systemPrompt, tools, maxTurns, temperature: 0.3 }
}

function getAgentDefs(provider: string, model: string): Record<string, AgentConfig> {
  return {
    researcher: makeAgent('researcher',
      `You are a mathematical researcher working in the Ramanujan machine / continued fraction discovery space.
You have access to a Python workspace at ${WORKSPACE} with mpmath, sympy, and custom PCF/discovery tools.
Use bash to run Python scripts and file_read to examine data files (JSON, .tex, .py).
Focus on extracting key facts, identifying patterns, and summarizing findings precisely.`,
      ['bash', 'file_read', 'grep'], 10, provider, model),

    analyst: makeAgent('analyst',
      `You are a computational mathematics analyst. You write and run short Python scripts to verify claims.
The workspace at ${WORKSPACE} has a .venv with mpmath, sympy, numpy. Run Python with:
  ${WORKSPACE}\\.venv\\Scripts\\python.exe <script>
Write verification scripts, run them, and report exact numeric results.`,
      ['bash', 'file_read', 'file_write'], 10, provider, model),

    writer: makeAgent('writer',
      `You are a technical writer specializing in mathematical papers and reports. Produce clear, well-structured summaries.
Use LaTeX notation where appropriate. Write the final report to ${WORKSPACE}\\agent_report.md.`,
      ['file_read', 'file_write'], 6, provider, model),

    critic: makeAgent('critic',
      `You are a peer reviewer for computational mathematics papers.
Read files in ${WORKSPACE}, identify errors, unclear statements, missing proofs. Be specific: cite line numbers.`,
      ['file_read', 'grep'], 8, provider, model),

    improver: makeAgent('improver',
      `You are a mathematical editor. Propose concrete fixes based on critique.
Save revision notes to ${WORKSPACE}\\review_notes.md.`,
      ['file_read', 'file_write'], 8, provider, model),

    explorer: makeAgent('explorer',
      `You are a PCF explorer. Write and run Python scripts using mpmath to search for new formulas.
The workspace has ramanujan_breakthrough_generator.py with PCFEngine. Run with:
  ${WORKSPACE}\\.venv\\Scripts\\python.exe <script>`,
      ['bash', 'file_read', 'file_write'], 12, provider, model),

    verifier: makeAgent('verifier',
      `You are a verification specialist. Recompute candidate formulas at 200+ digits using mpmath.
Run PSLQ, classify results. Save to ${WORKSPACE}\\verified_candidates.json.`,
      ['bash', 'file_read', 'file_write'], 10, provider, model),
  }
}

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

function sseWrite(res: ServerResponse, data: Record<string, unknown>) {
  res.write(`data: ${JSON.stringify(data)}\n\n`)
}

// ---------------------------------------------------------------------------
// Active run tracking (for stop)
// ---------------------------------------------------------------------------

let activeAbort: AbortController | null = null

// ---------------------------------------------------------------------------
// HTTP server
// ---------------------------------------------------------------------------

const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)

  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return }

  // Static: serve index.html
  if (url.pathname === '/' || url.pathname === '/index.html') {
    const html = readFileSync(resolve(__dirname, 'index.html'), 'utf-8')
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    res.end(html)
    return
  }

  // API: status check
  if (url.pathname === '/api/status') {
    const hasToken = !!(
      process.env.ANTHROPIC_API_KEY?.length ||
      process.env.OPENAI_API_KEY?.length ||
      process.env.GITHUB_TOKEN?.length ||
      process.env.GITHUB_COPILOT_TOKEN?.length ||
      (existsSync(TOKEN_FILE) && readFileSync(TOKEN_FILE, 'utf-8').trim().startsWith('gho_'))
    )
    const { provider, model } = detectProvider()
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ authenticated: hasToken, provider, model }))
    return
  }

  // API: stop
  if (url.pathname === '/api/stop' && req.method === 'POST') {
    if (activeAbort) activeAbort.abort()
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ stopped: true }))
    return
  }

  // API: run (SSE)
  if (url.pathname === '/api/run') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    })

    const mode = url.searchParams.get('mode') ?? 'research'
    const agentNames = (url.searchParams.get('agents') ?? '').split(',').filter(Boolean)
    const goal = url.searchParams.get('goal') ?? ''

    if (!goal) {
      sseWrite(res, { type: 'error', message: 'No goal provided' })
      res.end()
      return
    }

    const { provider, model } = detectProvider()
    const allAgents = getAgentDefs(provider, model)
    const agents: AgentConfig[] = agentNames
      .filter(n => n in allAgents)
      .map(n => allAgents[n as keyof typeof allAgents])

    if (agents.length === 0) {
      sseWrite(res, { type: 'error', message: 'No valid agents selected' })
      res.end()
      return
    }

    activeAbort = new AbortController()
    const abort = activeAbort

    // Intercept device code callback to send to UI
    const originalOnDeviceCode = (uri: string, code: string) => {
      sseWrite(res, { type: 'auth_required', uri, code })
    }

    const orchestrator = new OpenMultiAgent({
      defaultModel: model,
      defaultProvider: provider,
      onProgress: (event: OrchestratorEvent) => {
        if (abort.signal.aborted) return
        switch (event.type) {
          case 'agent_start':
            sseWrite(res, { type: 'agent_start', agent: event.agent })
            break
          case 'agent_complete':
            sseWrite(res, { type: 'agent_complete', agent: event.agent })
            break
          case 'task_start': {
            const t = event.data as Task | undefined
            sseWrite(res, { type: 'task_start', title: t?.title ?? event.task, assignee: t?.assignee ?? '?' })
            break
          }
          case 'task_complete': {
            const t = event.data as Task | undefined
            sseWrite(res, { type: 'task_complete', title: t?.title ?? event.task })
            break
          }
        }
      },
    })

    try {
      const team = orchestrator.createTeam(`${mode}-team`, {
        name: `${mode}-team`,
        agents,
        sharedMemory: true,
      })

      const result = await orchestrator.runTeam(team, goal)

      if (!abort.signal.aborted) {
        // Check if auth happened (token got persisted)
        if (process.env.GITHUB_TOKEN) {
          sseWrite(res, { type: 'auth_complete' })
        }

        if (result.output) {
          sseWrite(res, { type: 'output', text: result.output })
        }
        sseWrite(res, {
          type: 'tokens',
          input: result.totalTokenUsage.input_tokens,
          output: result.totalTokenUsage.output_tokens,
        })
        sseWrite(res, { type: 'done', success: result.success })
      }
    } catch (err) {
      if (!abort.signal.aborted) {
        sseWrite(res, { type: 'error', message: (err as Error).message })
      }
    } finally {
      activeAbort = null
      res.end()
    }
    return
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'text/plain' })
  res.end('Not found')
})

server.listen(PORT, () => {
  const { provider, model } = detectProvider()
  console.log(`\n  Multi-Agent Research Hub`)
  console.log(`  http://localhost:${PORT}`)
  console.log(`  Provider: ${provider} / ${model}`)
  console.log(`  Workspace: ${WORKSPACE}`)

  const hasPersistedToken = existsSync(TOKEN_FILE)
  if (hasPersistedToken) {
    console.log(`  Token: found persisted token (no auth needed)`)
  } else if (process.env.GITHUB_TOKEN || process.env.ANTHROPIC_API_KEY) {
    console.log(`  Token: found in environment`)
  } else {
    console.log(`  Token: none — will prompt on first run`)
  }
  console.log()
})

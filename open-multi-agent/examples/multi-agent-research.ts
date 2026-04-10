/**
 * Multi-agent team runner for the Ramanujan/math discovery workspace.
 *
 * Usage:
 *   npx tsx examples/multi-agent-research.ts "Analyze the PCF discoveries in pcf_discoveries.json"
 *   npx tsx examples/multi-agent-research.ts --mode review "Check vquad_paper.tex for errors"
 *   npx tsx examples/multi-agent-research.ts --mode explore "Find novel continued fraction formulas for zeta(5)"
 *
 * Modes:
 *   research  (default) — 3 agents: researcher, analyst, writer
 *   review    — 2 agents: critic, improver
 *   explore   — 2 agents: explorer, verifier
 *
 * Uses GitHub Copilot (no API keys). Falls back to Anthropic/OpenAI if keys are set.
 *
 * The agents can read/write files and run Python scripts in the parent workspace.
 */

import { OpenMultiAgent } from '../src/index.js'
import type { AgentConfig, OrchestratorEvent, Task } from '../src/types.js'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const __dirname = dirname(fileURLToPath(import.meta.url))
const WORKSPACE = resolve(__dirname, '..', '..')  // parent: claude-chat/

type ProviderChoice = { provider: 'anthropic' | 'openai' | 'copilot'; model: string }

function detectProvider(): ProviderChoice {
  if (process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_API_KEY.includes('REPLACE'))
    return { provider: 'anthropic', model: 'claude-sonnet-4-6' }
  if (process.env.OPENAI_API_KEY)
    return { provider: 'openai', model: 'gpt-4o' }
  return { provider: 'copilot', model: 'gpt-4o' }
}

const { provider, model } = detectProvider()

// ---------------------------------------------------------------------------
// Agent templates
// ---------------------------------------------------------------------------

function agent(name: string, systemPrompt: string, tools: string[], maxTurns = 8): AgentConfig {
  return { name, model, provider, systemPrompt, tools, maxTurns, temperature: 0.3 }
}

const AGENTS = {
  // Research mode
  researcher: agent('researcher',
    `You are a mathematical researcher working in the Ramanujan machine / continued fraction discovery space.
You have access to a Python workspace at ${WORKSPACE} with mpmath, sympy, and custom PCF/discovery tools.
Use bash to run Python scripts and file_read to examine data files (JSON, .tex, .py).
Focus on extracting key facts, identifying patterns, and summarizing findings precisely.`,
    ['bash', 'file_read', 'grep'], 10),

  analyst: agent('analyst',
    `You are a computational mathematics analyst. You write and run short Python scripts to verify claims.
The workspace at ${WORKSPACE} has a .venv with mpmath, sympy, numpy. Activate it with:
  ${WORKSPACE}\\.venv\\Scripts\\python.exe <script>
Write verification scripts, run them, and report exact numeric results.
Be rigorous: state precision in decimal digits, note any discrepancies.`,
    ['bash', 'file_read', 'file_write'], 10),

  writer: agent('writer',
    `You are a technical writer specializing in mathematical papers and reports.
Read the research and analysis results from previous agents, then produce a clear, well-structured summary.
Use LaTeX notation where appropriate. Write the final report to ${WORKSPACE}\\agent_report.md.`,
    ['file_read', 'file_write'], 6),

  // Review mode
  critic: agent('critic',
    `You are a peer reviewer for computational mathematics papers.
Read files in ${WORKSPACE}, identify errors, unclear statements, missing proofs, and notation issues.
Be specific: cite line numbers, quote exact text, classify severity (critical/major/minor).`,
    ['file_read', 'grep'], 8),

  improver: agent('improver',
    `You are a mathematical editor. Given the critic's feedback, propose concrete fixes.
Write corrected text, suggest restructured sections, and flag anything that needs the author's input.
Save your revision notes to ${WORKSPACE}\\review_notes.md.`,
    ['file_read', 'file_write'], 8),

  // Explore mode
  explorer: agent('explorer',
    `You are a PCF (polynomial continued fraction) explorer.
Write and run Python scripts using mpmath at high precision to search for new formulas.
The workspace has ramanujan_breakthrough_generator.py with PCFEngine you can import.
Activate Python: ${WORKSPACE}\\.venv\\Scripts\\python.exe
Search methodically: vary polynomial coefficients, check convergence, match against known constants.`,
    ['bash', 'file_read', 'file_write'], 12),

  verifier: agent('verifier',
    `You are a verification specialist. Given candidate formulas from the explorer:
1. Recompute at higher precision (200+ digits) using mpmath
2. Run PSLQ to find exact algebraic relations
3. Check if the formula is a known identity (compare with literature)
4. Classify: NOVEL, KNOWN, or TRIVIAL
Save verified results to ${WORKSPACE}\\verified_candidates.json.`,
    ['bash', 'file_read', 'file_write'], 10),
}

// ---------------------------------------------------------------------------
// Mode definitions
// ---------------------------------------------------------------------------

type Mode = 'research' | 'review' | 'explore'

const MODES: Record<Mode, { agents: AgentConfig[]; description: string }> = {
  research: {
    agents: [AGENTS.researcher, AGENTS.analyst, AGENTS.writer],
    description: 'Research team: gather facts → verify computations → write report',
  },
  review: {
    agents: [AGENTS.critic, AGENTS.improver],
    description: 'Review team: critique → suggest improvements',
  },
  explore: {
    agents: [AGENTS.explorer, AGENTS.verifier],
    description: 'Exploration team: search for formulas → verify candidates',
  },
}

// ---------------------------------------------------------------------------
// Progress logging
// ---------------------------------------------------------------------------

function handleProgress(event: OrchestratorEvent): void {
  const ts = new Date().toISOString().slice(11, 23)
  switch (event.type) {
    case 'agent_start':
      console.log(`\n[${ts}] ▶ Agent "${event.agent}" starting`)
      break
    case 'agent_complete':
      console.log(`[${ts}] ✓ Agent "${event.agent}" done`)
      break
    case 'task_start': {
      const task = event.data as Task | undefined
      console.log(`[${ts}]   ┌ Task: "${task?.title ?? event.task}" → ${task?.assignee ?? '?'}`)
      break
    }
    case 'task_complete': {
      const task = event.data as Task | undefined
      console.log(`[${ts}]   └ Task complete: "${task?.title ?? event.task}"`)
      break
    }
    case 'task_retry':
      console.log(`[${ts}]   ↻ Retrying: "${event.task}"`)
      break
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const args = process.argv.slice(2)

// Parse --mode flag
let mode: Mode = 'research'
const modeIdx = args.indexOf('--mode')
if (modeIdx !== -1 && args[modeIdx + 1]) {
  const m = args[modeIdx + 1] as Mode
  if (!(m in MODES)) {
    console.error(`Unknown mode: ${m}. Available: ${Object.keys(MODES).join(', ')}`)
    process.exit(1)
  }
  mode = m
  args.splice(modeIdx, 2)
}

const goal = args.join(' ').trim()
if (!goal) {
  console.error('Usage: npx tsx examples/multi-agent-research.ts [--mode research|review|explore] "your goal"')
  console.error('\nExamples:')
  console.error('  npx tsx examples/multi-agent-research.ts "Analyze pcf_discoveries.json and summarize findings"')
  console.error('  npx tsx examples/multi-agent-research.ts --mode review "Review vquad_paper.tex"')
  console.error('  npx tsx examples/multi-agent-research.ts --mode explore "Search for zeta(5) continued fractions"')
  process.exit(1)
}

const modeConfig = MODES[mode]
console.log(`\n${'═'.repeat(70)}`)
console.log(`  Multi-Agent ${mode.toUpperCase()} (${provider}/${model})`)
console.log(`  ${modeConfig.description}`)
console.log(`  Agents: ${modeConfig.agents.map(a => a.name).join(' → ')}`)
console.log(`${'═'.repeat(70)}`)
console.log(`\nGoal: ${goal}\n`)

const orchestrator = new OpenMultiAgent({
  defaultModel: model,
  defaultProvider: provider,
  onProgress: handleProgress,
})

const team = orchestrator.createTeam(`${mode}-team`, {
  name: `${mode}-team`,
  agents: modeConfig.agents,
  sharedMemory: true,
})

const result = await orchestrator.runTeam(team, goal)

console.log(`\n${'─'.repeat(70)}`)
if (result.success) {
  console.log('\n📋 FINAL OUTPUT:\n')
  console.log(result.output)
  console.log(`\n${'─'.repeat(70)}`)
  console.log(`Tokens: input=${result.totalTokenUsage.input_tokens}, output=${result.totalTokenUsage.output_tokens}`)
  console.log('Done.')
} else {
  console.error('\nTeam failed:', result.output)
  process.exit(1)
}

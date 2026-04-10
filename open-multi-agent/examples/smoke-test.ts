/**
 * Smoke test — verify open-multi-agent is installed and working.
 *
 * Run:
 *   npx tsx examples/smoke-test.ts
 *
 * No API keys needed. Uses the GitHub Copilot adapter which authenticates
 * via OAuth device flow — on first run it will show a URL and code to
 * authorize in your browser. After that, the token is cached.
 *
 * If you prefer a specific provider, set the corresponding env var:
 *   ANTHROPIC_API_KEY, OPENAI_API_KEY, or GITHUB_TOKEN
 */

import { OpenMultiAgent } from '../src/index.js'
import type { OrchestratorEvent } from '../src/types.js'

// ── Auto-detect best available provider ───────────────────────────────────
type ProviderChoice = { provider: 'anthropic' | 'openai' | 'copilot'; model: string }

function detectProvider(): ProviderChoice {
  if (process.env.ANTHROPIC_API_KEY) {
    console.log('Using Anthropic (ANTHROPIC_API_KEY found)')
    return { provider: 'anthropic', model: 'claude-sonnet-4-6' }
  }
  if (process.env.OPENAI_API_KEY) {
    console.log('Using OpenAI (OPENAI_API_KEY found)')
    return { provider: 'openai', model: 'gpt-4o' }
  }
  // Default: Copilot — works with no env vars via OAuth device flow
  console.log('No API keys found — using GitHub Copilot adapter (OAuth device flow)')
  console.log('If prompted, open the URL in your browser and enter the code.\n')
  return { provider: 'copilot', model: 'gpt-4o' }
}

const { provider, model } = detectProvider()

// ── Run a single-agent smoke test ─────────────────────────────────────────
const orchestrator = new OpenMultiAgent({
  defaultModel: model,
  defaultProvider: provider,
  onProgress: (event: OrchestratorEvent) => {
    if (event.type === 'agent_start')    console.log(`[start]    agent=${event.agent}`)
    if (event.type === 'agent_complete') console.log(`[complete] agent=${event.agent}`)
  },
})

console.log(`Running smoke test (${provider} / ${model})...\n`)

const result = await orchestrator.runAgent(
  {
    name: 'smoke',
    model,
    provider,
    systemPrompt: 'You are a helpful assistant. Respond briefly.',
    maxTurns: 1,
    maxTokens: 256,
  },
  'Say hello and confirm you are working.',
)

if (result.success) {
  console.log('\nAgent output:')
  console.log('─'.repeat(60))
  console.log(result.output)
  console.log('─'.repeat(60))
  console.log(`Tokens: input=${result.tokenUsage.input_tokens}, output=${result.tokenUsage.output_tokens}`)
  console.log('\nSetup complete.')
} else {
  console.error('\nAgent failed:', result.output)
  process.exit(1)
}

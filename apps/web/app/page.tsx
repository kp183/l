"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  SignedIn, 
  SignedOut, 
  UserButton 
} from "@clerk/nextjs";
import { 
  Activity, 
  Terminal, 
  Cpu, 
  DollarSign, 
  Layers, 
  Zap, 
  Play, 
  Check, 
  Copy, 
  ExternalLink,
  ChevronRight,
  TrendingUp,
  Sparkles,
  RefreshCw,
  Search,
  Code
} from "lucide-react";

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState<"openai" | "anthropic" | "custom">("openai");
  const [copied, setCopied] = useState(false);

  // Mini Cost Calculator State
  const [calcModel, setCalcModel] = useState<"gpt-4o" | "gpt-4o-mini" | "claude-3-5-sonnet" | "claude-3-5-haiku">("gpt-4o");
  const [calcPromptTokens, setCalcPromptTokens] = useState<number>(1000);
  const [calcCompletionTokens, setCalcCompletionTokens] = useState<number>(500);

  // Pricing rates per 1M tokens
  const pricingRates = {
    "gpt-4o": { input: 2.50, output: 10.00 },
    "gpt-4o-mini": { input: 0.150, output: 0.60 },
    "claude-3-5-sonnet": { input: 3.00, output: 15.00 },
    "claude-3-5-haiku": { input: 0.80, output: 4.00 }
  };

  const calculatedCost = (() => {
    const rate = pricingRates[calcModel];
    const inputCost = (calcPromptTokens / 1_000_000) * rate.input;
    const outputCost = (calcCompletionTokens / 1_000_000) * rate.output;
    return (inputCost + outputCost).toFixed(6);
  })();

  const codeSnippets = {
    openai: `import agentlens as al
import openai

# 1. Initialize SDK
al.init(api_key="al_live_...")

# 2. Auto-instrument clients
al.instrument_openai()

# 3. Trace your agent steps
@al.trace(name="Support Agent")
def run():
    client = openai.OpenAI()
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Help!"}]
    )

run()
al.flush()`,
    anthropic: `import agentlens as al
import anthropic

# 1. Initialize SDK
al.init(api_key="al_live_...")

# 2. Auto-instrument clients
al.instrument_anthropic()

# 3. Trace your agent steps
@al.trace(name="Creative Writer")
def write_story():
    client = anthropic.Anthropic()
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Tell a tale."}]
    )

write_story()
al.flush()`,
    custom: `import agentlens as al

al.init(api_key="al_live_...")

# Manual span wrapping
@al.trace(name="Orchestration Loop")
def agent_step():
    # Capture subtask steps
    with al.span(name="Thinking Process") as s:
        # Perform computation
        s.set_metadata({"temperature": 0.7})
        
    return "done"

agent_step()
al.flush()`
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(codeSnippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 overflow-x-hidden">
      
      {/* Dynamic Background Gradients */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[600px] pointer-events-none select-none overflow-hidden z-0">
        <div className="absolute top-[-10%] left-[-20%] w-[80%] h-[80%] rounded-full bg-indigo-500/10 blur-[120px]" />
        <div className="absolute top-[10%] right-[-10%] w-[60%] h-[70%] rounded-full bg-violet-600/10 blur-[130px]" />
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 w-full border-b border-slate-900 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl h-16 items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
              AgentLens
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#pricing-preview" className="hover:text-white transition-colors">Pricing Engine</a>
            <a href="#sdk" className="hover:text-white transition-colors">SDK Setup</a>
            <a href="https://github.com/kp183/l" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-white transition-colors">
              GitHub <ExternalLink className="h-3 w-3" />
            </a>
          </nav>

          <div className="flex items-center gap-4">
            <SignedOut>
              <Link 
                href="/sign-in" 
                className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link 
                href="/sign-up" 
                className="rounded-lg bg-gradient-to-r from-indigo-500 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/15 hover:shadow-indigo-500/25 hover:from-indigo-600 hover:to-violet-700 transition-all duration-200"
              >
                Get Started
              </Link>
            </SignedOut>

            <SignedIn>
              <Link 
                href="/dashboard" 
                className="rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-850 px-4 py-2 text-sm font-semibold text-white transition-all duration-200"
              >
                Dashboard
              </Link>
              <div className="h-8 w-8 rounded-full border border-slate-800 flex items-center justify-center overflow-hidden">
                <UserButton afterSignOutUrl="/" />
              </div>
            </SignedIn>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pt-20 pb-24 text-center md:pt-32 md:pb-36">
        
        {/* Release Tag */}
        <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/5 px-4 py-1.5 text-xs font-semibold text-indigo-400 backdrop-blur-sm animate-pulse">
          <Sparkles className="h-3 w-3" />
          <span>AgentLens v1.0.0 is Live</span>
        </div>

        {/* Title */}
        <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight text-white sm:text-6xl md:text-7xl lg:text-8xl leading-none">
          Observability at the
          <span className="block mt-2 bg-gradient-to-r from-indigo-400 via-violet-400 to-pink-400 bg-clip-text text-transparent">
            Speed of Thought.
          </span>
        </h1>

        {/* Sub-header */}
        <p className="mx-auto mt-8 max-w-2xl text-base text-slate-400 sm:text-lg md:text-xl leading-relaxed">
          Pristine, real-time tracing for autonomous AI agents. Capture nested parent-child steps, measure exact token dollar-costs, and analyze tool hierarchies with zero runtime overhead.
        </p>

        {/* CTA Buttons */}
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <Link 
            href="/sign-up" 
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-6 py-3.5 text-base font-semibold text-white shadow-xl shadow-indigo-500/20 hover:shadow-indigo-500/30 hover:from-indigo-600 hover:to-violet-700 transition-all duration-200 transform hover:-translate-y-0.5"
          >
            Start Free Ingestion <ChevronRight className="h-4 w-4" />
          </Link>
          <a 
            href="https://github.com/kp183/l" 
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 px-6 py-3.5 text-base font-semibold text-slate-200 transition-all duration-200"
          >
            <Terminal className="h-4 w-4 text-indigo-400" /> View SDK on GitHub
          </a>
        </div>

        {/* Dashboard Mockup Representation */}
        <div className="relative mt-20 md:mt-24 rounded-2xl border border-slate-900 bg-slate-950 p-4 md:p-6 shadow-2xl shadow-indigo-500/5">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-indigo-500/10 via-transparent to-violet-600/5 pointer-events-none" />
          
          {/* Mock Window Header */}
          <div className="flex items-center justify-between border-b border-slate-900 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-rose-500/80" />
              <div className="h-3 w-3 rounded-full bg-amber-500/80" />
              <div className="h-3 w-3 rounded-full bg-emerald-500/80" />
              <span className="ml-2 text-xs font-mono text-slate-500">agentlens-console // live-traces</span>
            </div>
            <div className="flex items-center gap-2 rounded-md bg-slate-900/50 border border-slate-900 px-2 py-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
              <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest font-semibold">Live Streaming</span>
            </div>
          </div>

          {/* Interactive Gantt Tree Mockup */}
          <div className="w-full text-left font-mono text-xs text-slate-300 rounded-lg bg-slate-900/40 p-4 border border-slate-900 overflow-x-auto space-y-4">
            {/* Trace 1: Root Agent */}
            <div className="flex flex-col md:flex-row md:items-center justify-between p-3.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
              <div className="flex items-center gap-3">
                <Layers className="h-4 w-4 text-indigo-400" />
                <div>
                  <span className="font-semibold text-white">Main Support Coordinator</span>
                  <span className="ml-2 rounded-full bg-indigo-500/15 text-indigo-300 text-[10px] px-1.5 py-0.5">agent</span>
                </div>
              </div>
              <div className="flex items-center gap-6 mt-2 md:mt-0 text-slate-400">
                <span>Duration: <strong className="text-white">1,420ms</strong></span>
                <span>Cost: <strong className="text-emerald-400">$0.00234</strong></span>
              </div>
            </div>

            {/* Child 1: Intent Classification */}
            <div className="flex flex-col md:flex-row md:items-center justify-between p-3 ml-6 rounded-lg border border-slate-800 bg-slate-950/40">
              <div className="flex items-center gap-3">
                <ChevronRight className="h-4 w-4 text-slate-500" />
                <Cpu className="h-4 w-4 text-violet-400" />
                <div>
                  <span className="font-semibold text-white">Classify Intent (gpt-4o-mini)</span>
                  <span className="ml-2 rounded-full bg-violet-500/15 text-violet-300 text-[10px] px-1.5 py-0.5">llm</span>
                </div>
              </div>
              <div className="flex items-center gap-6 mt-2 md:mt-0 text-slate-400">
                <span>Tokens: <span className="text-slate-200">125 / 45</span></span>
                <span>Cost: <strong className="text-emerald-400">$0.000045</strong></span>
              </div>
            </div>

            {/* Child 2: Memory Retrieval */}
            <div className="flex flex-col md:flex-row md:items-center justify-between p-3 ml-6 rounded-lg border border-slate-800 bg-slate-950/40">
              <div className="flex items-center gap-3">
                <ChevronRight className="h-4 w-4 text-slate-500" />
                <Terminal className="h-4 w-4 text-amber-400" />
                <div>
                  <span className="font-semibold text-white">Query VectorDB</span>
                  <span className="ml-2 rounded-full bg-amber-500/15 text-amber-300 text-[10px] px-1.5 py-0.5">tool</span>
                </div>
              </div>
              <div className="flex items-center gap-6 mt-2 md:mt-0 text-slate-400">
                <span>Matches: <span className="text-slate-200">3 docs</span></span>
                <span>Duration: <strong className="text-white">180ms</strong></span>
              </div>
            </div>

            {/* Child 3: Response Synthesis */}
            <div className="flex flex-col md:flex-row md:items-center justify-between p-3 ml-6 rounded-lg border border-slate-800 bg-slate-950/40">
              <div className="flex items-center gap-3">
                <ChevronRight className="h-4 w-4 text-slate-500" />
                <Cpu className="h-4 w-4 text-violet-400" />
                <div>
                  <span className="font-semibold text-white">Generate Synthesis (gpt-4o)</span>
                  <span className="ml-2 rounded-full bg-violet-500/15 text-violet-300 text-[10px] px-1.5 py-0.5">llm</span>
                </div>
              </div>
              <div className="flex items-center gap-6 mt-2 md:mt-0 text-slate-400">
                <span>Tokens: <span className="text-slate-200">850 / 220</span></span>
                <span>Cost: <strong className="text-emerald-400">$0.002295</strong></span>
              </div>
            </div>

          </div>
        </div>

      </section>

      {/* Value Pillars / Features */}
      <section id="features" className="relative z-10 border-t border-slate-900 bg-slate-950 py-24 md:py-32">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Engineered for High-Performance AI Apps
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-slate-400">
              AgentLens solves the complexity of nested tool tracking, token inflation, and agent latency in production environments.
            </p>
          </div>

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            
            {/* Feature 1 */}
            <div className="flex flex-col rounded-2xl border border-slate-900 bg-slate-900/30 p-6 hover:border-slate-850 hover:bg-slate-900/50 transition-all duration-200">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 mb-6">
                <Zap className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">Non-Blocking SDK</h3>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Background thread workers dispatch traces asynchronously. Your agent code executes without any latency delay.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="flex flex-col rounded-2xl border border-slate-900 bg-slate-900/30 p-6 hover:border-slate-850 hover:bg-slate-900/50 transition-all duration-200">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400 mb-6">
                <DollarSign className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">Dynamic Pricing Engine</h3>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Automatically maps token payloads to our extensive pricing database to compute real-time cost analysis of every trace.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="flex flex-col rounded-2xl border border-slate-900 bg-slate-900/30 p-6 hover:border-slate-850 hover:bg-slate-900/50 transition-all duration-200">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 mb-6">
                <Layers className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">Hierarchical Gantt Charts</h3>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Visualize multi-layered agent workflow loops. Drill down into specific prompt variables, tool payloads, and metadata.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="flex flex-col rounded-2xl border border-slate-900 bg-slate-900/30 p-6 hover:border-slate-850 hover:bg-slate-900/50 transition-all duration-200">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 mb-6">
                <Activity className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">Real-Time Streams</h3>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Powered by a low-latency Redis Pub/Sub framework. New spans are pushed directly to the dashboard over WebSockets.
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* SDK Code Snippets Section */}
      <section id="sdk" className="relative z-10 py-24 md:py-32 bg-slate-900/20 border-t border-slate-900">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-12 lg:grid-cols-12 items-center">
            
            {/* Context Left */}
            <div className="lg:col-span-5 text-left">
              <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/5 px-3 py-1 text-xs font-semibold text-violet-400 backdrop-blur-sm mb-4">
                <Code className="h-3.5 w-3.5" />
                <span>Quick Deployment</span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Instrument in less than 60 seconds
              </h2>
              <p className="mt-4 text-base text-slate-400 leading-relaxed">
                Install our lightweight Python client library. With a single auto-instrumentation function call, all your existing OpenAI and Anthropic client workflows are tracked securely.
              </p>

              <div className="mt-8 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 mt-0.5">
                    <Check className="h-3 w-3" />
                  </div>
                  <span className="text-sm text-slate-300">Simple <code>pip install agentlens</code> install.</span>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 mt-0.5">
                    <Check className="h-3 w-3" />
                  </div>
                  <span className="text-sm text-slate-300">Fully thread-safe daemon worker architecture.</span>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 mt-0.5">
                    <Check className="h-3 w-3" />
                  </div>
                  <span className="text-sm text-slate-300">Supports custom manual spans for DB, tools, & APIs.</span>
                </div>
              </div>
            </div>

            {/* Code Box Right */}
            <div className="lg:col-span-7 rounded-2xl border border-slate-900 bg-slate-950 p-6 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-900 pb-4 mb-4">
                
                {/* Switcher Tabs */}
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => setActiveTab("openai")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      activeTab === "openai" 
                        ? "bg-slate-900 border border-slate-800 text-white" 
                        : "text-slate-450 hover:text-slate-200"
                    }`}
                  >
                    OpenAI Client
                  </button>
                  <button 
                    onClick={() => setActiveTab("anthropic")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      activeTab === "anthropic" 
                        ? "bg-slate-900 border border-slate-800 text-white" 
                        : "text-slate-450 hover:text-slate-200"
                    }`}
                  >
                    Anthropic Client
                  </button>
                  <button 
                    onClick={() => setActiveTab("custom")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      activeTab === "custom" 
                        ? "bg-slate-900 border border-slate-800 text-white" 
                        : "text-slate-450 hover:text-slate-200"
                    }`}
                  >
                    Manual Spans
                  </button>
                </div>

                {/* Copy Button */}
                <button 
                  onClick={copyToClipboard}
                  className="flex items-center gap-1.5 text-xs text-slate-450 hover:text-slate-250 bg-slate-900/50 border border-slate-900 rounded-md px-2.5 py-1.5"
                >
                  {copied ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>

              {/* Code Snippet Box */}
              <pre className="text-left font-mono text-[11px] md:text-[13px] text-slate-350 bg-slate-950 p-4 rounded-xl border border-slate-900 overflow-x-auto select-all leading-relaxed max-h-[350px]">
                <code>{codeSnippets[activeTab]}</code>
              </pre>
            </div>

          </div>
        </div>
      </section>

      {/* Cost Calculator Section */}
      <section id="pricing-preview" className="relative z-10 border-t border-slate-900 py-24 md:py-32">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/5 px-3 py-1 text-xs font-semibold text-emerald-400 backdrop-blur-sm mb-4">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>Real-Time Pricing Calculator</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Interact with the Pricing Engine
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-450">
              Pick a model and customize token consumption metrics to test how our ingestion layer calculates cost variables.
            </p>
          </div>

          {/* Interactive Calculator Block */}
          <div className="grid gap-8 md:grid-cols-2 rounded-2xl border border-slate-900 bg-slate-950 p-6 md:p-8 shadow-2xl">
            
            {/* Input Settings */}
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-450 mb-2">Select Model</label>
                <select 
                  value={calcModel} 
                  onChange={(e: any) => setCalcModel(e.target.value)}
                  className="w-full rounded-xl border border-slate-850 bg-slate-900 px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                >
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
                  <option value="claude-3-5-haiku">claude-3-5-haiku</option>
                </select>
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-450">Prompt (Input) Tokens</label>
                  <span className="text-xs font-mono font-bold text-white">{calcPromptTokens.toLocaleString()}</span>
                </div>
                <input 
                  type="range" 
                  min="100" 
                  max="100000" 
                  step="100"
                  value={calcPromptTokens} 
                  onChange={(e) => setCalcPromptTokens(Number(e.target.value))}
                  className="w-full accent-indigo-500 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-450">Completion (Output) Tokens</label>
                  <span className="text-xs font-mono font-bold text-white">{calcCompletionTokens.toLocaleString()}</span>
                </div>
                <input 
                  type="range" 
                  min="100" 
                  max="100000" 
                  step="100"
                  value={calcCompletionTokens} 
                  onChange={(e) => setCalcCompletionTokens(Number(e.target.value))}
                  className="w-full accent-indigo-500 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>

            {/* Calculations Result */}
            <div className="flex flex-col justify-between rounded-xl border border-slate-900 bg-slate-900/30 p-6 text-left">
              <div>
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">Calculated Cost (USD)</span>
                <div className="mt-3 text-4xl md:text-5xl font-extrabold tracking-tight text-emerald-400 font-mono">
                  ${calculatedCost}
                </div>
                <p className="mt-3 text-xs text-slate-450 leading-relaxed">
                  Based on direct API pricing schemas: <br />
                  Input rate: <span className="text-slate-300 font-mono">${pricingRates[calcModel].input}/1M</span> · 
                  Output rate: <span className="text-slate-300 font-mono">${pricingRates[calcModel].output}/1M</span>
                </p>
              </div>

              <div className="mt-8 border-t border-slate-900 pt-6 space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-450">
                  <span>Ingestion Processing Time</span>
                  <span className="text-white font-mono">&lt; 3.2ms</span>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-450">
                  <span>Accuracy Level</span>
                  <span className="text-emerald-400 font-mono">100.00%</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* CTA Wrap-up */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 py-20 text-center">
        <div className="rounded-3xl bg-gradient-to-tr from-indigo-500/10 via-violet-600/5 to-transparent border border-slate-900 p-8 md:p-16 relative overflow-hidden">
          
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
          
          <h2 className="text-3xl font-extrabold text-white sm:text-4xl">
            Ready to trace your first agent loop?
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-sm md:text-base text-slate-450 leading-relaxed">
            Register for a free local console dashboard. Deploy our background daemon SDK and watch your nested tool configurations visualize in real-time.
          </p>
          
          <div className="mt-8 flex justify-center gap-4">
            <Link 
              href="/sign-up" 
              className="rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-6 py-3 font-semibold text-white shadow-lg hover:from-indigo-600 hover:to-violet-700 transition-all transform hover:-translate-y-0.5 duration-150"
            >
              Get Started Free
            </Link>
            <a 
              href="https://github.com/kp183/l" 
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-slate-800 bg-slate-900 px-6 py-3 font-semibold text-slate-300 hover:text-white transition-colors"
            >
              GitHub Repository
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-900 bg-slate-950 py-12 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 rounded-md bg-indigo-500 flex items-center justify-center">
              <Activity className="h-3 w-3 text-white" />
            </div>
            <span className="font-semibold text-slate-400">AgentLens Observability Platform</span>
          </div>

          <div className="flex items-center gap-6">
            <a href="https://github.com/kp183/l" target="_blank" rel="noreferrer" className="hover:text-slate-350 transition-colors">GitHub</a>
            <span>·</span>
            <a href="https://github.com/kp183/l/blob/main/LICENSE" target="_blank" rel="noreferrer" className="hover:text-slate-350 transition-colors">MIT License</a>
            <span>·</span>
            <span className="text-slate-600">Built with Next.js & FastAPI</span>
          </div>
        </div>
      </footer>

    </div>
  );
}

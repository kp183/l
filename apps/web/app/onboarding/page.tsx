"use client";

import React, { useState, useEffect } from "react";
import { useAuth, useUser, UserButton } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { api, Organization, Project, APIKey } from "@/lib/api";
import { 
  Building2, 
  FolderPlus, 
  KeyRound, 
  Loader2, 
  Clipboard, 
  ClipboardCheck, 
  ArrowRight,
  Wifi,
  Sparkles
} from "lucide-react";

export default function OnboardingPage() {
  const { isLoaded, userId, getToken } = useAuth();
  const { user } = useUser();
  const router = useRouter();

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [orgName, setOrgName] = useState("");
  const [projectName, setProjectName] = useState("");

  // Created states
  const [createdOrg, setCreatedOrg] = useState<Organization | null>(null);
  const [createdProject, setCreatedProject] = useState<Project | null>(null);
  const [createdKey, setCreatedKey] = useState<APIKey | null>(null);
  
  const [copied, setCopied] = useState(false);

  // Helper to slugify text
  const slugify = (text: string) =>
    text
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

  // Step 1: Create Organization
  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgName.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No authorization token");
      const org = await api.createOrg(orgName, slugify(orgName), token);
      setCreatedOrg(org);
      setStep(2);
    } catch (err: any) {
      setError(err.message || "Failed to create organization");
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Create Project
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim() || !createdOrg) return;

    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No authorization token");
      const project = await api.createProject(createdOrg.id, projectName, slugify(projectName), token);
      setCreatedProject(project);
      
      // Immediately generate API Key for step 3
      const key = await api.createAPIKey(project.id, "Default Key", token);
      setCreatedKey(key);
      
      setStep(3);
    } catch (err: any) {
      setError(err.message || "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Go to Step 4 (Waiting for trace)
  const handleProceedToWaiting = () => {
    setStep(4);
  };

  // Copy API key logic
  const handleCopyKey = () => {
    if (createdKey?.raw_key) {
      navigator.clipboard.writeText(createdKey.raw_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Step 4: Poll for first trace
  useEffect(() => {
    if (step !== 4 || !createdProject) return;

    let active = true;
    const interval = setInterval(async () => {
      try {
        const token = await getToken();
        if (!token) return;
        
        const response = await api.listTraces(createdProject.id, token, { limit: 1 });
        if (response.data && response.data.length > 0 && active) {
          clearInterval(interval);
          router.push(`/dashboard?project_id=${createdProject.id}`);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2500);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [step, createdProject, getToken, router]);

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
      </div>
    );
  }

  const snippet = `import agentlens as al

al.init(
    api_key="${createdKey?.raw_key || "al_live_your_api_key"}",
    base_url="${typeof window !== "undefined" ? window.location.origin.replace(":3000", ":8000") : "http://localhost:8000"}"
)
al.instrument_openai()`;

  return (
    <div className="relative min-h-screen flex flex-col bg-slate-950 overflow-hidden">
      {/* Dynamic Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="relative z-10 w-full max-w-7xl mx-auto px-6 py-4 flex justify-between items-center border-b border-slate-900 bg-slate-950/80 backdrop-blur-md">
        <div className="flex items-center space-x-2">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <span className="font-semibold text-xl tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            AgentLens
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-slate-400 hidden sm:inline-block">
            Signed in as <span className="text-slate-200">{user?.emailAddresses[0]?.emailAddress}</span>
          </span>
          <UserButton afterSignOutUrl="/sign-in" />
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-2xl bg-slate-900/40 border border-slate-800/80 rounded-2xl p-8 backdrop-blur-xl shadow-2xl shadow-black/40">
          
          {/* Step Progress Bar */}
          <div className="flex items-center justify-between mb-8 border-b border-slate-800/60 pb-6">
            <div className="flex items-center space-x-6 w-full">
              {[1, 2, 3, 4].map((num) => (
                <div key={num} className="flex-1 flex items-center space-x-3">
                  <div className={`h-8 w-8 rounded-full flex items-center justify-center font-medium text-sm transition-all duration-300 ${
                    step === num 
                      ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30 scale-110" 
                      : step > num 
                      ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30" 
                      : "bg-slate-800/60 text-slate-500 border border-slate-800"
                  }`}>
                    {num}
                  </div>
                  <span className={`text-xs font-medium tracking-wide uppercase transition-all duration-300 hidden md:inline ${
                    step === num ? "text-slate-100" : "text-slate-500"
                  }`}>
                    {num === 1 ? "Organization" : num === 2 ? "Project" : num === 3 ? "API Key" : "Connection"}
                  </span>
                  {num < 4 && <div className="flex-1 h-[2px] bg-slate-800" />}
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 text-sm">
              {error}
            </div>
          )}

          {/* STEP 1: CREATE ORGANIZATION */}
          {step === 1 && (
            <form onSubmit={handleCreateOrg} className="space-y-6 animate-fadeIn">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <Building2 className="h-6 w-6 text-indigo-400" />
                  <h2 className="text-xl font-semibold text-slate-100">Create an Organization</h2>
                </div>
                <p className="text-sm text-slate-400">
                  Organizations serve as your primary workspace context. Group your engineering teams and agent projects.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 tracking-wide uppercase">Organization Name</label>
                <input
                  type="text"
                  placeholder="e.g. Acme Intelligence"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  required
                  disabled={loading}
                />
              </div>

              <button
                type="submit"
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-600 hover:to-violet-700 text-white font-medium shadow-lg shadow-indigo-500/20 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group"
                disabled={loading || !orgName.trim()}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    <span>Next: Create Project</span>
                    <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* STEP 2: CREATE PROJECT */}
          {step === 2 && (
            <form onSubmit={handleCreateProject} className="space-y-6 animate-fadeIn">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <FolderPlus className="h-6 w-6 text-indigo-400" />
                  <h2 className="text-xl font-semibold text-slate-100">Create a Project</h2>
                </div>
                <p className="text-sm text-slate-400">
                  A project represents a single autonomous agent service or pipeline. Traces are isolated at the project layer.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 tracking-wide uppercase">Project Name</label>
                <input
                  type="text"
                  placeholder="e.g. customer-support-agent"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  required
                  disabled={loading}
                />
              </div>

              <button
                type="submit"
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-600 hover:to-violet-700 text-white font-medium shadow-lg shadow-indigo-500/20 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group"
                disabled={loading || !projectName.trim()}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    <span>Generate API Credentials</span>
                    <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* STEP 3: API KEY & CODE SNIPPET */}
          {step === 3 && (
            <div className="space-y-6 animate-fadeIn">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <KeyRound className="h-6 w-6 text-indigo-400" />
                  <h2 className="text-xl font-semibold text-slate-100">Your Project API Key</h2>
                </div>
                <p className="text-sm text-slate-400">
                  Use this key to authenticate your SDK client with the platform. Copy this key now — it will never be displayed again.
                </p>
              </div>

              {/* API Key Box */}
              <div className="relative flex items-center justify-between p-4 rounded-xl bg-slate-950/80 border border-slate-800">
                <code className="text-sm font-mono text-indigo-300 break-all select-all pr-12">
                  {createdKey?.raw_key}
                </code>
                <button
                  onClick={handleCopyKey}
                  className="absolute right-4 p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-all"
                  title="Copy API key"
                >
                  {copied ? (
                    <ClipboardCheck className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <Clipboard className="h-5 w-5" />
                  )}
                </button>
              </div>

              {/* Integration Snippet */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 tracking-wide uppercase">Add to your Agent Application</label>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 overflow-x-auto">
                  <pre className="text-xs font-mono text-slate-300">{snippet}</pre>
                </div>
              </div>

              <button
                onClick={handleProceedToWaiting}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 hover:from-indigo-600 hover:to-violet-700 text-white font-medium shadow-lg shadow-indigo-500/20 transition-all duration-300 group"
              >
                <span>Continue: Wait for connection</span>
                <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          )}

          {/* STEP 4: WAITING FOR FIRST TRACE */}
          {step === 4 && (
            <div className="space-y-8 py-6 text-center animate-fadeIn">
              <div className="relative mx-auto w-24 h-24 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border border-indigo-500/30 animate-ping" />
                <Wifi className="h-10 w-10 text-indigo-400 animate-pulse" />
              </div>

              <div className="space-y-2 max-w-md mx-auto">
                <h2 className="text-xl font-semibold text-slate-100">Listening for Agent Spans...</h2>
                <p className="text-sm text-slate-400">
                  We are waiting for your agent application to send its first execution traces. 
                  Run your code with the snippet provided.
                </p>
              </div>

              {/* Integration Snippet (Mini display for reference) */}
              <div className="text-left w-full max-w-lg mx-auto p-4 rounded-xl bg-slate-950 border border-slate-900">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Reference Snippet</span>
                  <button 
                    onClick={() => {
                      navigator.clipboard.writeText(snippet);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }} 
                    className="text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="text-[11px] font-mono text-slate-400 overflow-x-auto whitespace-pre">
                  {snippet}
                </pre>
              </div>

              <div className="flex items-center justify-center space-x-2 text-xs text-slate-500">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Polling v1/traces for {createdProject?.name} every 2.5s</span>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

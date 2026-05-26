"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth, useUser, UserButton } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  api, 
  Organization, 
  Project, 
  APIKey, 
  Trace, 
  SpanNode,
  Span
} from "@/lib/api";
import { 
  Sparkles, 
  Building2, 
  FolderGit, 
  KeyRound, 
  Activity, 
  Clipboard, 
  ClipboardCheck, 
  Search, 
  Filter, 
  Clock, 
  Coins, 
  Layers, 
  AlertCircle, 
  ArrowLeft,
  X,
  Play,
  CheckCircle2,
  XCircle,
  FileCode,
  Terminal,
  Database,
  ArrowRightLeft,
  Trash2,
  Plus,
  Loader2
} from "lucide-react";

export default function DashboardPage() {
  const { isLoaded, userId, getToken } = useAuth();
  const { user } = useUser();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const activeProjectId = searchParams.get("project_id");
  const activeTraceId = searchParams.get("trace_id");

  // Local navigation states
  const [activeTab, setActiveTab] = useState<"traces" | "apikeys">("traces");
  
  // Trace filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [modelFilter, setModelFilter] = useState<string>("all");
  const [dateRange, setDateRange] = useState<string>("24h"); // "1h", "6h", "24h", "7d"

  // Selected Span in inspector
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  
  // API Key creation
  const [newKeyName, setNewKeyName] = useState("");
  const [justCreatedKey, setJustCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // WebSocket connection for streaming spans
  const [wsSpans, setWsSpans] = useState<Span[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // 1. Fetch User's Orgs
  const { data: orgs, isLoading: orgsLoading } = useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No authorization token");
      return api.listOrgs(token);
    },
    enabled: !!userId,
  });

  const activeOrg = orgs?.[0];

  // 2. Fetch Projects for active org
  const { data: projects, isLoading: projectsLoading } = useQuery<Project[]>({
    queryKey: ["projects", activeOrg?.id],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.listProjects(activeOrg!.id, token);
    },
    enabled: !!activeOrg,
  });

  const activeProject = projects?.find(p => p.id === activeProjectId) || projects?.[0];

  // 3. Sync project ID to URL if not set
  useEffect(() => {
    if (projects && projects.length > 0 && !activeProjectId) {
      router.replace(`/dashboard?project_id=${projects[0].id}`);
    }
  }, [projects, activeProjectId, router]);

  // Compute start date based on filter
  const getStartDateISO = () => {
    const now = new Date();
    if (dateRange === "1h") now.setHours(now.getHours() - 1);
    else if (dateRange === "6h") now.setHours(now.getHours() - 6);
    else if (dateRange === "24h") now.setHours(now.getHours() - 24);
    else if (dateRange === "7d") now.setDate(now.getDate() - 7);
    else return null;
    return now.toISOString();
  };

  // 4. Fetch Traces
  const { data: tracesData, isLoading: tracesLoading } = useQuery({
    queryKey: ["traces", activeProject?.id, statusFilter, modelFilter, dateRange],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.listTraces(activeProject!.id, token, {
        status: statusFilter,
        model: modelFilter,
        startDate: getStartDateISO(),
      });
    },
    enabled: !!activeProject && activeTab === "traces" && !activeTraceId,
    refetchInterval: activeTraceId ? false : 10000, // Poll every 10s if list is open
  });

  const uniqueModels = React.useMemo(() => {
    if (!tracesData?.data) return [];
    return Array.from(
      new Set(
        tracesData.data
          .map(t => t.name.includes("(") ? t.name.split("(")[1].replace(")", "").trim() : null)
          .filter((val): val is string => Boolean(val))
      )
    );
  }, [tracesData]);

  // 5. Fetch API Keys
  const { data: apiKeys, isLoading: keysLoading } = useQuery<APIKey[]>({
    queryKey: ["apikeys", activeProject?.id],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.listAPIKeys(activeProject!.id, token);
    },
    enabled: !!activeProject && activeTab === "apikeys",
  });

  // 6. Fetch Trace Detail
  const { data: traceDetail } = useQuery<Trace>({
    queryKey: ["trace", activeTraceId],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.getTrace(activeTraceId!, token);
    },
    enabled: !!activeTraceId,
  });

  // 7. Fetch Trace Spans Tree
  const { data: traceSpansData } = useQuery({
    queryKey: ["traceSpans", activeTraceId],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.getTraceSpans(activeTraceId!, token);
    },
    enabled: !!activeTraceId,
  });

  // Real-time WebSocket connection for running traces
  useEffect(() => {
    if (!activeTraceId || !traceDetail || traceDetail.status !== "running") {
      setWsSpans([]);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    let active = true;
    const connectWS = async () => {
      try {
        const token = await getToken();
        if (!token || !active) return;

        const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsHost = window.location.host.replace("3000", "8000");
        const wsUrl = `${wsProto}//${wsHost}/v1/ws/traces/${activeTraceId}?token=${token}`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "span" && active) {
              setWsSpans(prev => {
                // Deduplicate or append
                const exists = prev.some(s => s.id === msg.data.id);
                if (exists) {
                  return prev.map(s => s.id === msg.data.id ? msg.data : s);
                }
                return [...prev, msg.data];
              });
              // Invalidate trace detail query to fetch completed stats when ws streams
              queryClient.invalidateQueries({ queryKey: ["trace", activeTraceId] });
            }
          } catch (e) {
            console.error("WS parse error", e);
          }
        };

        ws.onclose = () => {
          // Reconnect logic or cleanup
          wsRef.current = null;
        };
      } catch (err) {
        console.error("WS connection error", err);
      }
    };

    connectWS();

    return () => {
      active = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [activeTraceId, traceDetail, getToken, queryClient]);

  // Mutations
  const createKeyMutation = useMutation({
    mutationFn: async (name: string) => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.createAPIKey(activeProject!.id, name, token);
    },
    onSuccess: (data) => {
      setJustCreatedKey(data.raw_key || null);
      setNewKeyName("");
      queryClient.invalidateQueries({ queryKey: ["apikeys", activeProject?.id] });
    }
  });

  const revokeKeyMutation = useMutation({
    mutationFn: async (keyId: string) => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.revokeAPIKey(keyId, token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["apikeys", activeProject?.id] });
    }
  });

  // Calculate relative Gantt metrics
  const getGanttMetrics = (span: Span, traceStartStr: string, traceDurationMs: number | null) => {
    if (!traceStartStr || !traceDurationMs) return { left: 0, width: 100 };
    
    const traceStart = new Date(traceStartStr).getTime();
    const spanStart = new Date(span.started_at).getTime();
    
    const offsetMs = Math.max(0, spanStart - traceStart);
    
    const offsetPercent = (offsetMs / traceDurationMs) * 100;
    
    let spanDuration = span.duration_ms;
    if (spanDuration === null) {
      // Still running, estimate based on now
      spanDuration = Date.now() - spanStart;
    }
    
    const widthPercent = Math.max(2, (spanDuration / traceDurationMs) * 100);
    
    return {
      left: Math.min(98, offsetPercent),
      width: Math.min(100 - offsetPercent, widthPercent)
    };
  };

  // Reconstruct tree flat nodes with indentation depth
  const getFlatSpanNodes = () => {
    // 1. If we have live spans from WS, combine them with static fetch
    let flatSpans: Span[] = [];
    if (traceSpansData?.data) {
      // Flatten existing static tree first
      const flatten = (nodes: SpanNode[]): Span[] => {
        let res: Span[] = [];
        for (const n of nodes) {
          const { children, ...rest } = n;
          res.push(rest);
          res.push(...flatten(children));
        }
        return res;
      };
      flatSpans = flatten(traceSpansData.data);
    }

    // Merge in websocket spans
    for (const wsS of wsSpans) {
      const existsIdx = flatSpans.findIndex(s => s.id === wsS.id);
      if (existsIdx > -1) {
        flatSpans[existsIdx] = wsS;
      } else {
        flatSpans.push(wsS);
      }
    }

    if (flatSpans.length === 0) return [];

    // Sort spans by start time
    flatSpans.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());

    // Build map for parent-child lookup
    const map = new Map<string, Span>();
    const childrenMap = new Map<string, Span[]>();
    const roots: Span[] = [];

    for (const s of flatSpans) {
      map.set(s.id, s);
      if (s.parent_span_id) {
        if (!childrenMap.has(s.parent_span_id)) {
          childrenMap.set(s.parent_span_id, []);
        }
        childrenMap.get(s.parent_span_id)!.push(s);
      } else {
        roots.push(s);
      }
    }

    // Sort child lists by start time
    for (const [_, childList] of childrenMap.entries()) {
      childList.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());
    }

    const flatResult: { span: Span; depth: number }[] = [];
    
    const traverse = (span: Span, depth: number) => {
      flatResult.push({ span, depth });
      const children = childrenMap.get(span.id) || [];
      for (const child of children) {
        traverse(child, depth + 1);
      }
    };

    for (const root of roots) {
      traverse(root, 0);
    }

    return flatResult;
  };

  const flatSpanNodes = getFlatSpanNodes();
  const selectedSpanObj = flatSpanNodes.find(node => node.span.id === selectedSpanId)?.span || flatSpanNodes[0]?.span;

  // Selected Span tab
  const [inspectorTab, setInspectorTab] = useState<"input" | "output" | "llm" | "error" | "metadata">("input");

  // Sync selected span id
  useEffect(() => {
    if (flatSpanNodes.length > 0 && !selectedSpanId) {
      setSelectedSpanId(flatSpanNodes[0].span.id);
    }
  }, [flatSpanNodes, selectedSpanId]);

  if (orgsLoading || projectsLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-50 overflow-hidden font-sans">
      {/* ── SIDEBAR ── */}
      <aside className="w-64 border-r border-slate-900 bg-slate-950 flex flex-col z-20 shrink-0">
        {/* Logo Section */}
        <div className="p-6 border-b border-slate-900 flex items-center space-x-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="font-semibold text-lg bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            AgentLens
          </span>
        </div>

        {/* Project Switcher */}
        <div className="p-4 border-b border-slate-900">
          <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">Project</label>
          <div className="relative">
            <select
              value={activeProject?.id || ""}
              onChange={(e) => {
                router.push(`/dashboard?project_id=${e.target.value}`);
                // Clear trace selection
                setWsSpans([]);
              }}
              className="w-full bg-slate-900/60 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition"
            >
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex-1 p-4 space-y-1.5">
          <button
            onClick={() => {
              setActiveTab("traces");
              router.push(`/dashboard?project_id=${activeProject?.id}`);
            }}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition ${
              activeTab === "traces" && !activeTraceId
                ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/25"
                : "text-slate-400 hover:bg-slate-900/40 hover:text-slate-200"
            }`}
          >
            <Activity className="h-4.5 w-4.5" />
            <span>Agent Traces</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("apikeys");
              // Clear trace detail from url when switching to api keys
              router.push(`/dashboard?project_id=${activeProject?.id}`);
            }}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition ${
              activeTab === "apikeys"
                ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/25"
                : "text-slate-400 hover:bg-slate-900/40 hover:text-slate-200"
            }`}
          >
            <KeyRound className="h-4.5 w-4.5" />
            <span>API Keys</span>
          </button>
        </nav>

        {/* Sidebar Footer User info */}
        <div className="p-4 border-t border-slate-900 bg-slate-950 flex items-center justify-between">
          <div className="flex items-center space-x-3 overflow-hidden">
            <UserButton afterSignOutUrl="/sign-in" />
            <div className="text-left overflow-hidden">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.fullName || "Agent Engineer"}</p>
              <p className="text-[10px] text-slate-500 truncate">{user?.emailAddresses[0]?.emailAddress}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ── */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Dynamic Background Gradients */}
        <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-500/5 rounded-full blur-[100px] pointer-events-none" />

        {/* Header */}
        <header className="h-16 border-b border-slate-900 flex items-center justify-between px-8 bg-slate-950/60 backdrop-blur-md z-10 shrink-0">
          <div className="flex items-center space-x-3">
            {activeTraceId && (
              <button
                onClick={() => {
                  router.push(`/dashboard?project_id=${activeProject?.id}`);
                  setWsSpans([]);
                }}
                className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            )}
            <h1 className="text-md font-semibold text-slate-100">
              {activeTraceId ? "Trace Details" : activeTab === "traces" ? "Agent Traces" : "Project API Credentials"}
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-xs text-slate-500 bg-slate-900 border border-slate-800/80 px-3 py-1.5 rounded-full">
              Org: <span className="text-slate-300 font-medium">{activeOrg?.name}</span>
            </span>
          </div>
        </header>

        {/* Body content based on tab / activeTraceId */}
        <div className="flex-1 overflow-y-auto flex flex-col">

          {/* 1. API KEYS VIEW */}
          {activeTab === "apikeys" && (
            <div className="p-8 max-w-4xl w-full mx-auto space-y-8">
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-slate-200">API Credentials</h2>
                <p className="text-sm text-slate-400">
                  Manage API keys for the project <span className="text-indigo-400">{activeProject?.name}</span>. These keys are used to authenticate your AI agent SDK clients.
                </p>
              </div>

              {/* API Key Creation Form */}
              <div className="p-6 rounded-2xl bg-slate-900/30 border border-slate-900">
                <h3 className="text-sm font-semibold text-slate-200 mb-4">Create New API Key</h3>
                <form 
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!newKeyName.trim()) return;
                    createKeyMutation.mutate(newKeyName);
                  }}
                  className="flex space-x-3"
                >
                  <input
                    type="text"
                    placeholder="e.g. Production Ingestion Key"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
                    required
                  />
                  <button
                    type="submit"
                    className="flex items-center space-x-2 py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition shadow-lg shadow-indigo-600/10"
                    disabled={createKeyMutation.isPending}
                  >
                    {createKeyMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <Plus className="h-4 w-4" />
                        <span>Create Key</span>
                      </>
                    )}
                  </button>
                </form>

                {justCreatedKey && (
                  <div className="mt-6 p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Key Created Successfully</span>
                      <button 
                        onClick={() => setJustCreatedKey(null)}
                        className="text-slate-400 hover:text-white"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="text-xs text-slate-400">
                      Copy this key now. It is stored as a SHA-256 hash in our database — we cannot show it to you again.
                    </p>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                      <code className="text-xs font-mono text-indigo-300 break-all select-all pr-12">
                        {justCreatedKey}
                      </code>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(justCreatedKey);
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        }}
                        className="p-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition"
                      >
                        {copied ? (
                          <ClipboardCheck className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <Clipboard className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* API Keys List */}
              <div className="rounded-2xl border border-slate-900 overflow-hidden bg-slate-950/40">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-900 bg-slate-950/80">
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Name</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Prefix</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Created</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Last Used</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900 text-sm">
                    {keysLoading ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8">
                          <Loader2 className="h-5 w-5 animate-spin mx-auto text-indigo-500" />
                        </td>
                      </tr>
                    ) : apiKeys?.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-slate-500">
                          No API keys found. Create one above to start ingesting spans.
                        </td>
                      </tr>
                    ) : (
                      apiKeys?.map((key) => (
                        <tr key={key.id} className={key.revoked_at ? "opacity-50" : ""}>
                          <td className="px-6 py-4 font-medium text-slate-200">{key.name}</td>
                          <td className="px-6 py-4 font-mono text-xs text-indigo-300">{key.key_prefix}</td>
                          <td className="px-6 py-4 text-slate-400">
                            {new Date(key.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4 text-slate-400">
                            {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : "Never"}
                          </td>
                          <td className="px-6 py-4 text-right">
                            {key.revoked_at ? (
                              <span className="text-xs bg-red-500/10 text-red-400 border border-red-500/20 px-2.5 py-1 rounded-full">
                                Revoked
                              </span>
                            ) : (
                              <button
                                onClick={() => revokeKeyMutation.mutate(key.id)}
                                className="p-2 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 border border-transparent hover:border-red-500/20 transition"
                                title="Revoke API key"
                                disabled={revokeKeyMutation.isPending}
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 2. TRACES LIST VIEW */}
          {activeTab === "traces" && !activeTraceId && (
            <div className="p-8 space-y-6">
              
              {/* Search & Filters */}
              <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/20 border border-slate-900 backdrop-blur-md">
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-400 tracking-wide uppercase">
                    <Filter className="h-4 w-4 text-indigo-400" />
                    <span>Filter:</span>
                  </div>
                  
                  {/* Status Filter */}
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
                  >
                    <option value="all">All Statuses</option>
                    <option value="success">Success</option>
                    <option value="error">Error</option>
                    <option value="running">Running</option>
                  </select>

                  {/* Model Filter */}
                  <select
                    value={modelFilter}
                    onChange={(e) => setModelFilter(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
                  >
                    <option value="all">All Models</option>
                    {uniqueModels.map((m, i) => (
                      <option key={i} value={m}>{m}</option>
                    ))}
                  </select>

                  {/* Date Filter */}
                  <select
                    value={dateRange}
                    onChange={(e) => setDateRange(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
                  >
                    <option value="1h">Last hour</option>
                    <option value="6h">Last 6 hours</option>
                    <option value="24h">Last 24 hours</option>
                    <option value="7d">Last 7 days</option>
                  </select>
                </div>

                <div className="flex items-center space-x-2 text-xs text-slate-500">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span>Auto-refreshing (10s)</span>
                </div>
              </div>

              {/* Traces Table / List */}
              <div className="rounded-2xl border border-slate-900 overflow-hidden bg-slate-950/40">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-900 bg-slate-950/80">
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Trace Name</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Started</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Duration</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Cost</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Tokens</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Spans</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900 text-sm">
                    {tracesLoading ? (
                      <tr>
                        <td colSpan={7} className="text-center py-12">
                          <Loader2 className="h-6 w-6 animate-spin mx-auto text-indigo-500" />
                        </td>
                      </tr>
                    ) : tracesData?.data?.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center py-16">
                          <div className="space-y-4 max-w-lg mx-auto">
                            <Terminal className="h-8 w-8 text-slate-600 mx-auto animate-pulse" />
                            <p className="text-slate-400 font-medium">No traces recorded yet for this project</p>
                            <p className="text-xs text-slate-500">
                              Integrate the Python SDK using your project credentials to start monitoring executions in real time.
                            </p>
                            <div className="p-3 bg-slate-950 border border-slate-900 rounded-xl text-left">
                              <pre className="text-[10px] font-mono text-slate-400">
{`import agentlens as al
al.init(api_key="your_api_key")
al.instrument_openai()`}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      tracesData?.data?.map((trace) => (
                        <tr 
                          key={trace.id}
                          onClick={() => router.push(`/dashboard?project_id=${activeProject?.id}&trace_id=${trace.id}`)}
                          className="hover:bg-slate-900/30 cursor-pointer transition duration-150"
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center space-x-2">
                              {trace.status === "success" && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
                              {trace.status === "error" && <XCircle className="h-4 w-4 text-rose-500 animate-pulse" />}
                              {trace.status === "running" && (
                                <span className="relative flex h-3 w-3">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                                </span>
                              )}
                              <span className={`text-xs font-semibold capitalize ${
                                trace.status === "success" ? "text-emerald-400" :
                                trace.status === "error" ? "text-rose-400" : "text-indigo-400"
                              }`}>
                                {trace.status}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="font-semibold text-slate-200">{trace.name}</div>
                            <div className="text-[10px] text-slate-500 font-mono mt-0.5 break-all select-all">{trace.id}</div>
                          </td>
                          <td className="px-6 py-4 text-slate-400 font-medium">
                            {new Date(trace.started_at).toLocaleTimeString()}
                            <span className="text-xs text-slate-500 block">
                              {new Date(trace.started_at).toLocaleDateString()}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-slate-300 font-mono">
                            {trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : "—"}
                          </td>
                          <td className="px-6 py-4 text-slate-300 font-mono">
                            {trace.total_cost_usd === 0 ? "$0.00" :
                             trace.total_cost_usd < 0.01 ? `$${trace.total_cost_usd.toFixed(4)}` :
                             `$${trace.total_cost_usd.toFixed(2)}`}
                          </td>
                          <td className="px-6 py-4 font-mono text-slate-400 text-xs">
                            {trace.total_tokens.toLocaleString()}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center space-x-1.5">
                              <span className="text-xs font-medium text-slate-300">{trace.span_count} spans</span>
                              {trace.error_count > 0 && (
                                <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                                  {trace.error_count} err
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 3. TRACE DETAIL VIEW */}
          {activeTraceId && traceDetail && (
            <div className="flex-1 flex flex-col overflow-hidden">
              
              {/* Trace Stats Header Bar */}
              <div className="px-8 py-5 border-b border-slate-900 bg-slate-950/40 shrink-0 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-3">
                    <h2 className="text-lg font-bold text-slate-100">{traceDetail.name}</h2>
                    <span className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                      traceDetail.status === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                      traceDetail.status === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" : 
                      "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse"
                    }`}>
                      {traceDetail.status === "running" && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                      {traceDetail.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 font-mono break-all select-all">
                    Trace UUID: {traceDetail.id}
                  </div>
                </div>

                <div className="flex items-center space-x-8">
                  {/* Duration */}
                  <div className="flex items-center space-x-2">
                    <Clock className="h-4.5 w-4.5 text-slate-400" />
                    <div>
                      <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Duration</div>
                      <div className="font-semibold text-slate-200 font-mono">
                        {traceDetail.duration_ms ? `${(traceDetail.duration_ms / 1000).toFixed(2)}s` : "Running"}
                      </div>
                    </div>
                  </div>

                  {/* Total Cost */}
                  <div className="flex items-center space-x-2">
                    <Coins className="h-4.5 w-4.5 text-slate-400" />
                    <div>
                      <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Total Cost</div>
                      <div className="font-semibold text-slate-200 font-mono">
                        {traceDetail.total_cost_usd === 0 ? "$0.00" :
                         traceDetail.total_cost_usd < 0.01 ? `$${traceDetail.total_cost_usd.toFixed(4)}` :
                         `$${traceDetail.total_cost_usd.toFixed(2)}`}
                      </div>
                    </div>
                  </div>

                  {/* Tokens */}
                  <div className="flex items-center space-x-2">
                    <Database className="h-4.5 w-4.5 text-slate-400" />
                    <div>
                      <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Tokens</div>
                      <div className="font-semibold text-slate-200 font-mono">
                        {traceDetail.total_tokens.toLocaleString()}
                      </div>
                    </div>
                  </div>

                  {/* Spans Count */}
                  <div className="flex items-center space-x-2">
                    <Layers className="h-4.5 w-4.5 text-slate-400" />
                    <div>
                      <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Spans</div>
                      <div className="font-semibold text-slate-200">
                        {flatSpanNodes.length} Spans
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Split Screen Panel for Gantt Tree and Inspector */}
              <div className="flex-1 flex overflow-hidden">
                
                {/* ── LEFT PANE: GANTT SPAN TREE ── */}
                <div className="flex-1 border-r border-slate-900 overflow-y-auto p-6 space-y-4 min-w-[50%]">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Span Execution Timeline</div>
                  
                  <div className="space-y-2">
                    {flatSpanNodes.map(({ span, depth }) => {
                      const isSelected = span.id === selectedSpanId;
                      const metrics = getGanttMetrics(span, traceDetail.started_at, traceDetail.duration_ms);

                      return (
                        <div
                          key={span.id}
                          onClick={() => setSelectedSpanId(span.id)}
                          className={`group flex flex-col p-3 rounded-xl border cursor-pointer transition ${
                            isSelected 
                              ? "bg-indigo-600/10 border-indigo-500/40 text-indigo-200" 
                              : span.status === "error"
                              ? "bg-rose-500/5 border-rose-500/20 hover:border-rose-500/30 text-rose-200"
                              : "bg-slate-900/30 border-slate-900 hover:border-slate-800 text-slate-300"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            {/* Span Name and Indentation depth */}
                            <div className="flex items-center space-x-2 overflow-hidden" style={{ paddingLeft: `${depth * 16}px` }}>
                              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                                span.span_type === "llm" ? "bg-indigo-500/15 text-indigo-300" :
                                span.span_type === "tool" ? "bg-emerald-500/15 text-emerald-300" :
                                span.span_type === "retrieval" ? "bg-cyan-500/15 text-cyan-300" :
                                span.span_type === "agent" ? "bg-violet-500/15 text-violet-300" :
                                "bg-slate-800 text-slate-400"
                              }`}>
                                {span.span_type}
                              </span>
                              
                              <span className="font-semibold text-sm truncate">{span.name}</span>
                            </div>

                            {/* Duration Badge */}
                            <div className="flex items-center space-x-2 shrink-0 ml-4">
                              <span className="text-xs font-mono text-slate-400">
                                {span.duration_ms ? `${span.duration_ms}ms` : "running"}
                              </span>
                              
                              {span.status === "error" && <AlertCircle className="h-4 w-4 text-rose-500" />}
                              {span.status === "running" && (
                                <span className="relative flex h-2.5 w-2.5">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Gantt Bar Visualizer */}
                          <div className="relative h-1.5 bg-slate-950/60 rounded-full mt-3 overflow-hidden border border-slate-900/60">
                            <div
                              className={`absolute h-full rounded-full transition-all duration-300 ${
                                span.status === "error" 
                                  ? "bg-rose-500" 
                                  : span.status === "running"
                                  ? "bg-indigo-500 animate-pulse"
                                  : "bg-gradient-to-r from-indigo-500 to-violet-500"
                              }`}
                              style={{ 
                                left: `${metrics.left}%`, 
                                width: `${metrics.width}%` 
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* ── RIGHT PANE: SPAN INSPECTOR ── */}
                <div className="w-[45%] shrink-0 flex flex-col bg-slate-950/40 overflow-hidden">
                  
                  {/* Selected Span Info */}
                  {selectedSpanObj ? (
                    <div className="flex-1 flex flex-col overflow-hidden">
                      <div className="p-6 border-b border-slate-900 space-y-3 shrink-0">
                        <div className="flex items-center justify-between">
                          <h3 className="font-bold text-slate-100 text-md truncate">{selectedSpanObj.name}</h3>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            selectedSpanObj.status === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/25" :
                            selectedSpanObj.status === "error" ? "bg-rose-500/10 text-rose-400 border border-rose-500/25" :
                            "bg-indigo-500/10 text-indigo-400 border border-indigo-500/25"
                          }`}>
                            {selectedSpanObj.status}
                          </span>
                        </div>
                        
                        <div className="flex flex-wrap gap-2">
                          <span className="text-[10px] font-mono bg-slate-900 border border-slate-800 text-slate-300 px-2 py-0.5 rounded">
                            Type: {selectedSpanObj.span_type}
                          </span>
                          {selectedSpanObj.duration_ms !== null && (
                            <span className="text-[10px] font-mono bg-slate-900 border border-slate-800 text-slate-300 px-2 py-0.5 rounded">
                              Duration: {selectedSpanObj.duration_ms}ms
                            </span>
                          )}
                          {selectedSpanObj.cost_usd !== null && selectedSpanObj.cost_usd > 0 && (
                            <span className="text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                              Cost: ${selectedSpanObj.cost_usd.toFixed(4)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Tabs Bar */}
                      <div className="flex border-b border-slate-900 bg-slate-950/80 text-sm shrink-0">
                        {/* Tab Input */}
                        <button
                          onClick={() => setInspectorTab("input")}
                          className={`flex-1 py-3 px-4 text-center border-b-2 font-medium transition ${
                            inspectorTab === "input" 
                              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5" 
                              : "border-transparent text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          Input
                        </button>
                        
                        {/* Tab Output */}
                        <button
                          onClick={() => setInspectorTab("output")}
                          className={`flex-1 py-3 px-4 text-center border-b-2 font-medium transition ${
                            inspectorTab === "output" 
                              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5" 
                              : "border-transparent text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          Output
                        </button>

                        {/* Tab LLM Metadata for LLM spans */}
                        {selectedSpanObj.span_type === "llm" && (
                          <button
                            onClick={() => setInspectorTab("llm")}
                            className={`flex-1 py-3 px-4 text-center border-b-2 font-medium transition ${
                              inspectorTab === "llm" 
                                ? "border-indigo-500 text-indigo-400 bg-indigo-500/5" 
                                : "border-transparent text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            LLM details
                          </button>
                        )}

                        {/* Tab Error if error state */}
                        {selectedSpanObj.status === "error" && (
                          <button
                            onClick={() => setInspectorTab("error")}
                            className={`flex-1 py-3 px-4 text-center border-b-2 font-medium transition ${
                              inspectorTab === "error" 
                                ? "border-indigo-500 text-rose-400 bg-rose-500/5" 
                                : "border-transparent text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            Error
                          </button>
                        )}

                        {/* Metadata Tab */}
                        <button
                          onClick={() => setInspectorTab("metadata")}
                          className={`flex-1 py-3 px-4 text-center border-b-2 font-medium transition ${
                            inspectorTab === "metadata" 
                              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5" 
                              : "border-transparent text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          Metadata
                        </button>
                      </div>

                      {/* Inspector Content Panel */}
                      <div className="flex-1 overflow-y-auto p-6 font-mono text-xs text-slate-300">
                        {/* Tab: Input */}
                        {inspectorTab === "input" && (
                          <div className="space-y-4">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Captured Payload Input</div>
                            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-900 overflow-x-auto whitespace-pre-wrap select-all">
                              {JSON.stringify(selectedSpanObj.input, null, 2)}
                            </pre>
                          </div>
                        )}

                        {/* Tab: Output */}
                        {inspectorTab === "output" && (
                          <div className="space-y-4">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Captured Payload Output</div>
                            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-900 overflow-x-auto whitespace-pre-wrap select-all">
                              {JSON.stringify(selectedSpanObj.output, null, 2)}
                            </pre>
                          </div>
                        )}

                        {/* Tab: LLM */}
                        {inspectorTab === "llm" && (
                          <div className="space-y-4">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">LLM Model Metrics</div>
                            <div className="grid grid-cols-2 gap-4">
                              <div className="p-4 rounded-xl bg-slate-950 border border-slate-900 space-y-1">
                                <div className="text-[10px] font-semibold text-slate-500 uppercase">Model</div>
                                <div className="font-semibold text-indigo-300">{selectedSpanObj.model || "unknown"}</div>
                              </div>
                              <div className="p-4 rounded-xl bg-slate-950 border border-slate-900 space-y-1">
                                <div className="text-[10px] font-semibold text-slate-500 uppercase">Provider</div>
                                <div className="font-semibold text-indigo-300 capitalize">{selectedSpanObj.provider || "unknown"}</div>
                              </div>
                              <div className="p-4 rounded-xl bg-slate-950 border border-slate-900 space-y-1">
                                <div className="text-[10px] font-semibold text-slate-500 uppercase">Input Tokens</div>
                                <div className="font-semibold text-slate-200 font-mono">{selectedSpanObj.input_tokens || 0}</div>
                              </div>
                              <div className="p-4 rounded-xl bg-slate-950 border border-slate-900 space-y-1">
                                <div className="text-[10px] font-semibold text-slate-500 uppercase">Output Tokens</div>
                                <div className="font-semibold text-slate-200 font-mono">{selectedSpanObj.output_tokens || 0}</div>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Tab: Error */}
                        {inspectorTab === "error" && (
                          <div className="space-y-4">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider text-rose-400">Exception Information</div>
                            
                            <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/10 space-y-2">
                              <div className="font-bold text-rose-400">{selectedSpanObj.error_type}</div>
                              <div className="text-slate-300 font-sans">{selectedSpanObj.error_message}</div>
                            </div>

                            {selectedSpanObj.error_stack && (
                              <div className="space-y-2">
                                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Stack Trace</div>
                                <pre className="p-4 rounded-xl bg-slate-950 border border-slate-900 overflow-x-auto whitespace-pre select-all text-[10px] text-rose-300/80">
                                  {selectedSpanObj.error_stack}
                                </pre>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Tab: Metadata */}
                        {inspectorTab === "metadata" && (
                          <div className="space-y-4">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Extended Attributes</div>
                            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-900 overflow-x-auto whitespace-pre-wrap select-all">
                              {JSON.stringify(selectedSpanObj.metadata || {}, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center p-8 text-slate-500 text-center">
                      Select a Span to inspect its payloads
                    </div>
                  )}

                </div>
              </div>

            </div>
          )}

        </div>
      </main>
    </div>
  );
}

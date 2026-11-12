import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, CloudOff, LoaderCircle, RefreshCw, Send, Trash2, Volume2 } from "lucide-react";
import { toast } from "sonner";

import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { WORKER_ORDER } from "@/lib/agents";
import { useI18n } from "@/lib/i18n";
import { formatWhen } from "@/lib/format";
import { speak } from "@/lib/speech";
import type { Agent, Briefing, BriefingSettings, Channel, Mission, Project, StoreItem, Task } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import AgentAvatar from "@/components/AgentAvatar";
import AgentHistoryButton from "@/components/AgentHistoryButton";
import AgentModelEditor from "@/components/AgentModelEditor";
import BrainBadge from "@/components/BrainBadge";
import StatusBadge from "@/components/StatusBadge";
import RoomStream from "@/components/RoomStream";
import DataRegionState from "@/components/DataRegionState";
import ActionErrorNotice from "@/components/ActionErrorNotice";

const CHIPS = ["chip.weather", "chip.store", "chip.emails", "chip.cameras"];

const HEALTH_AREAS = [
  { id: "agents", queryKey: ["agents"], label: "health.agents" },
  { id: "projects", queryKey: ["projects"], label: "health.projects" },
  { id: "tasks", queryKey: ["tasks"], label: "health.tasks" },
  { id: "room", queryKey: ["room"], label: "health.room" },
  { id: "store", queryKey: ["store"], label: "health.store" },
  { id: "channels", queryKey: ["channels"], label: "health.channels" },
] as const;

type HealthStatus = "online" | "loading" | "stale" | "offline" | "unchecked";
type HealthEvent = { id: string; areaId: string; kind: "outage" | "recovered"; at: string };
const HEALTH_EVENTS_KEY = "qgzero.healthEvents";

function healthStatus(state: ReturnType<ReturnType<typeof useQueryClient>["getQueryState"]>): HealthStatus {
  if (!state) return "unchecked";
  if (state.status === "pending") return "loading";
  if (state.status === "error") return state.data !== undefined ? "stale" : "offline";
  return "online";
}

function HealthStatusIcon({ status }: { status: HealthStatus }) {
  if (status === "online") return <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />;
  if (status === "stale") return <AlertTriangle className="size-4 text-amber-600" aria-hidden="true" />;
  if (status === "offline") return <CloudOff className="size-4 text-red-600" aria-hidden="true" />;
  return <LoaderCircle className={`size-4 text-slate-400 ${status === "loading" ? "animate-spin" : ""}`} aria-hidden="true" />;
}

function OperationalHealthCard() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [, setRevision] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const previous = useRef<Record<string, HealthStatus>>({});
  const [events, setEvents] = useState<HealthEvent[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(HEALTH_EVENTS_KEY) ?? "[]") as HealthEvent[];
    } catch {
      return [];
    }
  });

  useEffect(
    () => queryClient.getQueryCache().subscribe(() => setRevision((value) => value + 1)),
    [queryClient],
  );

  const rows = HEALTH_AREAS.map((area) => {
    const state = queryClient.getQueryState(area.queryKey);
    return { ...area, status: healthStatus(state), updatedAt: state?.dataUpdatedAt ?? 0 };
  });
  const statusSignature = rows.map((row) => `${row.id}:${row.status}`).join("|");

  useEffect(() => {
    const nextEvents: HealthEvent[] = [];
    for (const row of rows) {
      const before = previous.current[row.id];
      previous.current[row.id] = row.status;
      if (!before || before === row.status) continue;
      if (row.status === "offline" || row.status === "stale") {
        nextEvents.push({ id: `${Date.now()}-${row.id}-outage`, areaId: row.id, kind: "outage", at: new Date().toISOString() });
      } else if (row.status === "online" && (before === "offline" || before === "stale")) {
        nextEvents.push({ id: `${Date.now()}-${row.id}-recovered`, areaId: row.id, kind: "recovered", at: new Date().toISOString() });
      }
    }
    if (nextEvents.length) {
      setEvents((current) => {
        const updated = [...nextEvents.reverse(), ...current].slice(0, 8);
        localStorage.setItem(HEALTH_EVENTS_KEY, JSON.stringify(updated));
        return updated;
      });
    }
  }, [statusSignature]);

  const areaLabel = (areaId: string) => t(HEALTH_AREAS.find((area) => area.id === areaId)?.label ?? areaId);
  const refreshAll = async () => {
    setRefreshing(true);
    try {
      await Promise.all(
        HEALTH_AREAS.map((area) => queryClient.refetchQueries({ queryKey: area.queryKey, exact: true })),
      );
    } finally {
      setRefreshing(false);
    }
  };
  const clearHistory = () => {
    localStorage.removeItem(HEALTH_EVENTS_KEY);
    setEvents([]);
  };

  return (
    <Card data-testid="operational-health-card">
      <CardHeader className="flex-row items-center justify-between gap-2 pb-3">
        <CardTitle className="flex items-center gap-2 font-heading text-base" data-testid="operational-health-title">
          <Activity className="size-4 text-blue-600" aria-hidden="true" />
          {t("health.title")}
        </CardTitle>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-11 sm:h-8"
          data-testid="health-refresh-all-button"
          disabled={refreshing}
          onClick={() => void refreshAll()}
        >
          <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
          {refreshing ? t("health.refreshing") : t("health.refresh")}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1" data-testid="operational-health-areas">
          {rows.map((row) => (
            <div key={row.id} className="flex items-center gap-2 rounded-lg border bg-white p-2.5" data-testid={`health-area-${row.id}`}>
              <HealthStatusIcon status={row.status} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold" data-testid={`health-area-${row.id}-label`}>{t(row.label)}</p>
                <p className="text-[10px] text-muted-foreground" data-testid={`health-area-${row.id}-updated`}>
                  {row.updatedAt ? `${t("health.updated")} ${formatWhen(new Date(row.updatedAt).toISOString(), lang)}` : t("health.notChecked")}
                </p>
              </div>
              <span className="text-[11px] font-semibold" data-testid={`health-area-${row.id}-status`}>{t(`health.status.${row.status}`)}</span>
            </div>
          ))}
        </div>
        <div className="border-t pt-3" data-testid="health-event-history">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500" data-testid="health-history-title">{t("health.history")}</p>
            {events.length > 0 && (
              <button
                type="button"
                className="inline-flex min-h-11 items-center gap-1 text-[11px] font-semibold text-slate-500 hover:text-slate-800 sm:min-h-8"
                data-testid="health-history-clear-button"
                onClick={clearHistory}
              >
                <Trash2 className="size-3" aria-hidden="true" />
                {t("health.clear")}
              </button>
            )}
          </div>
          {events.length === 0 ? (
            <p className="text-xs text-muted-foreground" data-testid="health-history-empty">{t("health.historyEmpty")}</p>
          ) : (
            <div className="space-y-1.5">
              {events.slice(0, 4).map((event) => (
                <p key={event.id} className="flex items-center justify-between gap-2 text-xs" data-testid={`health-event-${event.id}`}>
                  <span>{areaLabel(event.areaId)} · {t(`health.event.${event.kind}`)}</span>
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{formatWhen(event.at, lang)}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function AgentNode({ agentKey, agent }: { agentKey: string; agent?: Agent }) {
  const { t, lang } = useI18n();
  const name = agent?.name ?? agentKey.charAt(0).toUpperCase() + agentKey.slice(1);
  const role = agent ? (lang === "pt" ? agent.role_pt : agent.role_en) : "";
  return (
    <div data-testid={`agent-card-${agentKey}`} className="rounded-lg border bg-white p-3 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center gap-2.5">
        <AgentAvatar agentKey={agentKey} active={agent?.status === "working"} size={38} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-heading text-sm font-bold">{name}</span>
            {agent && (
              <BrainBadge
                provider={agent.provider}
                model={agent.model}
                testId={`agent-provider-badge-${agentKey}`}
              />
            )}
            {agent?.status === "working" && (
              <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                {t("status.working")}
              </span>
            )}
          </div>
          <p className="truncate text-xs text-muted-foreground">{role}</p>
        </div>
        {agent && agent.open_tasks > 0 && (
          <span className="ml-auto shrink-0 rounded-full bg-blue-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-blue-700" data-testid={`agent-open-tasks-${agentKey}`}>
            {agent.open_tasks} {t("hierarchy.openTasks")}
          </span>
        )}
        {agent && <AgentHistoryButton agent={agent} />}
        {agent && <AgentModelEditor agent={agent} />}
      </div>
      {agent && (
        <p className="mt-2 border-t pt-2 font-mono text-[11px] text-slate-500" data-testid={`agent-brain-${agentKey}`}>
          {t("hierarchy.brain")}: {agent.brain}
        </p>
      )}
    </div>
  );
}

function Connector() {
  return (
    <div className="flex items-center justify-center py-0.5">
      <div className="h-3 w-px bg-border" />
      <div className="size-1.5 rounded-full bg-blue-400/70" />
      <div className="h-3 w-px bg-border" />
    </div>
  );
}

function HierarchyPanel() {
  const { t } = useI18n();
  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiGet<Agent[]>("/agents"),
    refetchInterval: 3000,
  });
  const agents = agentsQuery.data;
  const byKey = new Map((agents ?? []).map((a) => [a.key, a]));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-base">{t("hierarchy.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-0">
        <DataRegionState query={agentsQuery} testId="cockpit-agents-data" className="mb-3" />
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3" data-testid="agent-card-boss">
          <div className="flex items-center gap-2.5">
            <AgentAvatar agentKey="user" size={38} />
            <div className="min-w-0">
              <p className="truncate font-heading text-sm font-bold">{t("hierarchy.boss")}</p>
              <p className="truncate text-xs text-muted-foreground">{t("hierarchy.bossSub")}</p>
            </div>
          </div>
        </div>
        <Connector />
        <AgentNode agentKey="zero" agent={byKey.get("zero")} />
        <Connector />
        <AgentNode agentKey="pro" agent={byKey.get("pro")} />
        <Connector />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-1">
          {WORKER_ORDER.map((key) => (
            <AgentNode key={key} agentKey={key} agent={byKey.get(key)} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MissionPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [projectId, setProjectId] = useState("none");
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => apiGet<Project[]>("/projects") });
  const projects = projectsQuery.data;
  const projectName = (id: string) => (id === "none" ? t("projects.pick") : (projects ?? []).find((p) => p.id === id)?.name ?? id);

  const dispatch = useMutation({
    mutationFn: (text: string) => apiPost<Mission>("/missions", { text, project_id: projectId === "none" ? null : projectId }),
    onSuccess: () => {
      setDraft("");
      toast.success(t("mission.sent"));
      for (const key of ["missions", "tasks", "room", "agents"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
    onError: () => toast.error(t("mission.error")),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-base">{t("mission.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          data-testid="mission-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={t("mission.placeholder")}
          rows={3}
        />
        <DataRegionState query={projectsQuery} testId="cockpit-mission-projects-data" />
        <Select value={projectId} onValueChange={(v: string) => setProjectId(v)}>
          <SelectTrigger className="w-full" data-testid="mission-project-select">
            <SelectValue>{(v) => `📁 ${projectName(v as string)}`}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">{t("projects.pick")}</SelectItem>
            {(projects ?? []).map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex flex-wrap gap-1.5">
          {CHIPS.map((chip, i) => (
            <button
              key={chip}
              data-testid={`mission-chip-${i}`}
              onClick={() => setDraft(t(chip))}
              className="min-h-11 rounded-full border border-border bg-white px-3 py-1.5 text-xs text-slate-600 transition-colors hover:bg-slate-50"
            >
              {t(chip)}
            </button>
          ))}
        </div>
        <Button
          data-testid="dispatch-mission-btn"
          className="w-full"
          size="lg"
          disabled={!draft.trim() || draft.trim().length < 3 || dispatch.isPending}
          onClick={() => draft.trim() && dispatch.mutate(draft.trim())}
        >
          <Send className="size-4" />
          {dispatch.isPending ? t("mission.sending") : t("mission.send")}
        </Button>
        <ActionErrorNotice
          visible={dispatch.isError}
          pending={dispatch.isPending}
          testId="mission-dispatch"
          mayDuplicate
          onDismiss={() => dispatch.reset()}
          onRetry={() => {
            const text = dispatch.variables ?? draft.trim();
            if (text) dispatch.mutate(text);
          }}
        />
      </CardContent>
    </Card>
  );
}

const BRIEFING_HOURS = [5, 6, 7, 8, 9, 10];

function BriefingCard() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [cityDraft, setCityDraft] = useState("");

  const briefingsQuery = useQuery({
    queryKey: ["briefings"],
    queryFn: () => apiGet<Briefing[]>("/briefing"),
    refetchInterval: 10000,
  });
  const settingsQuery = useQuery({
    queryKey: ["briefing-settings"],
    queryFn: () => apiGet<BriefingSettings>("/briefing/settings"),
  });
  const briefings = briefingsQuery.data;
  const settings = settingsQuery.data;

  useEffect(() => {
    if (settings?.city) setCityDraft(settings.city);
  }, [settings?.city]);

  const run = useMutation({
    mutationFn: () => apiPost<Briefing>("/briefing/run"),
    onSuccess: () => {
      toast.success(t("briefing.done"));
      queryClient.invalidateQueries({ queryKey: ["briefings"] });
      queryClient.invalidateQueries({ queryKey: ["room"] });
    },
    onError: () => toast.error(t("common.error")),
  });

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiPatch<BriefingSettings>("/briefing/settings", body),
    onSuccess: () => {
      toast.success(t("briefing.saved"));
      queryClient.invalidateQueries({ queryKey: ["briefing-settings"] });
    },
    onError: () => toast.error(t("common.error")),
  });

  const latest = briefings?.[0];

  return (
    <Card data-testid="briefing-card">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="font-heading text-base">{t("briefing.title")}</CardTitle>
        <div className="flex gap-1.5">
          {latest && (
            <Button size="sm" variant="outline" data-testid="briefing-listen-btn" onClick={() => speak(latest.content)}>
              <Volume2 className="size-4" />
              {t("briefing.listen")}
            </Button>
          )}
          <Button size="sm" data-testid="briefing-run-btn" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? t("briefing.running") : t("briefing.run")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ActionErrorNotice
          visible={run.isError}
          pending={run.isPending}
          testId="briefing-run"
          mayDuplicate
          onDismiss={() => run.reset()}
          onRetry={() => run.mutate()}
        />
        <ActionErrorNotice
          visible={save.isError}
          pending={save.isPending}
          testId="briefing-settings-save"
          onDismiss={() => save.reset()}
          onRetry={() => save.variables && save.mutate(save.variables)}
        />
        <DataRegionState query={briefingsQuery} testId="cockpit-briefings-data" />
        <DataRegionState query={settingsQuery} testId="cockpit-briefing-settings-data" />
        {settings && (
          <div className="flex flex-wrap items-center gap-3" data-testid="briefing-settings-controls">
            <label className="flex min-h-11 items-center gap-2 text-xs font-medium">
              <Checkbox
                data-testid="briefing-auto-toggle"
                checked={settings.auto}
                onCheckedChange={(c) => save.mutate({ auto: Boolean(c) })}
              />
              {t("briefing.auto")}
            </label>
            <Select value={String(settings.hour)} onValueChange={(v: string) => save.mutate({ hour: Number(v) })}>
              <SelectTrigger size="sm" className="w-20" data-testid="briefing-hour-select">
                <SelectValue>{(v) => `${v as string}h`}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {BRIEFING_HOURS.map((h) => (
                  <SelectItem key={h} value={String(h)}>
                    {`${h}h`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              data-testid="briefing-city-input"
              value={cityDraft}
              onChange={(e) => setCityDraft(e.target.value)}
              onBlur={() => {
                if (cityDraft.trim() && cityDraft.trim() !== settings.city) save.mutate({ city: cityDraft.trim() });
              }}
              placeholder={t("briefing.city")}
              className="h-9 w-36 text-xs"
            />
          </div>
        )}
        {latest ? (
          <div className="rounded-lg border bg-sky-50/50 p-3" data-testid="briefing-latest">
            <p className="mb-1 font-mono text-[11px] text-slate-500">
              {latest.day} · {latest.city}
            </p>
            <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-relaxed">{latest.content.replace(/\*\*/g, "")}</p>
          </div>
        ) : briefings !== undefined ? (
          <p className="text-sm text-muted-foreground" data-testid="briefing-empty">
            {t("briefing.empty")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function StatsRow() {
  const { t } = useI18n();
  const missionsQuery = useQuery({ queryKey: ["missions"], queryFn: () => apiGet<Mission[]>("/missions"), refetchInterval: 3000 });
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: () => apiGet<Task[]>("/tasks"), refetchInterval: 3000 });
  const missions = missionsQuery.data;
  const tasks = tasksQuery.data;

  const active = (missions ?? []).filter((m) => m.status === "planning" || m.status === "delegating").length;
  const queued = (tasks ?? []).filter((x) => x.status === "queued" || x.status === "working").length;
  const done = (tasks ?? []).filter((x) => x.status === "verified").length;
  const review = (tasks ?? []).filter((x) => x.status === "review").length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="stats-row">
      <DataRegionState query={missionsQuery} testId="cockpit-missions-data" className="col-span-2 sm:col-span-4" />
      <DataRegionState query={tasksQuery} testId="cockpit-tasks-data" className="col-span-2 sm:col-span-4" />
      {[
        { label: t("stats.active"), value: missions === undefined ? "—" : active, tid: "stat-active" },
        { label: t("stats.queued"), value: tasks === undefined ? "—" : queued, tid: "stat-queued" },
        { label: t("status.review"), value: tasks === undefined ? "—" : review, tid: "stat-review" },
        { label: t("status.verified"), value: tasks === undefined ? "—" : done, tid: "stat-done" },
      ].map(({ label, value, tid }) => (
        <div key={tid} className="rounded-lg border bg-white p-3 text-center shadow-sm">
          <p className="font-heading text-2xl font-bold text-blue-600" data-testid={tid}>
            {value}
          </p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      ))}
    </div>
  );
}

function TasksPreview() {
  const { t } = useI18n();
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: () => apiGet<Task[]>("/tasks"), refetchInterval: 3000 });
  const tasks = tasksQuery.data;
  const shown = (tasks ?? []).slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="font-heading text-base">{t("tasks.preview")}</CardTitle>
        <Link to="/tarefas" data-testid="tasks-preview-link" className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline">
          {t("tasks.openFull")}
          <ArrowRight className="size-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRegionState query={tasksQuery} testId="cockpit-task-preview-data" />
        {tasks !== undefined && shown.length === 0 && <p className="py-2 text-sm text-muted-foreground" data-testid="cockpit-task-preview-empty">{t("tasks.empty")}</p>}
        {shown.map((task) => (
          <div key={task.id} data-testid={`task-preview-${task.id}`} className="flex items-center gap-2.5 rounded-lg border bg-white p-2.5">
            <AgentAvatar agentKey={task.agent_key} size={28} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{task.title}</span>
            <StatusBadge status={task.status} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function StoreCard() {
  const { t } = useI18n();
  const storeQuery = useQuery({ queryKey: ["store"], queryFn: () => apiGet<StoreItem[]>("/store/items"), refetchInterval: 5000 });
  const items = storeQuery.data;
  const all = items ?? [];
  const groups = [
    { key: "stock", status: "critical", label: "store.stock", dot: "bg-red-500" },
    { key: "order", status: "open", label: "store.order", dot: "bg-blue-500" },
    { key: "coupon", status: "active", label: "store.coupon", dot: "bg-emerald-500" },
  ];
  return (
    <Card data-testid="store-card">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="font-heading text-base">{t("store.title")}</CardTitle>
        <Link to="/loja" data-testid="store-preview-link" className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline">
          {t("store.openFull")}
          <ArrowRight className="size-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        <DataRegionState query={storeQuery} testId="cockpit-store-data" />
        {groups.map((g) => {
          const hot = all.filter((i) => i.kind === g.key && i.status === g.status);
          return (
            <div key={g.key} data-testid={`store-group-${g.key}`}>
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-600">
                <span className={`size-2 rounded-full ${g.dot}`} />
                {t(g.label)} · {t(`store.${g.status}`)} <span className="font-mono">({items === undefined ? "—" : hot.length})</span>
              </p>
              {hot.slice(0, 3).map((i) => (
                <p key={i.id} className="truncate pl-3.5 text-sm">
                  {i.title} <span className="font-mono text-xs text-muted-foreground">{i.value}</span>
                </p>
              ))}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function ChannelsPreview() {
  const { t, lang } = useI18n();
  const channelsQuery = useQuery({ queryKey: ["channels"], queryFn: () => apiGet<Channel[]>("/channels"), refetchInterval: 5000 });
  const channels = channelsQuery.data;
  const shown = (channels ?? []).slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="font-heading text-base">{t("channels.preview")}</CardTitle>
        <Link to="/canais" data-testid="channels-preview-link" className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline">
          {t("channels.openFull")}
          <ArrowRight className="size-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-2">
        <DataRegionState query={channelsQuery} testId="cockpit-channels-data" />
        {channels !== undefined && shown.length === 0 && <p className="text-sm text-muted-foreground" data-testid="cockpit-channels-empty">{t("channels.empty")}</p>}
        {shown.map((ch) => (
          <div key={ch.id} data-testid={`channel-preview-${ch.key}`} className="flex items-center gap-2.5">
            <span className={`size-2 shrink-0 rounded-full ${ch.status === "connected" ? "bg-emerald-500" : "bg-slate-300"}`} />
            <span className="min-w-0 flex-1 truncate text-sm">{ch.name}</span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {ch.status === "connected" ? t("channels.connected") : t("channels.disconnected")}
            </span>
          </div>
        ))}
        <p className="pt-1 text-[11px] text-muted-foreground">{lang === "pt" ? "Conexões do Zero com o mundo" : "Zero's connections to the world"}</p>
      </CardContent>
    </Card>
  );
}

export default function Cockpit() {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-[1600px] space-y-4 p-3 sm:space-y-5 sm:p-6">
      <header className="space-y-1">
        <h1 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl" data-testid="cockpit-title">
          {t("cockpit.greeting")}
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">{t("cockpit.sub")}</p>
      </header>

      <StatsRow />

      <div className="grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-12">
        <div className="space-y-4 sm:space-y-5 lg:col-span-3">
          <HierarchyPanel />
        </div>
        <div className="space-y-4 sm:space-y-5 lg:col-span-5">
          <MissionPanel />
          <Card className="flex min-h-[320px] flex-col">
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="font-heading text-base">{t("room.title")}</CardTitle>
              <Link to="/sala" data-testid="room-preview-link" className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline">
                {t("room.openFull")}
                <ArrowRight className="size-3.5" />
              </Link>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col pt-0">
              <RoomStream limit={8} />
            </CardContent>
          </Card>
        </div>
        <div className="space-y-4 sm:space-y-5 lg:col-span-4">
          <BriefingCard />
          <OperationalHealthCard />
          <StoreCard />
          <TasksPreview />
          <ChannelsPreview />
        </div>
      </div>
    </div>
  );
}

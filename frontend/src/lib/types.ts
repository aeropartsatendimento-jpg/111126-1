// Hand-written mirrors of the Pydantic models in backend/models/models.py.
// Nothing infers across the HTTP boundary — keep this file in sync in the same edit.

export interface Agent {
  id: string;
  key: string;
  name: string;
  role_pt: string;
  role_en: string;
  description_pt: string;
  description_en: string;
  provider: string;
  model: string;
  brain: string;
  status: string;
  open_tasks: number;
  created_at: string;
}

export interface AgentModelUpdate {
  provider: string; // openai | anthropic | gemini
  model: string;
  brain?: string | null;
}

export interface AgentModelChange {
  id: string;
  agent_key: string;
  from_provider: string;
  from_model: string;
  from_brain: string;
  to_provider: string;
  to_model: string;
  to_brain: string;
  created_at: string;
}

export interface Mission {
  id: string;
  text: string;
  status: string; // planning | delegating | completed | failed
  plan_intro: string | null;
  project_id: string | null;
  created_at: string;
}

export interface Task {
  id: string;
  mission_id: string;
  mission_text: string;
  agent_key: string;
  title: string;
  detail: string;
  status: string; // queued | working | review | verified | rejected | failed
  result: string | null;
  project_id: string | null;
  review_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoomMessage {
  id: string;
  sender_key: string; // user | zero | pro | jarvis | aluna | plus | system
  kind: string; // chat | delegation | system | summary
  content: string;
  mission_id: string | null;
  created_at: string;
}

export interface DirectMessage {
  id: string;
  role: string; // user | zero
  content: string;
  intent: string; // explicando | propondo | executando
  proposal: string | null;
  project_id: string | null;
  mission_id: string | null;
  created_at: string;
}

export interface Channel {
  id: string;
  key: string; // whatsapp | facebook | internet | visual | mcp
  name: string;
  description_pt: string;
  description_en: string;
  status: string; // connected | disconnected
  config: Record<string, string>;
  updated_at: string;
}

export interface VisualMissionStep {
  key: string;
  label: string;
  detail: string;
  status: string; // pending | completed
}

export interface VisualBrowserAction {
  type: string; // open | read | click | write | copy | paste
  label: string;
  target: string;
  status: string; // pending | completed
  output: string;
}

export interface VisualMission {
  id: string;
  url: string;
  objective: string;
  status: string; // queued | running | completed | failed
  mode: string; // simulated
  steps: VisualMissionStep[];
  actions: VisualBrowserAction[];
  result: string | null;
  created_at: string;
  updated_at: string;
}

export interface SearchHit {
  title: string;
  url: string;
  snippet: string;
}

export interface SearchResponse {
  query: string;
  engine: string;
  results: SearchHit[];
}

export interface SystemInfo {
  app: string;
  llm_configured: boolean;
  brain: string; // cloud | simulated
}

export interface Briefing {
  id: string;
  day: string; // YYYY-MM-DD (America/Sao_Paulo)
  city: string;
  content: string;
  created_at: string;
}

export interface BriefingSettings {
  auto: boolean;
  hour: number;
  city: string;
}

export interface CronWebhookEnvelope {
  event: "schedule.triggered";
  schedule_id: string;
  run_id: string | null;
  dispatch_time: string | null;
  job_id: string | null;
  data: null;
}

export interface CronWebhookAck {
  accepted: boolean;
  duplicate: boolean;
  run_id: string;
}

export interface Project {
  id: string;
  name: string;
  objective: string;
  status: string; // active | paused | done
  in_progress: string;
  blocker: string;
  next_step: string;
  last_verified: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Account {
  id: string;
  name: string;
  provider: string;
  status: string; // available | busy | offline | unverified
  note: string;
  created_at: string;
}

export interface StoreItem {
  id: string;
  kind: string; // stock | order | coupon
  title: string;
  detail: string;
  value: string;
  status: string; // stock: critical|ok · order: open|done · coupon: active|expired
  is_sample: boolean;
  updated_at: string;
}

export interface McpInfo {
  path: string;
  token_configured: boolean;
  tools: string[];
}

export interface Memory {
  id: string;
  kind: string; // decisao_chefe | fato_verificado | proposta | antiga
  title: string;
  content: string;
  source: string;
  project_id: string | null;
  replaces: string | null;
  superseded_by: string | null;
  created_at: string;
}

export interface ReflectionInfo {
  verdict: 'CONFIRM' | 'CORRECT';
  quality_score: number;
  gaps: string[];
  corrections: string[];
}

export interface ExecutionStep {
  execution_id?: string;
  step_number: number;
  agent_name: string;
  tool_name: string;
  intent?: string;
  status: string;
  result_summary: string;
  duration_seconds: number;
}

export interface ChatResponse {
  execution_id: string;
  request_id: string;
  answer: string;
  intent?: string;
  agents_used: string[];
  tools_used: string[];
  execution_steps?: ExecutionStep[];
  metrics: Record<string, any>;
  reflection: ReflectionInfo;
  data_source: string;
  elapsed_seconds: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  responseDetails?: ChatResponse;
}

export interface AgentInfo {
  name: string;
  description: string;
  role: string;
}

export interface ToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, any>;
}

export interface HealthInfo {
  status: string;
  app: string;
  version: string;
  env: string;
  data_source: string;
}

export interface ReadinessInfo {
  status: string;
  components: Record<string, {
    status: string;
    detail: string;
    latency_ms?: number;
    mode?: string;
    tools_count?: number;
  }>;
  timestamp: string;
}



export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  org_id: string;
  org_name?: string;
}


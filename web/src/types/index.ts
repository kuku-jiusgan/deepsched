export interface Project {
  id: number;
  name: string;
  code: string;
  client_name?: string;
  priority: number;
  sla_level?: string;
  status: string;
  profit_weight: number;
  manager_id?: number | null;
  manager_name?: string;
  start_date?: string;
  end_date?: string;
  tasks: Task[];
}

export interface Task {
  id: number;
  project_id: number;
  name: string;
  task_type: string;
  requires_instrument: boolean;
  requires_human: boolean;
  est_duration_hours?: number;
  switchover_hours: number;
  status: string;
  earliest_start?: string;
  latest_due?: string;
  priority_weight: number;
  instrument_ids: number[];
  predecessor_ids: number[];
  assignee_id: number | null;
  assignee_name: string | null;
  parent_id: number | null;
  children?: Task[];
}

export interface CapabilityReq {
  id: number;
  tag_name: string;
  tag_value: string;
}

export interface Instrument {
  id: number;
  code: string;
  name: string;
  instrument_group: string;
  brand?: string;
  model?: string;
  location?: string;
  availability_status: 'available' | 'unavailable';
  status: string;
  buffer_rate: number;
  switchover_base_hours: number;
  capabilities: CapabilityReq[];
}

export interface InstrumentFault {
  id: number;
  instrument_id: number | null;
  reported_at: string;
  estimated_resolved_at: string | null;
  resolved_at: string | null;
  description: string;
  status: string;
  schedule_impact?: {
    shifted_slots: number;
    affected_tasks: number;
    notified_users: number;
  };
  affected_tasks?: FaultAffectedTask[];
}

export interface FaultAffectedTask {
  task_id: number;
  task_name: string;
  project_id: number | null;
  project_name: string | null;
  project_code: string | null;
  assignee_name: string | null;
  original_start: string;
  original_end: string;
  shifted_start: string;
  shifted_end: string;
  can_shift: boolean;
  reason: string;
}

export interface TimeSlot {
  id: number;
  task_id: number;
  instrument_id: number;
  plan_start: string;
  plan_end: string;
  actual_start?: string;
  actual_end?: string;
  tier: string;
  status: string;
  task_name?: string;
  task_type?: string | null;
  project_code?: string | null;
  project_name?: string;
  instrument_name?: string;
  assignee_name?: string;
  project_id?: number | null;
  delay_hours?: number | null;
  delay_reason?: string | null;
  delay_reported_at?: string | null;
}

export interface DashboardData {
  total_instruments: number;
  active_instruments: number;
  total_projects: number;
  active_projects: number;
  avg_utilization: number;
  delayed_tasks: number;
  buffer_warnings: string[];
  milestone_risks: { project: string; milestone: string; due_date: string }[];
}

export interface UtilizationStats {
  instrument_id: number;
  instrument_name: string;
  instrument_code?: string | null;
  total_available_hours: number;
  scheduled_hours: number;
  actual_run_hours: number;
  expected_utilization_rate: number;
  actual_utilization_rate: number;
  utilization_rate: number;
  buffer_consumed_rate: number;
}

export interface DAGData {
  nodes: { id: number; name: string; type: string; requires_instrument: boolean; status: string }[];
  edges: { from: number; to: number }[];
}

export interface InsertCost {
  displaced_tasks: { task_id: number; task_name: string; project_name: string; original_start: string; delay_hours: number }[];
  affected_projects: { name: string }[];
  milestone_violations: { project: string; milestone: string; days_late: number }[];
  total_delay_hours: number;
}

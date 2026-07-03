export interface Project {
  id: number;
  name: string;
  code: string;
  client_name?: string;
  priority: number;
  sla_level?: string;
  status: string;
  profit_weight: number;
  manager?: string;
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
  capability_requirements: CapabilityReq[];
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
  status: string;
  buffer_rate: number;
  switchover_base_hours: number;
  capabilities: CapabilityReq[];
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
  project_name?: string;
  instrument_name?: string;
  assignee_name?: string;
  project_id?: number;
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
  total_available_hours: number;
  scheduled_hours: number;
  actual_run_hours: number;
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

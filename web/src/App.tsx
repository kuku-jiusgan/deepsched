import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';

// 运营数据中台
import Dashboard from './pages/Dashboard';
import DetailedReports from './pages/operations/DetailedReports';
import LabStatusScreen from './pages/operations/LabStatusScreen';

// 交互式看板
import InstrumentGantt from './pages/InstrumentGantt';
import ProjectGantt from './pages/kanban/ProjectGantt';

// 任务管理
import PersonalWorkspace from './pages/tasks/PersonalWorkspace';
import TaskFeedback from './pages/tasks/TaskFeedback';
import ExperimentAnomaly from './pages/tasks/ExperimentAnomaly';

// 项目管理
import ProjectBoard from './pages/ProjectBoard';
import PlanBreakdown from './pages/projects/PlanBreakdown';
import ProjectDAG from './pages/ProjectDAG';
import ResourceLedger from './pages/projects/ResourceLedger';

// 排程管理
import ScheduleRules from './pages/schedule/ScheduleRules';
import ScheduleManager from './pages/ScheduleManager';
import RescheduleAdjust from './pages/schedule/RescheduleAdjust';
import InsertOrder from './pages/schedule/InsertOrder';

// 系统管理
import AlertPush from './pages/system/AlertPush';
import ExternalSync from './pages/system/ExternalSync';
import UserManagement from './pages/system/UserManagement';
import SystemBasic from './pages/system/SystemBasic';

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />

        {/* 运营数据中台 */}
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="operations/reports" element={<DetailedReports />} />
        <Route path="operations/lab-status" element={<LabStatusScreen />} />

        {/* 交互式看板 */}
        <Route path="kanban/instrument-gantt" element={<InstrumentGantt />} />
        <Route path="kanban/project-gantt" element={<ProjectGantt />} />

        {/* 任务管理 */}
        <Route path="tasks/workspace" element={<PersonalWorkspace />} />
        <Route path="tasks/feedback" element={<TaskFeedback />} />
        <Route path="tasks/anomaly" element={<ExperimentAnomaly />} />

        {/* 项目管理 */}
        <Route path="projects/ledger" element={<ProjectBoard />} />
        <Route path="projects/plan-breakdown" element={<PlanBreakdown />} />
        <Route path="projects/process-dag" element={<ProjectDAG />} />
        <Route path="projects/resource-ledger" element={<ResourceLedger />} />

        {/* 排程管理 */}
        <Route path="schedule/rules" element={<ScheduleRules />} />
        <Route path="schedule/engine" element={<ScheduleManager />} />
        <Route path="schedule/reschedule" element={<RescheduleAdjust />} />
        <Route path="schedule/insert-order" element={<InsertOrder />} />

        {/* 系统管理 */}
        <Route path="system/alerts" element={<AlertPush />} />
        <Route path="system/external-sync" element={<ExternalSync />} />
        <Route path="system/users" element={<UserManagement />} />
        <Route path="system/basic" element={<SystemBasic />} />
      </Route>
    </Routes>
  );
};

export default App;
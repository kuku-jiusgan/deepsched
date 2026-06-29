import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import Dashboard from './pages/Dashboard';
import InstrumentGantt from './pages/InstrumentGantt';
import ProjectBoard from './pages/ProjectBoard';
import ProjectDAG from './pages/ProjectDAG';
import ScheduleManager from './pages/ScheduleManager';

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="gantt" element={<InstrumentGantt />} />
        <Route path="projects" element={<ProjectBoard />} />
        <Route path="dag" element={<ProjectDAG />} />
        <Route path="schedule" element={<ScheduleManager />} />
      </Route>
    </Routes>
  );
};

export default App;
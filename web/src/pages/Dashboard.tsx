import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Table, Tag, Spin, message } from 'antd';
import {
  ExperimentOutlined, ProjectOutlined, ClockCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { getDashboard, getUtilization } from '../services/api';
import type { DashboardData, UtilizationStats } from '../types';

const ACCENT = '#2563eb';
const COLORS = ['#2563eb', '#16a34a', '#ea580c', '#dc2626', '#7c3aed', '#0891b2'];

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [utilization, setUtilization] = useState<UtilizationStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboard(), getUtilization()])
      .then(([d, u]) => { setData(d); setUtilization(u); })
      .catch(() => message.error('加载仪表盘数据失败'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />;

  const utilColumns = [
    { title: '仪器', dataIndex: 'instrument_name', key: 'name' },
    { title: '利用率', dataIndex: 'utilization_rate', key: 'rate',
      render: (v: number) => {
        const color = v > 70 ? '#16a34a' : v > 50 ? '#ea580c' : '#dc2626';
        return <Tag color={color}>{v}%</Tag>;
      }
    },
    { title: '计划 (h)', dataIndex: 'scheduled_hours', key: 'scheduled' },
    { title: '实际 (h)', dataIndex: 'actual_run_hours', key: 'actual' },
  ];

  const barData = utilization.map(u => ({
    name: u.instrument_name.length > 8 ? u.instrument_name.slice(0, 8) + '...' : u.instrument_name,
    '计划占用': u.scheduled_hours,
    '实际运行': u.actual_run_hours,
  }));

  const pieData = utilization.map(u => ({
    name: u.instrument_name,
    value: u.actual_run_hours,
  }));

  const stats = [
    { title: '仪器总数', value: data?.total_instruments || 0, suffix: '活跃 ' + (data?.active_instruments || 0), icon: <ExperimentOutlined /> },
    { title: '项目总数', value: data?.total_projects || 0, suffix: '活跃 ' + (data?.active_projects || 0), icon: <ProjectOutlined /> },
    { title: '平均利用率', value: (data?.avg_utilization || 0) + '%', suffix: '', icon: <ThunderboltOutlined /> },
    { title: '延期任务', value: data?.delayed_tasks || 0, suffix: '', icon: <ClockCircleOutlined />, danger: !!data?.delayed_tasks },
  ];

  return (
    <div>
      <div className="page-header">
        <h2>仪表盘</h2>
        <p>仪器利用率与项目概览</p>
      </div>

      <div className="stat-grid">
        {stats.map((item, i) => (
          <div className="stat-card" key={i}>
            <div>
              <div className="stat-card-label">{item.title}</div>
              <div className="stat-card-value" style={item.danger ? { color: '#dc2626' } : undefined}>
                {item.value}
              </div>
              {item.suffix ? <div className="stat-card-suffix">{item.suffix}</div> : null}
            </div>
            <div className="stat-card-icon" style={item.danger ? { background: '#fef2f2', color: '#dc2626' } : undefined}>
              {item.icon}
            </div>
          </div>
        ))}
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <div className="chart-card">
            <div className="chart-card-header">仪器占用对比</div>
            <div className="chart-card-body">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="name" fontSize={11} tick={{ fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis fontSize={11} tick={{ fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="计划占用" fill={ACCENT} radius={[4, 4, 0, 0]} barSize={28} />
                  <Bar dataKey="实际运行" fill="#16a34a" radius={[4, 4, 0, 0]} barSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Col>
        <Col xs={24} lg={10}>
          <div className="chart-card">
            <div className="chart-card-header">运行时间分布</div>
            <div className="chart-card-body">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={90}
                    dataKey="value" paddingAngle={2}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Col>
      </Row>

      <Card title="仪器利用率详情" style={{ marginTop: 16 }}>
        <Table dataSource={utilization} columns={utilColumns} rowKey="instrument_id"
          pagination={false} size="small" showHeader={true} />
      </Card>

      {data?.milestone_risks && data.milestone_risks.length > 0 && (
        <Card title="里程碑违约风险" style={{ marginTop: 16, border: '1px solid #fecaca', background: '#fef2f2' }}>
          {data.milestone_risks.map((r, i) => (
            <Tag color="#dc2626" key={i} style={{ margin: 4 }}>{r.project} - {r.milestone} ({r.due_date})</Tag>
          ))}
        </Card>
      )}
    </div>
  );
};

export default Dashboard;

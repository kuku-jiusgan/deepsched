import React, { useState, useCallback } from 'react';
import { Card, Button, Space, Modal, Select, message, Tag, Alert, Table } from 'antd';
import { ThunderboltOutlined, PlusCircleOutlined, ReloadOutlined, ForwardOutlined } from '@ant-design/icons';
import {
  generateSchedule, calculateInsertCost, confirmInsert,
  reschedule, dailyRoll, getProjects, getTimeslots,
} from '../services/api';
import type { InsertCost, TimeSlot, Project } from '../types';
import dayjs from 'dayjs';

const TIER_COLORS: Record<string, string> = { frozen: 'blue', confirmed: 'green', forecast: 'default' };
const TIER_LABELS: Record<string, string> = { frozen: '冻结', confirmed: '确认', forecast: '预测' };
const STATUS_COLORS: Record<string, string> = { completed: 'green', running: 'blue', scheduled: 'default' };
const STATUS_LABELS: Record<string, string> = { completed: '已完成', running: '运行中', scheduled: '已排程', interrupted: '已中断', pending: '待处理' };

const slotColumns = [
  { title: '仪器', dataIndex: 'instrument_name', key: 'inst' },
  { title: '项目', dataIndex: 'project_name', key: 'proj' },
  { title: '任务', dataIndex: 'task_name', key: 'task' },
  { title: '开始', dataIndex: 'plan_start', key: 'start',
    render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
  { title: '结束', dataIndex: 'plan_end', key: 'end',
    render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
  { title: '层级', dataIndex: 'tier', key: 'tier',
    render: (v: string) => <Tag color={TIER_COLORS[v] || 'default'}>{TIER_LABELS[v] || v}</Tag> },
  { title: '状态', dataIndex: 'status', key: 'status',
    render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{STATUS_LABELS[v] || v}</Tag> },
];

const ScheduleManager: React.FC = () => {
  const [genLoading, setGenLoading] = useState(false);
  const [insertModalOpen, setInsertModalOpen] = useState(false);
  const [insertCost, setInsertCost] = useState<InsertCost | null>(null);
  const [insertProjectId, setInsertProjectId] = useState<number | null>(null);
  const [recentSlots, setRecentSlots] = useState<TimeSlot[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  const fetchTaskIds = useCallback(async (projId: number): Promise<number[]> => {
    const allProjects = await getProjects();
    const proj = allProjects.find(p => p.id === projId);
    return proj?.tasks?.filter(t => t.requires_instrument).map(t => t.id) || [];
  }, []);

  const handleGenerate = async () => {
    setGenLoading(true);
    try {
      const result = await generateSchedule();
      message.success(result.message || '排程生成成功');
      const slots = await getTimeslots();
      setRecentSlots(slots.slice(0, 20));
    } catch {
      message.error('排程生成失败');
    } finally {
      setGenLoading(false);
    }
  };

  const handleInsertCalculate = async () => {
    if (!insertProjectId) return;
    try {
      const taskIds = await fetchTaskIds(insertProjectId);
      const cost = await calculateInsertCost({ project_id: insertProjectId, task_ids: taskIds });
      setInsertCost(cost);
    } catch {
      message.error('代价计算失败');
    }
  };

  const handleInsertConfirm = async () => {
    if (!insertProjectId) return;
    try {
      const taskIds = await fetchTaskIds(insertProjectId);
      await confirmInsert({ project_id: insertProjectId, task_ids: taskIds });
      message.success('插单完成');
      setInsertModalOpen(false);
      setInsertCost(null);
    } catch {
      message.error('插单失败');
    }
  };

  const handleReschedule = async (strategy: string) => {
    try {
      await reschedule({ trigger_type: 'manual', strategy });
      message.success('重排完成');
    } catch {
      message.error('重排失败');
    }
  };

  const handleDailyRoll = async () => {
    try {
      await dailyRoll();
      message.success('每日滚动完成');
    } catch {
      message.error('滚动失败');
    }
  };

  const openInsertModal = async () => {
    const projs = await getProjects();
    setProjects(projs);
    setInsertCost(null);
    setInsertProjectId(null);
    setInsertModalOpen(true);
  };

  return (
    <div>
      <div className="page-header">
        <h2>{'排程管理'}</h2>
        <p>{'生成排程、插单与动态重排'}</p>
      </div>

      <div className="action-bar">
        <Button type="primary" icon={<ThunderboltOutlined />} loading={genLoading} onClick={handleGenerate}>
          {'生成排程'}
        </Button>
        <Button icon={<PlusCircleOutlined />} onClick={openInsertModal}>{'插单'}</Button>
        <Button icon={<ReloadOutlined />} onClick={() => handleReschedule('local')}>{'局部修复'}</Button>
        <Button icon={<ReloadOutlined />} onClick={() => handleReschedule('project')}>{'项目级重排'}</Button>
        <Button icon={<ReloadOutlined />} danger onClick={() => handleReschedule('global')}>{'全局重排'}</Button>
        <Button icon={<ForwardOutlined />} onClick={handleDailyRoll}>{'每日滚动'}</Button>
      </div>

      {recentSlots.length > 0 && (
        <Card title={'最近排程结果'} style={{ marginTop: 16 }}>
          <Table dataSource={recentSlots} rowKey="id" size="small"
            columns={slotColumns} pagination={false} />
        </Card>
      )}

      <Modal title={'插单'} open={insertModalOpen} onCancel={() => setInsertModalOpen(false)}
        onOk={insertCost ? handleInsertConfirm : handleInsertCalculate}
        okText={insertCost ? '确认插单' : '计算代价'} width={600}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select placeholder={'选择项目'} style={{ width: '100%' }} value={insertProjectId}
            onChange={setInsertProjectId}
            options={projects.map(p => ({ label: p.code + ' - ' + p.name, value: p.id }))} />

          {insertCost && (
            <div>
              <Alert message={'插单将导致总延迟' + insertCost.total_delay_hours + ' 小时'}
                type={insertCost.milestone_violations.length > 0 ? 'error' : 'warning'} style={{ marginBottom: 12 }} />
              {insertCost.displaced_tasks.length > 0 && (
                <Card title={'被挤出的任务'} size="small">
                  {insertCost.displaced_tasks.map((t, i) => (
                    <Tag key={i} color="orange">{t.project_name} - {t.task_name} ({'延迟'}{t.delay_hours}h)</Tag>
                  ))}
                </Card>
              )}
              {insertCost.milestone_violations.length > 0 && (
                <Card title={'里程碑违约'} size="small" style={{ marginTop: 8 }}>
                  {insertCost.milestone_violations.map((v, i) => (
                    <Tag key={i} color="red">{v.project} - {v.milestone} ({'延迟'}{v.days_late}{'天'})</Tag>
                  ))}
                </Card>
              )}
            </div>
          )}
        </Space>
      </Modal>
    </div>
  );
};

export default ScheduleManager;

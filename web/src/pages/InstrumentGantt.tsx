import React, { useEffect, useState } from 'react';
import { Card, Select, Button, Space, Tag, Modal, Form, Input, InputNumber, message, Spin, Tabs, Tooltip } from 'antd';
import { PlusOutlined, PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getInstruments, getTimeslots, createInstrument, startTask, completeTask, interruptTask } from '../services/api';
import type { Instrument, TimeSlot } from '../types';

type ViewMode = 'day' | 'week' | 'month';

const ACCENT = '#2563eb';
const tierColors: Record<string, string> = { frozen: ACCENT, confirmed: '#16a34a', forecast: '#cbd5e1' };
const tierLabels: Record<string, string> = { frozen: '冻结', confirmed: '确认', forecast: '预测' };
const statusLabels: Record<string, string> = { scheduled: '待执行', running: '运行中', completed: '已完成', interrupted: '已中断' };

const SIDEBAR = 160;
const ROW_H = 68;
const HEADER_H = 38;

const InstrumentGantt: React.FC = () => {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [timeslots, setTimeslots] = useState<TimeSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('week');
  const [cursorDate, setCursorDate] = useState(dayjs());
  const [selectedInst, setSelectedInst] = useState<number[]>([]);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [detailSlot, setDetailSlot] = useState<TimeSlot | null>(null);
  const [addForm] = Form.useForm();

  const fetchData = () => {
    setLoading(true);
    const range = getDateRange();
    Promise.all([
      getInstruments(),
      getTimeslots({ start_date: range.start, end_date: range.end, ...(selectedInst.length > 0 ? { instrument_id: selectedInst[0] } : {}) })
    ]).then(([insts, slots]) => { setInstruments(insts); setTimeslots(slots); })
    .catch(() => message.error('加载数据失败'))
    .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [viewMode, cursorDate, selectedInst]);

  const getDateRange = () => {
    const s = cursorDate.startOf(viewMode === 'day' ? 'day' : viewMode === 'week' ? 'week' : 'month');
    const e = cursorDate.endOf(viewMode === 'day' ? 'day' : viewMode === 'week' ? 'week' : 'month');
    return { start: s.toISOString(), end: e.toISOString() };
  };

  const getColumns = (): { label: string; key: string; width: number; isWeekend?: boolean }[] => {
    if (viewMode === 'day') {
      const cols: { label: string; key: string; width: number }[] = [];
      for (let h = 0; h < 24; h++) cols.push({ label: h + ':00', key: 'h' + h, width: 60 });
      return cols;
    }
    if (viewMode === 'week') {
      const start = cursorDate.startOf('week');
      const days = ['一', '二', '三', '四', '五', '六', '日'];
      return days.map((d, i) => ({
        label: d + '\n' + start.add(i, 'day').format('MM/DD'),
        key: start.add(i, 'day').format('YYYY-MM-DD'),
        width: Math.floor((window.innerWidth - SIDEBAR - 80) / 7),
        isWeekend: i >= 5,
      }));
    }
    const start = cursorDate.startOf('month');
    const days = cursorDate.daysInMonth();
    const cols: { label: string; key: string; width: number; isWeekend?: boolean }[] = [];
    for (let d = 0; d < days; d++) {
      const date = start.add(d, 'day');
      cols.push({
        label: (d + 1).toString(),
        key: date.format('YYYY-MM-DD'),
        width: Math.floor((window.innerWidth - SIDEBAR - 80) / Math.min(days, 31)),
        isWeekend: [0, 6].includes(date.day()),
      });
    }
    return cols;
  };

  const getSlotStyle = (slot: TimeSlot, columns: { key: string; width: number }[]) => {
    const start = dayjs(slot.plan_start);
    const end = dayjs(slot.plan_end);
    if (viewMode === 'day') {
      const left = (start.hour() * 60 + start.minute()) / 60 * 60;
      const w = Math.max((end.diff(start, 'minute') / 60) * 60, 4);
      return { left, width: w };
    }
    const dateKey = start.format('YYYY-MM-DD');
    let left = 0;
    for (const col of columns) {
      if (col.key === dateKey) break;
      left += col.width;
    }
    const spanDays = Math.max(end.diff(start, 'day') + 1, 1);
    const colW = columns.find(c => c.key === dateKey)?.width || 60;
    return { left, width: Math.max(colW * spanDays, colW * 0.8) };
  };

  const navigate = (dir: -1 | 1) => {
    const unit = viewMode === 'day' ? 'day' : viewMode === 'week' ? 'week' : 'month';
    setCursorDate(cursorDate.add(dir, unit));
  };

  const titleStr = () => {
    if (viewMode === 'day') return cursorDate.format('YYYY年MM月DD日');
    if (viewMode === 'week') {
      const s = cursorDate.startOf('week');
      const e = cursorDate.endOf('week');
      return s.format('MM/DD') + ' - ' + e.format('MM/DD') + '  ' + cursorDate.format('YYYY年');
    }
    return cursorDate.format('YYYY年MM月');
  };

  const handleAddInstrument = async (values: any) => {
    await createInstrument(values);
    message.success('仪器添加成功');
    setAddModalOpen(false);
    addForm.resetFields();
    fetchData();
  };

  const handleTaskAction = async (slotId: number, action: string) => {
    try {
      if (action === 'start') await startTask(slotId);
      else if (action === 'complete') await completeTask(slotId);
      else if (action === 'interrupt') await interruptTask(slotId);
      message.success('操作成功');
      setDetailSlot(null);
      fetchData();
    } catch { message.error('操作失败'); }
  };

  const columns = getColumns();
  const filteredInsts = instruments.filter(i => selectedInst.length === 0 || selectedInst.includes(i.id));
  const totalWidth = columns.reduce((s, c) => s + c.width, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#1e293b', letterSpacing: '-0.3px' }}>仪器甘特图</h2>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94a3b8' }}>日/周/月视图切换，拖拽缩放查看排程</p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space wrap>
          <Select mode="multiple" placeholder="筛选仪器" style={{ minWidth: 200 }}
            value={selectedInst} onChange={setSelectedInst}
            options={instruments.map(i => ({ label: i.name, value: i.id }))} allowClear />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}
            style={{ borderRadius: 8, fontWeight: 500 }}>添加仪器</Button>
          <Button icon={<ReloadOutlined />} onClick={fetchData} style={{ borderRadius: 8 }}>刷新</Button>
        </Space>
        <Space>
          {Object.entries(tierLabels).map(([k, v]) => (
            <Tag key={k} color={tierColors[k]} style={{
              color: k === 'forecast' ? '#475569' : '#fff',
              borderRadius: 5, border: 'none', fontWeight: 500,
            }}>{v}</Tag>
          ))}
        </Space>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 0 }}>
        <Tabs activeKey={viewMode} onChange={(k) => setViewMode(k as ViewMode)}
          items={[
            { key: 'day', label: '日视图' },
            { key: 'week', label: '周视图' },
            { key: 'month', label: '月视图' },
          ]}
          style={{ marginBottom: 0 }}
        />
        <Space>
          <Button size="small" type="text" onClick={() => navigate(-1)} style={{ fontSize: 16 }}>{'<'}</Button>
          <span style={{ fontWeight: 600, fontSize: 14, color: '#334155', minWidth: 180, textAlign: 'center' }}>{titleStr()}</span>
          <Button size="small" type="text" onClick={() => navigate(1)} style={{ fontSize: 16 }}>{'>'}</Button>
          <Button size="small" onClick={() => setCursorDate(dayjs())} style={{ borderRadius: 6 }}>今天</Button>
        </Space>
      </div>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : (
        <Card styles={{ body: { padding: 0, flex: 1, display: 'flex', flexDirection: 'column' } }}
          style={{ flex: 1, display: 'flex', overflow: 'hidden', borderRadius: 10, border: '1px solid #f1f5f9', boxShadow: 'none' }}>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <div style={{ minWidth: SIDEBAR + totalWidth + 40 }}>
              <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', height: HEADER_H, flexShrink: 0 }}>
                <div style={{ width: SIDEBAR, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 14px', fontWeight: 600, fontSize: 12, color: '#64748b', borderRight: '1px solid #e2e8f0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  仪器
                </div>
                {columns.map(col => (
                  <div key={col.key} style={{
                    width: col.width, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, color: '#94a3b8', background: col.isWeekend ? '#f8fafc' : 'transparent',
                    borderRight: '1px solid #f1f5f9', whiteSpace: 'pre-line', textAlign: 'center', lineHeight: '14px', fontWeight: 500,
                  }}>
                    {col.label}
                  </div>
                ))}
              </div>

              {filteredInsts.length === 0 ? (
                <div style={{ padding: 60, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>暂无仪器，请先添加仪器</div>
              ) : (
                filteredInsts.map((inst, idx) => {
                  const instSlots = timeslots.filter(s => s.instrument_id === inst.id);
                  const isLast = idx === filteredInsts.length - 1;
                  return (
                    <div key={inst.id} style={{
                      display: 'flex', borderBottom: '1px solid #f1f5f9',
                      height: ROW_H, background: inst.status !== 'active' ? '#fef2f2' : (idx % 2 === 0 ? '#fff' : '#fafbfc'),
                      flex: isLast ? 1 : '0 0 auto'
                    }}>
                      <div style={{
                        width: SIDEBAR, flexShrink: 0, padding: '8px 14px', borderRight: '1px solid #e2e8f0',
                        background: '#f8fafc', display: 'flex', flexDirection: 'column', justifyContent: 'center'
                      }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#1e293b', lineHeight: '18px' }}>{inst.name}</div>
                        <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: '16px' }}>{inst.brand} {inst.model}</div>
                        <Tag color={inst.status === 'active' ? '#16a34a' : '#dc2626'} style={{ fontSize: 10, marginTop: 2, lineHeight: '16px', borderRadius: 4, border: 'none' }}>
                          {inst.status === 'active' ? '正常' : inst.status}
                        </Tag>
                      </div>

                      <div style={{ position: 'relative', flex: 1 }}>
                        {columns.map(col => {
                          const colIdx = columns.indexOf(col);
                          const colLeft = columns.slice(0, colIdx).reduce((s, c) => s + c.width, 0);
                          return (
                            <div key={col.key} style={{
                              position: 'absolute', left: colLeft,
                              top: 0, width: col.width, height: '100%',
                              background: col.isWeekend ? '#fafbfc' : 'transparent',
                              borderRight: '1px solid #f8fafc'
                            }} />
                          );
                        })}

                        {instSlots.map(slot => {
                          const style = getSlotStyle(slot, columns);
                          const isRunning = slot.status === 'running';
                          const isCompleted = slot.status === 'completed';
                          const bg = tierColors[slot.tier] || tierColors.forecast;
                          return (
                            <Tooltip key={slot.id}
                              title={<div style={{ fontSize: 12 }}>
                                <div style={{ fontWeight: 600 }}>{slot.project_name}</div>
                                <div>{slot.task_name}</div>
                                <div style={{ color: '#94a3b8', marginTop: 4 }}>
                                  {dayjs(slot.plan_start).format('MM/DD HH:mm')} ~ {dayjs(slot.plan_end).format('HH:mm')}
                                </div>
                                <div style={{ marginTop: 2 }}>{statusLabels[slot.status]}</div>
                              </div>}
                            >
                              <div onClick={() => setDetailSlot(slot)} style={{
                                position: 'absolute', left: style.left, top: 6,
                                width: Math.max(style.width, 20), height: ROW_H - 12,
                                background: bg,
                                borderRadius: 5, color: slot.tier === 'forecast' ? '#475569' : '#fff',
                                fontSize: 11, padding: '4px 8px', overflow: 'hidden',
                                cursor: 'pointer', opacity: isCompleted ? 0.45 : 1,
                                border: isRunning ? '2px solid ' + ACCENT : '1px solid transparent',
                                boxShadow: isRunning ? '0 0 0 2px rgba(37,99,235,0.15)' : '0 1px 2px rgba(0,0,0,0.06)',
                                zIndex: isRunning ? 2 : 1,
                                display: 'flex', flexDirection: 'column', justifyContent: 'center',
                                lineHeight: '15px', minWidth: 0,
                                transition: 'box-shadow 0.15s',
                              }}>
                                <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  {slot.project_name}
                                </div>
                                <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 10, opacity: 0.85 }}>
                                  {slot.task_name}
                                </div>
                              </div>
                            </Tooltip>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </Card>
      )}

      <Modal title="任务详情" open={!!detailSlot} onCancel={() => setDetailSlot(null)}
        footer={detailSlot ? [
          detailSlot.status === 'scheduled' && <Button key="start" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleTaskAction(detailSlot.id, 'start')} style={{ borderRadius: 8 }}>开始执行</Button>,
          detailSlot.status === 'running' && <Button key="complete" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleTaskAction(detailSlot.id, 'complete')} style={{ borderRadius: 8 }}>标记完成</Button>,
          detailSlot.status === 'running' && <Button key="interrupt" danger icon={<CloseCircleOutlined />} onClick={() => handleTaskAction(detailSlot.id, 'interrupt')} style={{ borderRadius: 8 }}>中断</Button>,
          <Button key="close" onClick={() => setDetailSlot(null)} style={{ borderRadius: 8 }}>关闭</Button>,
        ].filter(Boolean) : undefined}
      >
        {detailSlot && (
          <div>
            <p><strong>项目：</strong>{detailSlot.project_name}</p>
            <p><strong>任务：</strong>{detailSlot.task_name}</p>
            <p><strong>仪器：</strong>{detailSlot.instrument_name}</p>
            <p><strong>计划：</strong>{dayjs(detailSlot.plan_start).format('YYYY-MM-DD HH:mm')} ~ {dayjs(detailSlot.plan_end).format('HH:mm')}</p>
            <p><strong>层级：</strong><Tag color={detailSlot.tier === 'frozen' ? ACCENT : detailSlot.tier === 'confirmed' ? '#16a34a' : '#94a3b8'} style={{ borderRadius: 4, border: 'none' }}>{tierLabels[detailSlot.tier]}</Tag></p>
            <p><strong>状态：</strong><Tag color={detailSlot.status === 'completed' ? '#16a34a' : detailSlot.status === 'running' ? ACCENT : '#94a3b8'} style={{ borderRadius: 4, border: 'none' }}>{statusLabels[detailSlot.status]}</Tag></p>
            {detailSlot.actual_start && <p><strong>实际开始：</strong>{dayjs(detailSlot.actual_start).format('YYYY-MM-DD HH:mm')}</p>}
            {detailSlot.actual_end && <p><strong>实际结束：</strong>{dayjs(detailSlot.actual_end).format('YYYY-MM-DD HH:mm')}</p>}
          </div>
        )}
      </Modal>

      <Modal title="添加仪器" open={addModalOpen} onCancel={() => setAddModalOpen(false)} onOk={() => addForm.submit()}>
        <Form form={addForm} layout="vertical" onFinish={handleAddInstrument}>
          <Form.Item name="name" label="仪器名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="brand" label="品牌"><Input /></Form.Item>
          <Form.Item name="model" label="型号"><Input /></Form.Item>
          <Form.Item name="location" label="位置"><Input /></Form.Item>
          <Form.Item name="buffer_rate" label="缓冲率" initialValue={0.85}><InputNumber min={0.5} max={1} step={0.05} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default InstrumentGantt;

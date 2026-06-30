import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Tag, message, Spin, Drawer, Tabs, DatePicker, Divider } from 'antd';
import { PlusOutlined, ApartmentOutlined, MinusCircleOutlined, EditOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getProjects, createProject, updateProject, getProject, getProjectDAG, addTask, updateTask } from '../services/api';
import type { Project, DAGData, Task } from '../types';

const ACCENT = '#2563eb';

const PROJECT_STATUS_LABELS: Record<string, string> = {
  active: '进行中',
  completed: '已完成',
  pending: '待启动',
  suspended: '已暂停',
  cancelled: '已取消',
  draft: '草稿',
};

const ProjectBoard: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [dagData, setDagData] = useState<DAGData | null>(null);
  const [taskOpen, setTaskOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filterCode, setFilterCode] = useState('');
  const [filterName, setFilterName] = useState('');
  const [filterClient, setFilterClient] = useState('');
  const [filterDateRange, setFilterDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [taskForm] = Form.useForm();

  const fetchProjects = () => {
    setLoading(true);
    getProjects().then(setProjects).catch(() => message.error('加载项目失败')).finally(() => setLoading(false));
  };

  useEffect(() => { fetchProjects(); }, []);

  const handleCreate = async (values: Record<string, unknown>) => {
    const payload = {
      ...values,
      start_date: values.start_date ? dayjs(values.start_date as string).toISOString() : undefined,
      end_date: values.end_date ? dayjs(values.end_date as string).toISOString() : undefined,
    };
    await createProject(payload);
    message.success('项目创建成功');
    setCreateOpen(false);
    createForm.resetFields();
    fetchProjects();
  };

  const handleUpdateProject = async (values: Record<string, unknown>) => {
    if (!selectedProject) return;
    const payload = {
      ...values,
      start_date: values.start_date ? dayjs(values.start_date as string).toISOString() : undefined,
      end_date: values.end_date ? dayjs(values.end_date as string).toISOString() : undefined,
    };
    await updateProject(selectedProject.id, payload);
    message.success('项目更新成功');
    setEditOpen(false);
    fetchProjects();
    handleViewDetail(selectedProject.id);
  };

  const openEditProject = () => {
    if (!selectedProject) return;
    editForm.setFieldsValue({
      name: selectedProject.name,
      code: selectedProject.code,
      client_name: selectedProject.client_name,
      priority: selectedProject.priority,
      sla_level: selectedProject.sla_level,
      profit_weight: selectedProject.profit_weight,
      manager: selectedProject.manager,
      start_date: selectedProject.start_date ? dayjs(selectedProject.start_date) : null,
      end_date: selectedProject.end_date ? dayjs(selectedProject.end_date) : null,
    });
    setEditOpen(true);
  };

  const handleViewDetail = async (projId: number) => {
    const proj = await getProject(projId);
    const dag = await getProjectDAG(projId);
    setSelectedProject(proj);
    setDagData(dag);
    setDetailOpen(true);
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    taskForm.setFieldsValue({
      name: task.name,
      task_type: task.task_type,
      est_duration_hours: task.est_duration_hours,
      switchover_hours: task.switchover_hours,
      predecessor_ids: task.predecessor_ids || [],
      capability_requirements: (task.capability_requirements || []).map((c) => ({
        tag_name: c.tag_name,
        tag_value: c.tag_value,
      })),
    });
    setTaskOpen(true);
  };

  const handleAddTask = async (values: Record<string, unknown>) => {
    if (!selectedProject) return;
    const payload = {
      ...values,
      requires_instrument: values.task_type === 'instrument',
      predecessor_ids: values.predecessor_ids || [],
      capability_requirements: (values.capability_requirements || []).map((c: Record<string, unknown>) => ({
        tag_name: c.tag_name,
        tag_value: c.tag_value,
      })),
    };
    if (editingTask) {
      await updateTask(editingTask.id, payload);
      message.success('任务更新成功');
    } else {
      await addTask(selectedProject.id, payload);
      message.success('任务添加成功');
    }
    setTaskOpen(false);
    setEditingTask(null);
    taskForm.resetFields();
    handleViewDetail(selectedProject.id);
  };

  const filteredProjects = projects.filter((p) => {
    if (filterCode && !p.code.toLowerCase().includes(filterCode.toLowerCase())) return false;
    if (filterName && !p.name.toLowerCase().includes(filterName.toLowerCase())) return false;
    if (filterClient && !(p.client_name || '').toLowerCase().includes(filterClient.toLowerCase())) return false;
    if (filterDateRange && filterDateRange[0] && filterDateRange[1]) {
      const start = filterDateRange[0].startOf('day');
      const end = filterDateRange[1].endOf('day');
      if (p.start_date) {
        const pStart = dayjs(p.start_date);
        if (pStart.isBefore(start) || pStart.isAfter(end)) return false;
      } else {
        return false;
      }
    }
    return true;
  });

  const columns = [
    { title: '项目编号', dataIndex: 'code', key: 'code', width: 130,
      render: (v: string) => <span style={{ fontFamily: 'monospace', fontWeight: 600, color: ACCENT, fontSize: 12 }}>{v}</span> },
    { title: '项目名称', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '客户', dataIndex: 'client_name', key: 'client', width: 140, ellipsis: true,
      render: (v: string) => v || '-' },
    { title: '负责人', dataIndex: 'manager', key: 'manager', width: 90,
      render: (v: string) => v || '-' },
    { title: '计划开始', dataIndex: 'start_date', key: 'start', width: 110,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-' },
    { title: '计划完成', dataIndex: 'end_date', key: 'end', width: 110,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-' },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80, align: 'center' as const,
      render: (v: number) => <Tag color={v >= 5 ? '#dc2626' : v >= 3 ? '#ea580c' : ACCENT}>{v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
      const color = v === 'active' ? '#16a34a' : v === 'completed' ? '#7c3aed' : '#94a3b8';
      return <Tag color={color}>{PROJECT_STATUS_LABELS[v] || v}</Tag>;
    } },
    { title: '操作', key: 'actions', width: 130,
      render: (_: unknown, record: Project) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<ApartmentOutlined />} onClick={() => handleViewDetail(record.id)}>详情</Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
            setSelectedProject(record);
            editForm.setFieldsValue({
              name: record.name,
              code: record.code,
              client_name: record.client_name,
              priority: record.priority,
              sla_level: record.sla_level,
              profit_weight: record.profit_weight,
              start_date: record.start_date ? dayjs(record.start_date) : null,
              end_date: record.end_date ? dayjs(record.end_date) : null,
            });
            setEditOpen(true);
          }}>编辑</Button>
        </Space>
      )
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h2>项目看板</h2>
        <p>管理项目、任务与依赖关系</p>
      </div>

      <div className="action-bar">
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建项目</Button>
        <Input
          placeholder="项目编号"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 150 }}
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
        />
        <Input
          placeholder="项目名称"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 180 }}
          value={filterName}
          onChange={(e) => setFilterName(e.target.value)}
        />
        <Input
          placeholder="客户名称"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 150 }}
          value={filterClient}
          onChange={(e) => setFilterClient(e.target.value)}
        />
        <DatePicker.RangePicker
          placeholder={['开始日期', '结束日期']}
          style={{ width: 240 }}
          value={filterDateRange as any}
          onChange={(dates) => setFilterDateRange(dates as any)}
          allowClear
        />
        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#94a3b8', alignSelf: 'center' }}>
          {filteredProjects.length} / {projects.length} 个项目
        </span>
      </div>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '50px auto' }} /> : (
        <Table dataSource={filteredProjects} columns={columns} rowKey="id" size="small" />
      )}

      {/* Create Project Modal */}
      <Modal title="新建项目" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => createForm.submit()}
        width={640} okText="创建项目">
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="如：某注射剂基因毒杂质研究" />
          </Form.Item>
          <Form.Item name="code" label="项目编号" rules={[{ required: true, message: '请输入项目编号' }]}>
            <Input placeholder="如：GT-2026-001" />
          </Form.Item>
          <Form.Item name="client_name" label="客户名称">
            <Input placeholder="如：某制药公司" />
          </Form.Item>
          <Form.Item name="manager" label="项目负责人">
            <Input placeholder="如：张三" />
          </Form.Item>
          <Space size={16}>
            <Form.Item name="priority" label="优先级" initialValue={3}>
              <InputNumber min={1} max={10} />
            </Form.Item>
            <Form.Item name="sla_level" label="SLA等级" initialValue="standard">
              <Select style={{ width: 120 }} options={[
                { label: '标准', value: 'standard' },
                { label: '加急', value: 'expedited' },
                { label: '特急', value: 'rush' },
              ]} />
            </Form.Item>
            <Form.Item name="profit_weight" label="利润权重" initialValue={1.0}>
              <InputNumber min={0.5} max={3} step={0.1} />
            </Form.Item>
          </Space>
          <Space size={16} style={{ width: '100%' }}>
            <Form.Item name="start_date" label="项目开始日期" style={{ width: 200 }}>
              <DatePicker placeholder="选择开始日期" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="end_date" label="项目结题日期" style={{ width: 200 }}>
              <DatePicker placeholder="选择结题日期" style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* Edit Project Modal */}
      <Modal title="编辑项目" open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => editForm.submit()}
        width={640} okText="保存">
        <Form form={editForm} layout="vertical" onFinish={handleUpdateProject}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="如：某注射剂基因毒杂质研究" />
          </Form.Item>
          <Form.Item name="code" label="项目编号" rules={[{ required: true, message: '请输入项目编号' }]}>
            <Input placeholder="如：GT-2026-001" />
          </Form.Item>
          <Form.Item name="client_name" label="客户名称">
            <Input placeholder="如：某制药公司" />
          </Form.Item>
          <Form.Item name="manager" label="项目负责人">
            <Input placeholder="如：张三" />
          </Form.Item>
          <Space size={16}>
            <Form.Item name="priority" label="优先级" initialValue={3}>
              <InputNumber min={1} max={10} />
            </Form.Item>
            <Form.Item name="sla_level" label="SLA等级" initialValue="standard">
              <Select style={{ width: 120 }} options={[
                { label: '标准', value: 'standard' },
                { label: '加急', value: 'expedited' },
                { label: '特急', value: 'rush' },
              ]} />
            </Form.Item>
            <Form.Item name="profit_weight" label="利润权重" initialValue={1.0}>
              <InputNumber min={0.5} max={3} step={0.1} />
            </Form.Item>
          </Space>
          <Space size={16} style={{ width: '100%' }}>
            <Form.Item name="start_date" label="项目开始日期" style={{ width: 200 }}>
              <DatePicker placeholder="选择开始日期" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="end_date" label="项目结题日期" style={{ width: 200 }}>
              <DatePicker placeholder="选择结题日期" style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {/* Project Detail Drawer */}
      <Drawer title={selectedProject?.name || '项目详情'} open={detailOpen} onClose={() => setDetailOpen(false)}
        extra={
          <Button icon={<EditOutlined />} onClick={openEditProject}>编辑项目</Button>
        }
        width={720}>
        {selectedProject && (
          <Tabs defaultActiveKey="tasks" items={[
            {
              key: 'tasks',
              label: '任务列表',
              children: (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingTask(null); taskForm.resetFields(); setTaskOpen(true); }} size="small">
                      添加任务
                    </Button>
                  </div>
                  <Table dataSource={selectedProject.tasks || []} rowKey="id" size="small"
                    columns={[
                      { title: '任务名称', dataIndex: 'name', key: 'name' },
                      { title: '类型', dataIndex: 'task_type', key: 'type',
                        render: (v: string) => <Tag>{v === 'instrument' ? '仪器' : v === 'manual' ? '人工' : '等待'}</Tag> },
                      { title: '预计耗时(h)', dataIndex: 'est_duration_hours', key: 'dur' },
                      { title: '状态', dataIndex: 'status', key: 'status',
                        render: (v: string) => {
      const color = v === 'scheduled' ? '#7c3aed' : v === 'running' ? ACCENT : v === 'done' ? '#16a34a' : '#94a3b8';
      const label: Record<string, string> = { scheduled: '已排程', running: '运行中', done: '已完成', blocked: '阻塞', pending: '待处理' };
      return <Tag color={color}>{label[v] || v}</Tag>;
    } },
                      { title: '操作', key: 'actions', width: 60,
                        render: (_: unknown, record: Task) => (
                          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditTask(record)} />
                        )
                      },
                    ]}
                    pagination={false} />
                </div>
              )
            },
            {
              key: 'dag',
              label: '依赖关系',
              children: (
                <div>
                  {dagData ? (
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 8 }}>
                        任务节点 ({dagData.nodes.length})
                      </div>
                      {dagData.nodes.map(n => (
                        <Tag key={n.id} color={n.requires_instrument ? ACCENT : '#94a3b8'} style={{ margin: 4 }}>
                          {n.name} ({n.type})
                        </Tag>
                      ))}
                      {dagData.edges.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                          <strong style={{ color: '#334155', fontSize: 13 }}>依赖关系：</strong>
                          {dagData.edges.map((e, i) => (
                            <div key={i} style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                              任务{e.from} → 任务{e.to}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : <Spin />}
                </div>
              )
            },
          ]} />
        )}
      </Drawer>

      {/* Add Task Modal */}
      <Modal title={editingTask ? '编辑任务' : '添加任务'} open={taskOpen} onCancel={() => { setTaskOpen(false); setEditingTask(null); }} onOk={() => taskForm.submit()}
        width={600} okText={editingTask ? '保存' : '添加任务'}>
        <Form form={taskForm} layout="vertical" onFinish={handleAddTask}
          initialValues={{ task_type: 'instrument', switchover_hours: 0.5, priority_weight: 1.0 }}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="如：LC-MS方法开发" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="task_type" label="任务类型" initialValue="instrument">
              <Select style={{ width: 140 }} options={[
                { label: '仪器依赖型', value: 'instrument' },
                { label: '人工型', value: 'manual' },
                { label: '等待型', value: 'waiting' },
              ]} />
            </Form.Item>
            <Form.Item name="est_duration_hours" label="预计耗时(小时)" rules={[{ required: true, message: '必填' }]}>
              <InputNumber min={0.5} step={0.5} placeholder="如：8" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="switchover_hours" label="切换时间(h)" initialValue={0.5}>
              <InputNumber min={0} step={0.5} style={{ width: 100 }} />
            </Form.Item>
          </Space>

          <Form.Item name="predecessor_ids" label="前置依赖任务">
            <Select mode="multiple" placeholder="选择依赖的前置任务（可选）"
              options={(selectedProject?.tasks || []).map(t => ({ label: t.name + ' (' + t.task_type + ')', value: t.id }))} />
          </Form.Item>

          <Divider style={{ margin: '12px 0' }}>仪器能力要求（仅仪器任务需要）</Divider>
          <Form.List name="capability_requirements">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item {...rest} name={[name, 'tag_name']} rules={[{ required: true, message: '标签名' }]}>
                      <Select placeholder="能力标签" style={{ width: 140 }} options={[
                        { label: '离子源', value: '离子源' },
                        { label: '质量分析器', value: '质量分析器' },
                        { label: '方法类型', value: '方法类型' },
                        { label: '灵敏度等级', value: '灵敏度等级' },
                      ]} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'tag_value']} rules={[{ required: true, message: '值' }]}>
                      <Select placeholder="标签值" style={{ width: 160 }} options={[
                        { label: 'ESI', value: 'ESI' },
                        { label: 'APCI', value: 'APCI' },
                        { label: 'QqQ', value: 'QqQ' },
                        { label: 'Q-TOF', value: 'Q-TOF' },
                        { label: '基因毒杂质', value: '基因毒杂质' },
                        { label: '有关物质', value: '有关物质' },
                        { label: '含量测定', value: '含量测定' },
                        { label: '痕量', value: '痕量' },
                        { label: '常量', value: '常量' },
                      ]} />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} style={{ color: '#dc2626' }} />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  添加能力要求
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectBoard;

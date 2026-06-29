import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Tag, message, Spin, Drawer, Tabs, DatePicker, Divider } from 'antd';
import { PlusOutlined, ApartmentOutlined, MinusCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getProjects, createProject, getProject, getProjectDAG, addTask } from '../services/api';
import type { Project, DAGData } from '../types';

const ACCENT = '#2563eb';

const ProjectBoard: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [dagData, setDagData] = useState<DAGData | null>(null);
  const [taskOpen, setTaskOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [taskForm] = Form.useForm();

  const fetchProjects = () => {
    setLoading(true);
    getProjects().then(setProjects).catch(() => message.error('加载项目失败')).finally(() => setLoading(false));
  };

  useEffect(() => { fetchProjects(); }, []);

  const handleCreate = async (values: any) => {
    const payload = {
      ...values,
      milestones: (values.milestones || []).map((m: any) => ({
        name: m.name,
        due_date: m.due_date ? dayjs(m.due_date).toISOString() : null,
      })),
    };
    await createProject(payload);
    message.success('项目创建成功');
    setCreateOpen(false);
    createForm.resetFields();
    fetchProjects();
  };

  const handleViewDetail = async (projId: number) => {
    const proj = await getProject(projId);
    const dag = await getProjectDAG(projId);
    setSelectedProject(proj);
    setDagData(dag);
    setDetailOpen(true);
  };

  const handleAddTask = async (values: any) => {
    if (!selectedProject) return;
    const payload = {
      ...values,
      requires_instrument: values.task_type === 'instrument',
      predecessor_ids: values.predecessor_ids || [],
      capability_requirements: (values.capability_requirements || []).map((c: any) => ({
        tag_name: c.tag_name,
        tag_value: c.tag_value,
      })),
    };
    await addTask(selectedProject.id, payload);
    message.success('任务添加成功');
    setTaskOpen(false);
    taskForm.resetFields();
    handleViewDetail(selectedProject.id);
  };

  const columns = [
    { title: '项目编号', dataIndex: 'code', key: 'code' },
    { title: '项目名称', dataIndex: 'name', key: 'name' },
    { title: '客户', dataIndex: 'client_name', key: 'client' },
    { title: '优先级', dataIndex: 'priority', key: 'priority',
      render: (v: number) => <Tag color={v >= 5 ? '#dc2626' : v >= 3 ? '#ea580c' : ACCENT}>{v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status',
      render: (v: string) => <Tag color={v === 'active' ? '#16a34a' : '#94a3b8'}>{v === 'active' ? '进行中' : v}</Tag> },
    { title: '操作', key: 'actions',
      render: (_: any, record: Project) => (
        <Button type="link" icon={<ApartmentOutlined />} onClick={() => handleViewDetail(record.id)}>查看</Button>
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
      </div>

      {loading ? <Spin size="large" style={{ display: 'block', margin: '50px auto' }} /> : (
        <Table dataSource={projects} columns={columns} rowKey="id" size="small" />
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
          <Space size={16}>
            <Form.Item name="priority" label="优先级" initialValue={3}>
              <InputNumber min={1} max={10} style={{ width: 100 }} />
            </Form.Item>
            <Form.Item name="sla_level" label="SLA级别" initialValue="standard">
              <Select style={{ width: 120 }} options={[
                { label: '紧急', value: 'urgent' },
                { label: '标准', value: 'standard' },
                { label: '普通', value: 'normal' },
              ]} />
            </Form.Item>
            <Form.Item name="profit_weight" label="利润权重" initialValue={1.0}>
              <InputNumber min={0.1} max={10} step={0.1} style={{ width: 100 }} />
            </Form.Item>
          </Space>

          <Divider>里程碑（可选）</Divider>
          <Form.List name="milestones">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item {...rest} name={[name, 'name']} rules={[{ required: true, message: '里程碑名称' }]}>
                      <Input placeholder="如：方法验证完成" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'due_date']} rules={[{ required: true, message: '截止日期' }]}>
                      <DatePicker placeholder="截止日期" />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} style={{ color: '#dc2626' }} />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  添加里程碑
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>

      {/* Project Detail Drawer */}
      <Drawer title={selectedProject?.name} open={detailOpen} onClose={() => setDetailOpen(false)} width={720}>
        {selectedProject && (
          <Tabs items={[
            {
              key: 'tasks', label: '任务列表',
              children: (
                <div>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setTaskOpen(true)} style={{ marginBottom: 16 }}>
                    添加任务
                  </Button>
                  <Table dataSource={selectedProject.tasks || []} rowKey="id" size="small"
                    columns={[
                      { title: '任务', dataIndex: 'name', key: 'name' },
                      { title: '类型', dataIndex: 'task_type', key: 'type',
                        render: (v: string) => <Tag>{v === 'instrument' ? '仪器' : v === 'manual' ? '人工' : '等待'}</Tag> },
                      { title: '耗时(h)', dataIndex: 'est_duration_hours', key: 'dur' },
                      { title: '状态', dataIndex: 'status', key: 'status',
                        render: (v: string) => <Tag color={v === 'scheduled' ? ACCENT : v === 'running' ? '#16a34a' : '#94a3b8'}>{v}</Tag> },
                    ]}
                  />
                </div>
              )
            },
            {
              key: 'dag', label: '依赖关系',
              children: (
                <div>
                  {dagData ? (
                    <div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {dagData.nodes.map(n => (
                          <Tag key={n.id} color={n.requires_instrument ? ACCENT : '#16a34a'} style={{ padding: '4px 10px' }}>
                            {n.name} ({n.type})
                          </Tag>
                        ))}
                      </div>
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
      <Modal title="添加任务" open={taskOpen} onCancel={() => setTaskOpen(false)} onOk={() => taskForm.submit()}
        width={600} okText="添加任务">
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

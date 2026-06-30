import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Tag,
  message, Spin, Popconfirm, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  ExperimentOutlined, SearchOutlined,
} from '@ant-design/icons';
import { getInstruments, createInstrument, updateInstrument, deleteInstrument } from '../../services/api';
import type { Instrument, CapabilityReq } from '../../types';

const ACCENT = '#2563eb';

const GROUP_OPTIONS = [
  { label: '基因毒组 (GTI)', value: 'GTI_Group' },
  { label: '质量组 (Quality)', value: 'Quality_Group' },
];

const STATUS_LABELS: Record<string, string> = {
  idle: '闲置',
  running: '运行中',
  maintenance: '维护中',
  fault: '故障停机',
  active: '活跃',
};

const STATUS_COLORS: Record<string, string> = {
  idle: '#16a34a',
  running: ACCENT,
  maintenance: '#ea580c',
  fault: '#dc2626',
  active: '#16a34a',
};

const GROUP_COLORS: Record<string, string> = {
  GTI_Group: '#7c3aed',
  Quality_Group: '#0891b2',
};

const CAP_TAG_OPTIONS = [
  { label: '离子源', value: '离子源' },
  { label: '质量分析器', value: '质量分析器' },
  { label: '方法类型', value: '方法类型' },
  { label: '灵敏度等级', value: '灵敏度等级' },
];

const CAP_VALUE_OPTIONS: Record<string, { label: string; value: string }[]> = {
  '离子源': [
    { label: 'ESI', value: 'ESI' },
    { label: 'APCI', value: 'APCI' },
  ],
  '质量分析器': [
    { label: 'QqQ', value: 'QqQ' },
    { label: 'Q-TOF', value: 'Q-TOF' },
    { label: 'Orbitrap', value: 'Orbitrap' },
  ],
  '方法类型': [
    { label: '基因毒杂质', value: '基因毒杂质' },
    { label: '有关物质', value: '有关物质' },
    { label: '含量测定', value: '含量测定' },
  ],
  '灵敏度等级': [
    { label: '痕量', value: '痕量' },
    { label: '常量', value: '常量' },
  ],
};

const ResourceLedger: React.FC = () => {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [groupFilter, setGroupFilter] = useState<string | undefined>();
  const [form] = Form.useForm();

  const fetchData = useCallback(() => {
    setLoading(true);
    getInstruments()
      .then(setInstruments)
      .catch(() => message.error('加载仪器列表失败'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = groupFilter
    ? instruments.filter((i) => i.instrument_group === groupFilter)
    : instruments;

  const openCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      instrument_group: 'GTI_Group',
      buffer_rate: 1.1,
      switchover_base_hours: 0.5,
      capabilities: [],
    });
    setModalOpen(true);
  };

  const openEdit = (record: Instrument) => {
    setEditingId(record.id);
    form.setFieldsValue({
      code: record.code,
      name: record.name,
      instrument_group: record.instrument_group,
      brand: record.brand,
      model: record.model,
      location: record.location,
      buffer_rate: record.buffer_rate,
      switchover_base_hours: record.switchover_base_hours,
      capabilities: record.capabilities?.map((c) => ({
        tag_name: c.tag_name,
        tag_value: c.tag_value,
      })) || [],
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        code: values.code,
        name: values.name,
        instrument_group: values.instrument_group,
        brand: values.brand,
        model: values.model,
        location: values.location,
        buffer_rate: values.buffer_rate,
        switchover_base_hours: values.switchover_base_hours,
        capabilities: values.capabilities || [],
      };

      if (editingId) {
        await updateInstrument(editingId, payload);
        message.success('仪器信息更新成功');
      } else {
        await createInstrument(payload);
        message.success('仪器添加成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 409) {
          message.error(axiosErr.response?.data?.detail || '仪器编码重复');
          return;
        }
      }
      // validation error handled by antd
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteInstrument(id);
      message.success('仪器已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '仪器编码',
      dataIndex: 'code',
      key: 'code',
      width: 130,
      render: (v: string) => <span style={{ fontFamily: 'monospace', fontWeight: 600, color: ACCENT }}>{v}</span>,
    },
    {
      title: '仪器名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '所属分组',
      dataIndex: 'instrument_group',
      key: 'group',
      width: 140,
      render: (v: string) => (
        <Tag color={GROUP_COLORS[v] || '#94a3b8'}>
          {v === 'GTI_Group' ? '基因毒组' : v === 'Quality_Group' ? '质量组' : v}
        </Tag>
      ),
    },
    {
      title: '品牌/型号',
      key: 'spec',
      width: 180,
      render: (_: unknown, r: Instrument) => (
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {[r.brand, r.model].filter(Boolean).join(' / ') || '-'}
        </span>
      ),
    },
    {
      title: '位置',
      dataIndex: 'location',
      key: 'location',
      width: 90,
      render: (v: string) => v || '-',
    },
    {
      title: '当前状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => (
        <Tag color={STATUS_COLORS[v] || '#94a3b8'}>{STATUS_LABELS[v] || v}</Tag>
      ),
    },
    {
      title: '缓冲率',
      dataIndex: 'buffer_rate',
      key: 'buffer',
      width: 80,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '能力标签',
      dataIndex: 'capabilities',
      key: 'caps',
      width: 200,
      render: (caps: CapabilityReq[]) => (
        <Space size={4} wrap>
          {(caps || []).slice(0, 3).map((c, i) => (
            <Tag key={i} style={{ fontSize: 11, margin: 0 }}>
              {c.tag_name}:{c.tag_value}
            </Tag>
          ))}
          {(caps || []).length > 3 && (
            <Tooltip title={(caps || []).map((c) => `${c.tag_name}:${c.tag_value}`).join(', ')}>
              <Tag style={{ fontSize: 11, margin: 0 }}>+{caps.length - 3}</Tag>
            </Tooltip>
          )}
          {(!caps || caps.length === 0) && <span style={{ color: '#cbd5e1' }}>未配置</span>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: Instrument) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除该仪器？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h2>基础资源台账</h2>
        <p>管理实验室仪器编码、名称、分组、能力标签及状态</p>
      </div>

      <div className="action-bar">
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加仪器
        </Button>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>
          刷新
        </Button>
        <Select
          placeholder="按分组筛选"
          allowClear
          style={{ width: 180 }}
          value={groupFilter}
          onChange={setGroupFilter}
          options={GROUP_OPTIONS}
        />
        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#94a3b8', alignSelf: 'center' }}>
          共 {filtered.length} 台仪器
        </span>
      </div>

      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
      ) : (
        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="id"
          size="middle"
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 1100 }}
        />
      )}

      {/* Add / Edit Modal */}
      <Modal
        title={editingId ? '编辑仪器' : '添加仪器'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        width={640}
        okText={editingId ? '保存' : '添加'}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item
              name="code"
              label="仪器唯一编码"
              rules={[{ required: true, message: '请输入仪器编码' }]}
              style={{ width: 200 }}
            >
              <Input placeholder="如：LCMS_001" />
            </Form.Item>
            <Form.Item
              name="name"
              label="标准仪器名称"
              rules={[{ required: true, message: '请输入仪器名称' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="如：液相色谱-质谱联用仪" />
            </Form.Item>
          </Space>

          <Space style={{ width: '100%' }} size={16}>
            <Form.Item
              name="instrument_group"
              label="所属物理分组"
              rules={[{ required: true }]}
              style={{ width: 200 }}
            >
              <Select options={GROUP_OPTIONS} />
            </Form.Item>
            <Form.Item name="brand" label="品牌" style={{ width: 180 }}>
              <Input placeholder="如：Agilent" />
            </Form.Item>
            <Form.Item name="model" label="型号" style={{ width: 180 }}>
              <Input placeholder="如：1290-6470" />
            </Form.Item>
          </Space>

          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="location" label="物理位置" style={{ width: 160 }}>
              <Input placeholder="如：A201" />
            </Form.Item>
            <Form.Item
              name="buffer_rate"
              label="缓冲率系数"
              tooltip="默认为 1.1，算法将预计执行时间乘以该系数"
              style={{ width: 140 }}
            >
              <InputNumber min={1.0} max={2.0} step={0.05} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="switchover_base_hours" label="切换基准耗时(h)" style={{ width: 160 }}>
              <InputNumber min={0} max={24} step={0.5} style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Form.List name="capabilities">
            {(fields, { add, remove }) => (
              <>
                <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 600, color: '#334155' }}>
                  仪器能力标签集
                  <span style={{ fontWeight: 400, fontSize: 11, color: '#94a3b8', marginLeft: 8 }}>
                    （算法匹配依据：任务能力要求 ⊆ 仪器能力标签）
                  </span>
                </div>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item {...rest} name={[name, 'tag_name']} rules={[{ required: true, message: '选标签' }]}>
                      <Select
                        placeholder="能力标签"
                        style={{ width: 140 }}
                        options={CAP_TAG_OPTIONS}
                      />
                    </Form.Item>
                    <Form.Item
                      noStyle
                      shouldUpdate={(prev, cur) =>
                        prev.capabilities?.[name]?.tag_name !== cur.capabilities?.[name]?.tag_name
                      }
                    >
                      {({ getFieldValue }) => {
                        const tagName = getFieldValue(['capabilities', name, 'tag_name']);
                        const valueOptions = tagName ? CAP_VALUE_OPTIONS[tagName] || [] : [];
                        return (
                          <Form.Item {...rest} name={[name, 'tag_value']} rules={[{ required: true, message: '选值' }]}>
                            <Select
                              placeholder="标签值"
                              style={{ width: 160 }}
                              options={valueOptions}
                            />
                          </Form.Item>
                        );
                      }}
                    </Form.Item>
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => remove(name)}
                      style={{ marginTop: 6 }}
                    />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add({ tag_name: undefined, tag_value: undefined })} block icon={<PlusOutlined />}>
                  添加能力标签
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
};

export default ResourceLedger;

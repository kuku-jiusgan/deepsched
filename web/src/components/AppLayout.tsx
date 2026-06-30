import React from 'react';
import { Layout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  FundOutlined,
  AppstoreOutlined,
  CheckSquareOutlined,
  ProjectOutlined,
  ScheduleOutlined,
  SettingOutlined,
  DashboardOutlined,
  FileTextOutlined,
  DesktopOutlined,
  BarChartOutlined,
  UserOutlined,
  MessageOutlined,
  WarningOutlined,
  DatabaseOutlined,
  PartitionOutlined,
  ApartmentOutlined,
  TableOutlined,
  ToolOutlined,
  ThunderboltOutlined,
  SwapOutlined,
  DollarOutlined,
  BellOutlined,
  SyncOutlined,
  TeamOutlined,
} from '@ant-design/icons';

const { Content, Sider } = Layout;

type MenuItem = {
  key: string;
  icon: React.ReactNode;
  label: string;
  children?: MenuItem[];
};

const menuItems: MenuItem[] = [
  {
    key: '/operations',
    icon: <FundOutlined />,
    label: '运营数据中台',
    children: [
      { key: '/dashboard', icon: <DashboardOutlined />, label: '核心 KPI 仪表盘' },
      { key: '/operations/reports', icon: <FileTextOutlined />, label: '精细化运营报表' },
      { key: '/operations/lab-status', icon: <DesktopOutlined />, label: '实验室状态大屏' },
    ],
  },
  {
    key: '/kanban',
    icon: <AppstoreOutlined />,
    label: '交互式看板',
    children: [
      { key: '/kanban/instrument-gantt', icon: <BarChartOutlined />, label: '仪器甘特图' },
      { key: '/kanban/project-gantt', icon: <BarChartOutlined />, label: '项目甘特图' },
    ],
  },
  {
    key: '/tasks',
    icon: <CheckSquareOutlined />,
    label: '任务管理',
    children: [
      { key: '/tasks/workspace', icon: <UserOutlined />, label: '个人工作台' },
      { key: '/tasks/feedback', icon: <MessageOutlined />, label: '任务反馈' },
      { key: '/tasks/anomaly', icon: <WarningOutlined />, label: '实验异常' },
    ],
  },
  {
    key: '/projects',
    icon: <ProjectOutlined />,
    label: '项目管理',
    children: [
      { key: '/projects/ledger', icon: <DatabaseOutlined />, label: '项目台账管理' },
      { key: '/projects/plan-breakdown', icon: <PartitionOutlined />, label: '项目计划拆解' },
      { key: '/projects/process-dag', icon: <ApartmentOutlined />, label: '标准工序依赖配置' },
      { key: '/projects/resource-ledger', icon: <TableOutlined />, label: '基础资源台账' },
    ],
  },
  {
    key: '/schedule',
    icon: <ScheduleOutlined />,
    label: '排程管理',
    children: [
      { key: '/schedule/rules', icon: <ToolOutlined />, label: '排程规则配置' },
      { key: '/schedule/engine', icon: <ThunderboltOutlined />, label: '自动排程引擎' },
      { key: '/schedule/reschedule', icon: <SwapOutlined />, label: '重排与人工微调' },
      { key: '/schedule/insert-order', icon: <DollarOutlined />, label: '插单与代价计算' },
    ],
  },
  {
    key: '/system',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/system/alerts', icon: <BellOutlined />, label: '智能预警推送' },
      { key: '/system/external-sync', icon: <SyncOutlined />, label: '外部数据同步' },
      { key: '/system/users', icon: <TeamOutlined />, label: '用户管理' },
      { key: '/system/basic', icon: <SettingOutlined />, label: '系统基础管理' },
    ],
  },
];

function findOpenKeys(pathname: string): string[] {
  for (const item of menuItems) {
    if (item.children?.some((child) => child.key === pathname)) {
      return [item.key];
    }
  }
  return [];
}

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <Sider width={220}
        style={{
          background: '#1a1a2e',
          borderRight: 'none',
        }}
      >
        <div style={{
          height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <span style={{
            color: '#fff', fontSize: 15, fontWeight: 600,
            letterSpacing: '0.5px',
          }}>
            DeepSched
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={findOpenKeys(location.pathname)}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            borderRight: 'none',
            marginTop: 8,
          }}
        />
      </Sider>
      <Layout style={{ background: '#f7f8fa' }}>
        <Content style={{ margin: 20, padding: 24, background: '#fff', borderRadius: 10, overflow: 'auto', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
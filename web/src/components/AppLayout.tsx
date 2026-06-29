import React from 'react';
import { Layout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  BarChartOutlined,
  ProjectOutlined,
  ScheduleOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';

const { Content, Sider } = Layout;

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/gantt', icon: <BarChartOutlined />, label: '仪器甘特图' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目看板' },
  { key: '/dag', icon: <ApartmentOutlined />, label: '依赖关系' },
  { key: '/schedule', icon: <ScheduleOutlined />, label: '排程管理' },
];

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <Sider width={200}
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
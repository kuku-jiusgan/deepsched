import React from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

const Page: React.FC = () => (
  <div style={{ padding: 24 }}>
    <Title level={4}>重排与人工微调</Title>
    <div style={{ color: '#999', marginTop: 16 }}>功能开发中…</div>
  </div>
);

export default Page;
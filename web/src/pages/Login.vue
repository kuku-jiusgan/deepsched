<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">DeepSched</h1>
      <p class="login-subtitle">仪器与项目智能调度管理平台</p>
      <a-form layout="vertical"  style="margin-top: 32px">
        <a-form-item>
          <a-input v-model:value="username" placeholder="用户名" size="large" autocomplete="username">
            <template #prefix><UserOutlined /></template>
          </a-input>
        </a-form-item>
        <a-form-item>
          <a-input-password v-model:value="password" placeholder="密码" size="large" autocomplete="current-password" @keyup.enter="handleLogin">
            <template #prefix><LockOutlined /></template>
          </a-input-password>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleLogin" size="large" block :loading="loading">登 录</a-button>
        </a-form-item>
        <div v-if="errorMsg" style="color: #dc2626; text-align: center; font-size: 13px">{{ errorMsg }}</div>
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

onMounted(() => {
  if (route.query.expired === '1') {
    errorMsg.value = '登录已过期，请重新登录'
  }
})

async function handleLogin() {
  if (!username.value || !password.value) { errorMsg.value = '请输入用户名和密码'; return }
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await axios.post('/api/v1/users/login', { username: username.value, password: password.value })
    localStorage.setItem('token', r.data.token)
    localStorage.setItem('user', JSON.stringify(r.data.user))
    router.replace('/dashboard')
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
.login-card {
  width: 400px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.login-title {
  text-align: center;
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
  letter-spacing: 1px;
}
.login-subtitle {
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
  margin-top: 8px;
}
</style>


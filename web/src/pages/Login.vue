<template>
  <div class="login-shell">
    <div class="login-backdrop" />
    <main class="login-layout">
      <section class="login-brand">
        <div class="institute-mark">
          <BankOutlined />
        </div>
        <p class="institute-name">山东大学淄博生物医药研究院</p>
        <h1>资源智能调度协同平台</h1>
      </section>

      <section class="login-card">
        <div class="login-card-header">
          <h2>登录平台</h2>
        </div>

        <a-form layout="vertical" class="login-form">
          <a-form-item>
            <a-input v-model:value="username" placeholder="用户名" size="large" autocomplete="username">
              <template #prefix><UserOutlined /></template>
            </a-input>
          </a-form-item>
          <a-form-item>
            <a-input-password
              v-model:value="password"
              placeholder="密码"
              size="large"
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>
          <a-form-item>
            <a-button type="primary" @click="handleLogin" size="large" block :loading="loading">登 录</a-button>
          </a-form-item>
          <div v-if="errorMsg" class="login-error">{{ errorMsg }}</div>
        </a-form>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { BankOutlined, UserOutlined, LockOutlined } from '@ant-design/icons-vue'
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
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const response = await axios.post('/api/v1/users/login', {
      username: username.value,
      password: password.value,
    })
    localStorage.setItem('token', response.data.token)
    localStorage.setItem('user', JSON.stringify(response.data.user))
    router.replace('/dashboard')
  } catch (error: unknown) {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null
    errorMsg.value = typeof detail === 'string' ? detail : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-shell {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: #f3f6f4;
  color: #17211d;
}

.login-backdrop {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(146, 22, 32, 0.08) 0 1px, transparent 1px 72px),
    linear-gradient(0deg, rgba(22, 92, 74, 0.07) 0 1px, transparent 1px 72px),
    #f4f7f5;
}

.login-backdrop::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, transparent 0 58%, rgba(146, 22, 32, 0.12) 58% 58.35%, transparent 58.35%),
    linear-gradient(0deg, transparent 0 70%, rgba(22, 92, 74, 0.14) 70% 70.35%, transparent 70.35%);
}

.login-layout {
  position: relative;
  z-index: 1;
  width: min(1040px, 100%);
  min-height: 560px;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) 420px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid #d8e0dc;
  border-radius: 10px;
  box-shadow: 0 18px 48px rgba(24, 39, 33, 0.16);
  overflow: hidden;
}

.login-brand {
  position: relative;
  padding: 64px 64px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #fbfcfb;
}

.login-brand::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 7px;
  background: #8f1d2c;
}

.institute-mark {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #8f1d2c;
  color: #fff;
  font-size: 24px;
  margin-bottom: 24px;
}

.institute-name {
  margin: 0 0 14px;
  color: #8f1d2c;
  font-size: 17px;
  font-weight: 700;
}

.login-brand h1 {
  margin: 0;
  max-width: 560px;
  color: #17211d;
  font-size: 42px;
  line-height: 1.18;
  font-weight: 800;
  letter-spacing: 0;
}

.login-card {
  width: 100%;
  padding: 56px 42px;
  background: #fff;
  border-left: 1px solid #dce5e1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.login-card-header {
  margin-bottom: 32px;
}

.login-card h2 {
  margin: 0;
  color: #17211d;
  font-size: 24px;
  font-weight: 700;
}

.login-form {
  margin-top: 0;
}

.login-error {
  color: #dc2626;
  text-align: center;
  font-size: 13px;
}

:deep(.ant-btn-primary) {
  background: #165c4a;
  border-color: #165c4a;
}

:deep(.ant-btn-primary:hover) {
  background: #1e705b;
  border-color: #1e705b;
}

@media (max-width: 860px) {
  .login-shell {
    padding: 24px;
  }

  .login-layout {
    grid-template-columns: 1fr;
  }

  .login-brand {
    padding: 42px 32px;
  }

  .login-brand h1 {
    font-size: 32px;
  }

  .login-card {
    border-left: 0;
    border-top: 1px solid #dce5e1;
    padding: 36px 32px;
  }
}
</style>
